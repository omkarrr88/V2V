class Config:
    GUI_UPDATE_INTERVAL = 5
    LIVE_UPDATE_INTERVAL = 25
    STALE_CLEANUP_INTERVAL = 50
    LOG_INTERVAL = 100
    FILE_WRITE_INTERVAL = 500

"""
V2V Blind Spot Detection — SUMO Simulation Runner (V3.0 5-Field BSM)
=====================================================================
Connects SUMO via TraCI to V3.0 BSD mathematical model engine.
BSM carries only 5 fields: x, y, speed, accel, decel.
All other quantities are derived by BSMParser.

SPEED OPTIMIZATIONS:
  1. BSD processing every step (1.0s) — matches 10 Hz BSM rate
  2. Only process vehicles that HAVE neighbors within 300m
  3. Cap processing at 15 targets per ego
  4. Spatial grid O(N) neighbor lookup
  5. Batch collect states — minimize TraCI round-trips
  6. Write live data every 25 steps only
  7. Differential coloring — only update when alert changes

SCENARIO SUPPORT (§9):
  - TSV (Traffic Signal Violation): --map intersection or --enable-tsv
  - HNR (Hilly Narrow Road): --map hilly or --enable-hnr
  - ScenarioScheduler manages repeating injections
"""

import os
import sys

# Configure stdout to handle utf-8 safely in Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


# ==============================================================================
# ── STEP 1: CRITICAL DLL & ENVIRONMENT FIX (MUST BE FIRST) ────────────────────
# ==============================================================================
import ctypes as _ctypes
import importlib.util as _util

for env_var in ["PROJ_LIB", "PROJ_DATA", "SUMO_HOME"]:
    os.environ.pop(env_var, None)

_path_parts = os.environ.get("PATH", "").split(os.pathsep)
_clean_path = [p for p in _path_parts if all(x not in p for x in ["PostgreSQL", "PostGIS", "Sumo"])]

_ECLIPSE_SUMO_BIN = ""
_sumo_spec = _util.find_spec("sumo")
if _sumo_spec and _sumo_spec.origin:
    _sumo_dir = os.path.dirname(_sumo_spec.origin)
    _candidate = os.path.join(_sumo_dir, "bin")
    if os.path.isdir(_candidate):
        _ECLIPSE_SUMO_BIN = _candidate

if _ECLIPSE_SUMO_BIN:
    os.environ["PATH"] = _ECLIPSE_SUMO_BIN + os.pathsep + os.pathsep.join(_clean_path)
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(_ECLIPSE_SUMO_BIN)
        except Exception:
            pass
    for _dep in ["proj_9.dll", "xerces-c_3_3.dll", "libsumocpp.dll"]:
        _dep_path = os.path.join(_ECLIPSE_SUMO_BIN, _dep)
        if os.path.isfile(_dep_path):
            try:
                _ctypes.WinDLL(_dep_path)
            except Exception:
                pass


# ==============================================================================
# ── STEP 2: TRY LIBSUMO IMPORT ────────────────────────────────────────────────
# ==============================================================================
_use_gui = True
if "--no-gui" in sys.argv:
    _use_gui = False
elif "--gui" in sys.argv:
    _use_gui = True

if not _use_gui:
    try:
        import libsumo as traci      # type: ignore
        import libsumo as tc         # type: ignore
        print(">>> Using LIBSUMO (Native C++ bindings) - Extreme Speed Mode")
    except Exception as _e:
        import traci                 # type: ignore
        import traci.constants as tc # type: ignore
        print(f"--- Using TraCI (TCP) - Normal Speed  [{_e}]")
else:
    import traci                 # type: ignore
    import traci.constants as tc # type: ignore
    print(">>> Using TraCI (TCP) - Normal Speed (GUI mode doesn't support libsumo on Windows)")

# ==============================================================================
# ── STEP 3: REGULAR IMPORTS ───────────────────────────────────────────────────
# ==============================================================================
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Prevent DLL Clashes
sys.modules["pyarrow"] = None  # type: ignore

import json
import time
import argparse
import numpy as np  # type: ignore
import pandas as pd  # type: ignore
import random
import sumolib  # type: ignore
from pathlib import Path
from typing import Dict, List, Any, Tuple

from bsd_engine import BSDEngine, VehicleState, BSMParser, Params, AlertLevel  # type: ignore
from train_ai_model import BSDPredictor  # type: ignore
import scenario_injector  # type: ignore


# ============================================================
# CONFIGURATION
# ============================================================
SUMO_CFG     = "../Maps/atal_v2v.sumocfg"
NET_FILE     = "../Maps/atal.net.xml"
OUTPUT_DIR   = "../Outputs"
METRICS_FILE = os.path.join(OUTPUT_DIR, "bsd_metrics.csv")
ALERTS_FILE  = os.path.join(OUTPUT_DIR, "bsd_alerts.csv")
LIVE_FILE    = os.path.join(OUTPUT_DIR, "bsd_live.json")

MAX_TARGETS_PER_EGO = 15
BSD_INTERVAL     = 1
COMM_RANGE       = 300.0
PACKET_DROP      = 0.05


# ============================================================
# MAP CONFIGURATIONS
# ============================================================
MAP_CONFIGS = {
    'default': {
        'cfg': '../Maps/atal_v2v.sumocfg',
        'net': '../Maps/atal.net.xml',
    },
    'intersection': {
        'cfg': '../Maps/intersection_tsv.sumocfg',
        'net': '../Maps/urban_intersection.net.xml',
    },
    'hilly': {
        'cfg': '../Maps/hilly_v2v.sumocfg',
        'net': '../Maps/hilly_road.net.xml',
    },
}


class GilbertElliottChannel:
    """2-state Markov channel: GOOD (low loss) and BAD (high loss/burst)."""
    def __init__(self, p_g2b=0.01, p_b2g=0.1, plr_good=0.01, plr_bad=0.50):
        self.state = 'GOOD'
        self.p_g2b = p_g2b   
        self.p_b2g = p_b2g   
        self.plr_good = plr_good
        self.plr_bad = plr_bad
    
    def step(self) -> bool:
        """Returns True if packet is RECEIVED, False if dropped."""
        if self.state == 'GOOD':
            if random.random() < self.p_g2b:
                self.state = 'BAD'
        else:
            if random.random() < self.p_b2g:
                self.state = 'GOOD'
        plr = self.plr_good if self.state == 'GOOD' else self.plr_bad
        return random.random() > plr


class BaselineBSD:
    """Euro NCAP Surrogate Safety Baseline (TTC Thresholding) and static box comparison."""
    TTC_WARNING = 2.5
    TTC_CRITICAL = 1.5
    
    def check(self, ego: VehicleState, targets: dict, engine) -> dict:
        alert_left = alert_right = "SAFE"
        static_left = static_right = "SAFE"
        for vid, target in targets.items():
            x_rel, y_rel = engine._to_ego_frame(ego, target.x, target.y)
            if 0.9 <= abs(x_rel) <= 4.4 and -15.0 <= y_rel <= ego.length / 2.0:
                side = "RIGHT" if x_rel > 0 else "LEFT"
                
                half_w = ego.width / 2.0
                if half_w <= abs(x_rel) <= half_w + 3.5 and -8.0 <= y_rel <= ego.length / 2.0:
                    if side == "LEFT": static_left = "WARNING"
                    else: static_right = "WARNING"
                    
                heading_diff = target.heading - ego.heading
                v_rel = ego.speed - target.speed * np.cos(heading_diff)
                d_gap = abs(y_rel) - (ego.length + target.length) / 2.0
                
                if d_gap <= 0:
                    ttc = 0.0
                elif v_rel > 0:
                    ttc = d_gap / v_rel
                else:
                    ttc = float('inf')
                    
                if ttc <= self.TTC_CRITICAL:
                    if side == "LEFT": alert_left = "CRITICAL"
                    else: alert_right = "CRITICAL"
                elif ttc <= self.TTC_WARNING:
                    if side == "LEFT" and alert_left != "CRITICAL": alert_left = "WARNING"
                    if side == "RIGHT" and alert_right != "CRITICAL": alert_right = "WARNING"
                    
        return {'alert_left': alert_left, 'alert_right': alert_right,
                'static_left': static_left, 'static_right': static_right}


# ============================================================
# SCENARIO SCHEDULER (§9)
# ============================================================
class ScenarioScheduler:
    """
    Manages repeating TSV and HNR scenario bursts.
    Each scenario fires every T_repeat steps and lasts T_duration steps.
    """
    def __init__(self, enable_tsv=True, enable_hnr=True,
                 tsv_interval=None, hnr_interval=None):
        self.enable_tsv = enable_tsv
        self.enable_hnr = enable_hnr
        self.tsv_interval = tsv_interval or Params.SCENARIO_REPEAT_INTERVAL
        self.hnr_interval = hnr_interval or Params.SCENARIO_REPEAT_INTERVAL
        self.tsv_duration = Params.SCENARIO_TSV_DURATION
        self.hnr_duration = Params.SCENARIO_HNR_DURATION
        self._tsv_active_until = -1
        self._hnr_active_until = -1

    def get_active_scenario(self, step: int) -> str:
        """Returns the scenario type string for the current step."""
        # Check if TSV burst is active
        if self.enable_tsv and step >= 0:
            if step % self.tsv_interval == 0 and step > 0:
                self._tsv_active_until = step + self.tsv_duration
            if step <= self._tsv_active_until:
                return "TSV"

        # Check if HNR burst is active (offset by half interval to avoid overlap)
        if self.enable_hnr and step >= 0:
            offset = self.hnr_interval // 2
            if (step - offset) % self.hnr_interval == 0 and step > offset:
                self._hnr_active_until = step + self.hnr_duration
            if step <= self._hnr_active_until:
                return "HNR"

        return "normal"


# ============================================================
# GNSS NOISE MODEL
# ============================================================
GNSS_STATE: Dict[str, Tuple[float, float]] = {}
V_STATE_CACHE = {}


def build_raw_bsm(vid, step, sub_data=None, sigma_gps=1.5):
    """
    Construct a raw 5-field BSM dict from SUMO TraCI data.
    BSM = {vid, x, y, speed, accel, decel, vehicle_type, timestamp}
    
    Heading, yaw_rate, etc. are NOT included — they are derived by BSMParser.
    """
    try:
        if sub_data is not None:
            if vid not in V_STATE_CACHE:
                V_STATE_CACHE[vid] = {}
            for k, v in sub_data.items():
                V_STATE_CACHE[vid][k] = v
                
            cache = V_STATE_CACHE[vid]
            pos = cache.get(tc.VAR_POSITION, (0.0, 0.0))
            spd = cache.get(tc.VAR_SPEED, 0.0)
            acc = cache.get(tc.VAR_ACCELERATION, 0.0)
            vtype = cache.get(tc.VAR_TYPE, "sedan").lower()
        else:
            pos = traci.vehicle.getPosition(vid)
            spd = traci.vehicle.getSpeed(vid)
            acc = traci.vehicle.getAcceleration(vid)
            vtype = traci.vehicle.getTypeID(vid).lower()
        
        # GNSS Noise: Correlated random walk (1st-order Gauss-Markov)
        TAU_CORR = 10.0
        SIGMA_DRIVE = sigma_gps * np.sqrt(1.0 - np.exp(-2.0 * 0.1 / TAU_CORR))
        prev_err = GNSS_STATE.get(vid, (0.0, 0.0))
        decay = np.exp(-0.1 / TAU_CORR)
        err_x = decay * prev_err[0] + np.random.normal(0, SIGMA_DRIVE)
        err_y = decay * prev_err[1] + np.random.normal(0, SIGMA_DRIVE)
        GNSS_STATE[vid] = (err_x, err_y)
        pos_x = pos[0] + err_x
        pos_y = pos[1] + err_y

        # Split signed acceleration into accel (≥0) and decel (≥0) per §1.1
        accel_pos = max(0.0, acc)
        decel_pos = max(0.0, -acc)

        return {
            'vid': vid,
            'x': pos_x,
            'y': pos_y,
            'speed': max(0.0, spd),
            'accel': accel_pos,
            'decel': decel_pos,
            'vehicle_type': vtype,
            'timestamp': step,
        }
    except Exception:
        return None


def alert_color(al, ar):
    lvl = {'SAFE': 0, 'CAUTION': 1, 'WARNING': 2, 'CRITICAL': 3}
    m = max(lvl.get(al, 0), lvl.get(ar, 0))
    return [(0,200,0,255), (255,200,0,255), (255,100,0,255), (255,0,0,255)][m]


def parse_args():
    p = argparse.ArgumentParser(description="V2V BSD Simulation (5-Field BSM)")
    p.add_argument("--gui", action="store_true", default=True)
    p.add_argument("--no-gui", action="store_true")
    p.add_argument("--steps", type=int, default=3600)
    p.add_argument("--alpha", type=float, default=None)
    p.add_argument("--beta", type=float, default=None)
    p.add_argument("--gamma", type=float, default=None)
    p.add_argument("--mu", type=float, default=None)
    p.add_argument("--no-lat-ttc", action="store_true")
    p.add_argument("--sigma-gps", type=float, default=None)
    p.add_argument("--ttc-crit", type=float, default=None)
    p.add_argument("--theta-3", type=float, default=None)
    p.add_argument("--plr-g2b", type=float, default=None)
    p.add_argument("--seed", type=int, default=42)
    # Scenario & Map arguments
    p.add_argument("--map", type=str, default="default",
                   choices=["default", "intersection", "hilly"],
                   help="Map to use: default (atal), intersection (TSV), hilly (HNR)")
    p.add_argument("--tsv-interval", type=int, default=None,
                   help="Steps between TSV scenario bursts")
    p.add_argument("--hnr-interval", type=int, default=None,
                   help="Steps between HNR scenario bursts")
    p.add_argument("--disable-tsv", action="store_true",
                   help="Disable Traffic Signal Violation scenario")
    p.add_argument("--disable-hnr", action="store_true",
                   help="Disable Hilly Narrow Road scenario")
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    random.seed(args.seed)
    np.random.seed(args.seed)

    # Select map configuration
    map_cfg = MAP_CONFIGS.get(args.map, MAP_CONFIGS['default'])
    sumo_cfg = map_cfg['cfg']
    net_file = map_cfg['net']

    # Verify map files exist, fall back to default
    if not os.path.exists(sumo_cfg):
        print(f"  Warning: Map '{args.map}' config not found at {sumo_cfg}, using default")
        sumo_cfg = MAP_CONFIGS['default']['cfg']
        net_file = MAP_CONFIGS['default']['net']

    _use_gui = args.gui and not args.no_gui
    if _ECLIPSE_SUMO_BIN:
        _exe = "sumo-gui.exe" if _use_gui else "sumo.exe"
        binary = os.path.join(_ECLIPSE_SUMO_BIN, _exe)
    else:
        binary = "sumo-gui" if _use_gui else "sumo"

    cmd = [
        binary, "-c", sumo_cfg, "--start",
        "--step-length", "0.1",
        "--quit-on-end",
        "--no-step-log", "true",
        "--no-duration-log", "true",
        "--no-warnings", "true",
        "--seed", str(args.seed),
    ]

    # Initialize scenario scheduler
    scheduler = ScenarioScheduler(
        enable_tsv=not args.disable_tsv,
        enable_hnr=not args.disable_hnr,
        tsv_interval=args.tsv_interval,
        hnr_interval=args.hnr_interval,
    )

    # Initialize BSM parser (shared across all vehicles)
    bsm_parser = BSMParser()

    print("=" * 70)
    print(">>> V2V Blind Spot Detection - SUMO Simulation")
    print("    Mathematical Model V3.0 | 5-Field BSM | Scenario Support")
    print("=" * 70)
    print(f"   Binary:     {binary}")
    print(f"   Map:        {args.map} ({sumo_cfg})")
    print(f"   Max Steps:  {args.steps}")
    print(f"   Sim Time:   {args.steps * 0.1:.0f}s ({args.steps * 0.1 / 60:.1f} min)")
    print(f"   BSD Every:  {BSD_INTERVAL} steps (0.1 s/step -> 10 Hz BSM)")
    print(f"   TSV:        {'enabled' if not args.disable_tsv else 'disabled'}")
    print(f"   HNR:        {'enabled' if not args.disable_hnr else 'disabled'}")
    print("=" * 70)

    traci.start(cmd)
    print(">>> SUMO started")

    net = sumolib.net.readNet(net_file)
    print(f">>> Network: {len(net.getEdges())} edges")

    ai = BSDPredictor()
    has_ai = ai.model is not None

    engines: Dict[str, Any] = {}
    last_colors: Dict[str, str] = {}
    metrics_log: List[Any] = []
    alerts_log: List[Any] = []
    channels: Dict[tuple, GilbertElliottChannel] = {}
    baseline_bsd = BaselineBSD()

    # Scenario injectors (§9)
    from scenario_injector import TSVInjector, HNRInjector
    tsv_injector = TSVInjector() if not args.disable_tsv else None
    hnr_injector = HNRInjector() if not args.disable_hnr else None
    if tsv_injector:
        print("🚦 TSV Injector: active (p_violator=0.3)")
    if hnr_injector:
        print("⛰️  HNR Injector: active")
    
    live = {
        'step': 0, 'vehicles': {}, 'has_ai': has_ai,
        'active_count': 0,
        'alert_counts': {'safe': 0, 'caution': 0, 'warning': 0, 'critical': 0},
        'comm_links': [],
        'scenario': 'normal',
        'params': {
            'L_base': Params.L_BASE, 'lambda': Params.LAMBDA_SCALE,
            'W_lane': Params.W_LANE, 'sigma_gps': Params.SIGMA_GPS,
            'alpha': Params.ALPHA, 'beta': Params.BETA, 'gamma': Params.GAMMA,
            'theta1': Params.THETA_1, 'theta2': Params.THETA_2, 'theta3': Params.THETA_3,
            'R_comm': Params.R_COMM, 'F_BSM': Params.F_BSM,
        }
    }

    max_steps = args.steps
    use_gui = args.gui and not args.no_gui
    t0 = time.time()

    cum_safe = cum_caution = cum_warning = cum_critical = 0

    sigma_gps_val = args.sigma_gps if args.sigma_gps is not None else Params.SIGMA_GPS
    if args.mu is not None:
        Params.MU_DEFAULT = args.mu
    
    print(f">>> Simulation running... {'(with overrides)' if any([args.alpha, args.beta, args.gamma, args.sigma_gps, args.ttc_crit, args.theta_3, args.plr_g2b, args.no_lat_ttc, args.mu]) else ''}")

    for step in range(max_steps):
        traci.simulationStep()

        if step % BSD_INTERVAL != 0:
            continue

        # Determine active scenario for this step
        active_scenario = scheduler.get_active_scenario(step)
        bsm_parser.set_scenario_context(active_scenario if active_scenario != "normal" else "normal")

        # Check ground truth collisions
        collision_vids: set = set()
        if step % 10 == 0:
            try:
                collisions = traci.simulation.getCollisions()
                collision_vids = {c.collider for c in collisions} | {c.victim for c in collisions}
            except Exception:
                pass

        # Subscribe new vehicles
        departed = traci.simulation.getDepartedIDList()
        for vid in departed:
            traci.vehicle.subscribe(vid, [
                tc.VAR_POSITION, tc.VAR_SPEED, tc.VAR_ACCELERATION,
                tc.VAR_TYPE
            ])
            if vid.startswith('bsp_') or vid.startswith('cls_'):
                traci.vehicle.setSpeedMode(vid, 0)
                traci.vehicle.setLaneChangeMode(vid, 0)

        # Get bulk data
        sub_results = traci.vehicle.getAllSubscriptionResults()
        vids = list(sub_results.keys())
        n_active = len(vids)
        if not vids:
            continue

        # Evict stale data
        arrived = traci.simulation.getArrivedIDList()
        for vid in arrived:
            GNSS_STATE.pop(vid, None)
            V_STATE_CACHE.pop(vid, None)
            bsm_parser.evict(vid)

        active_set = set(vids)
        for stale_vid in list(V_STATE_CACHE.keys()):
            if stale_vid not in active_set:
                del V_STATE_CACHE[stale_vid]
        for stale_vid in list(GNSS_STATE.keys()):
            if stale_vid not in active_set:
                del GNSS_STATE[stale_vid]
        for stale_vid in list(engines.keys()):
            if stale_vid not in active_set:
                del engines[stale_vid]
        stale_channel_keys = [
            k for k in list(channels.keys())
            if k[0] not in active_set or k[1] not in active_set
        ]
        for k in stale_channel_keys:
            del channels[k]

        # ── Build 5-field BSM and parse into VehicleState via BSMParser ──
        states: Dict[str, VehicleState] = {}
        for v, data in sub_results.items():
            raw_bsm = build_raw_bsm(v, step, sub_data=data, sigma_gps=sigma_gps_val)
            if raw_bsm is not None:
                states[v] = bsm_parser.parse(raw_bsm)

        if not states:
            continue

        # Build spatial grid
        grid: Dict[tuple, list] = {}
        for v, s in states.items():
            cell = (int(s.x // COMM_RANGE), int(s.y // COMM_RANGE))
            grid.setdefault(cell, []).append(v)

        # Filter to vehicles with neighbors
        ego_ids = []
        for vid, s in states.items():
            cell_x = int(s.x // COMM_RANGE)
            cell_y = int(s.y // COMM_RANGE)
            has_n = False
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if len(grid.get((cell_x+dx, cell_y+dy), [])) > (1 if dx==0 and dy==0 else 0):
                        has_n = True
                        break
                if has_n: break
            if has_n:
                ego_ids.append(vid)

        # Demonstration scenario injection (existing system)
        scenario_injector.inject_blind_spot_scenario(step, net, traci)
        scenario_injector.force_vehicle_interactions(step, net, traci)

        # TSV/HNR scenario-specific injectors (§9)
        if active_scenario == 'TSV' and tsv_injector is not None:
            tsv_injector.step(step, net, traci)
        if active_scenario == 'HNR' and hnr_injector is not None:
            hnr_injector.step(step, net, traci)

        # ── Per-vehicle BSD processing ──
        step_vehs: Dict[str, Any] = {}
        step_caution = step_warning = step_critical = 0

        ai_batch_keys: list = []
        ai_batch_rows: list = []
        interim_results: list = []

        for ego_vid in ego_ids:
            ego = states.get(ego_vid)
            if ego is None:
                continue
            
            # Find neighbors via grid
            ec = (int(ego.x // COMM_RANGE), int(ego.y // COMM_RANGE))
            candidates = []
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    candidates.extend(grid.get((ec[0]+dx, ec[1]+dy), []))
            
            neighbors: Dict[str, VehicleState] = {}
            received = set()
            for tv in candidates:
                if tv == ego_vid:
                    continue
                ts = states.get(tv)
                if ts is None:
                    continue
                dsq = (ego.x - ts.x)**2 + (ego.y - ts.y)**2
                if dsq <= COMM_RANGE**2:
                    neighbors[tv] = ts
                    chan_key = (ego_vid, tv)
                    if chan_key not in channels:
                        if args.plr_g2b is not None:
                            channels[chan_key] = GilbertElliottChannel(p_g2b=args.plr_g2b)
                        else:
                            channels[chan_key] = GilbertElliottChannel()
                    if channels[chan_key].step():
                        received.add(tv)

            if not neighbors:
                continue

            if len(neighbors) > MAX_TARGETS_PER_EGO:
                neighbors = dict(
                    sorted(neighbors.items(),
                           key=lambda kv: (ego.x - kv[1].x)**2 + (ego.y - kv[1].y)**2
                    )[:MAX_TARGETS_PER_EGO]
                )
                received = received & set(neighbors.keys())

            # Run BSD engine
            if ego_vid not in engines:
                engines[ego_vid] = BSDEngine(
                    alpha=args.alpha, beta=args.beta, gamma=args.gamma,
                    use_lateral_ttc=not args.no_lat_ttc,
                    sigma_gps=args.sigma_gps, ttc_crit=args.ttc_crit, theta_3=args.theta_3
                )
            
            # Apply scenario context to engine
            engines[ego_vid].set_scenario_context(active_scenario)
            
            result = engines[ego_vid].process_step(ego, neighbors, received)
            base_result = baseline_bsd.check(ego, neighbors, engines[ego_vid])

            al = result['alert_left']
            ar = result['alert_right']
            
            if use_gui and (step % Config.GUI_UPDATE_INTERVAL == 0):
                key = f"{al}_{ar}"
                if last_colors.get(ego_vid) != key:
                    try:
                        traci.vehicle.setColor(ego_vid, alert_color(al, ar))
                        last_colors[ego_vid] = key
                    except Exception:
                        pass

            if al == 'SAFE' and ar == 'SAFE':
                cum_safe += 1
            elif al == 'CRITICAL' or ar == 'CRITICAL':
                step_critical += 1; cum_critical += 1
            elif al == 'WARNING' or ar == 'WARNING':
                step_warning += 1; cum_warning += 1
            else:
                step_caution += 1; cum_caution += 1

            if received:
                for target_vid in received:
                    live['comm_links'].append({'ego': ego_vid, 'target': target_vid})

            # AI features — adapted for 5-field BSM
            target_details = result.get('target_details', [])
            max_gap  = min([t.get('d_gap', 100.0) for t in target_details]) if target_details else 100.0
            max_plr  = max([t.get('plr', 0.0) for t in target_details]) if target_details else 0.0

            k_lost_max = 0
            rel_speed  = 0.0
            target_angle = 0.0
            if target_details:
                top_tv = target_details[0]['target_vid']
                if ego_vid in engines and top_tv in engines[ego_vid].target_trackers:
                    k_lost_max = engines[ego_vid].target_trackers[top_tv].k_lost
                if top_tv in states:
                    v_tgt_proj = states[top_tv].speed * np.cos(states[top_tv].heading - ego.heading)
                    y_rel_top = target_details[0].get('y_rel', -1)
                    rel_speed = ego.speed - v_tgt_proj if y_rel_top >= 0 else v_tgt_proj - ego.speed
                    target_angle = np.arctan2(states[top_tv].y - ego.y, states[top_tv].x - ego.x) - ego.heading

            # Build AI feature row — 5-field BSM adapted
            ai_batch_keys.append(ego_vid)
            ai_batch_rows.append({
                'speed': ego.speed,
                'accel': ego.accel,
                'decel': ego.decel,
                'yaw_rate': ego.yaw_rate,
                'num_targets': result['num_targets'],
                'signals': 0,  # Not available in 5-field BSM
                'max_gap': max_gap, 'rel_speed': rel_speed,
                'max_plr': max_plr, 'k_lost_max': k_lost_max,
                'speed_kmh': ego.speed * 3.6,
                'abs_accel': abs(ego.net_accel),
                'abs_yaw_rate': abs(ego.yaw_rate),
                'is_braking': 1 if ego.decel > 1.0 else 0,
                'is_signaling': 0,  # Not available
                'has_targets': 1 if result['num_targets'] > 0 else 0,
                'speed_category': 0 if ego.speed < 5 else (1 if ego.speed < 20 else 2),
                'closing_speed': rel_speed,
                'target_angle': target_angle,
                'brake_ratio': ego.decel / max(ego.speed, 0.1),
                'abs_net_accel': abs(ego.net_accel),
                'scenario_tsv': 1 if active_scenario == 'TSV' else 0,
                'scenario_hnr': 1 if active_scenario == 'HNR' else 0,
            })
            interim_results.append((ego_vid, result, ego, target_details, max_gap,
                                     rel_speed, max_plr, k_lost_max, al, ar, base_result, target_angle))


        # ── Batch AI prediction ──
        ai_results_map: Dict[str, Any] = {}
        if has_ai and ai_batch_rows:
            batch_out = ai.batch_predict(ai_batch_rows)
            for k, v in zip(ai_batch_keys, batch_out):
                ai_results_map[k] = v

        # ── Assemble metrics ──
        log_this_step = (step % (BSD_INTERVAL * 2) == 0)
        for (ego_vid, result, ego, target_details, max_gap, rel_speed, max_plr,
             k_lost_max, al, ar, base_result, target_angle) in interim_results:
            ai_result = ai_results_map.get(ego_vid, {'ai_alert': 'N/A', 'ai_confidence': 0.0, 'ai_critical_prob': 0.0})

            sorted_details = sorted(target_details, key=lambda x: x['cri'], reverse=True)
            target_left  = next((t for t in sorted_details if t['side'] == 'LEFT'),  None)
            target_right = next((t for t in sorted_details if t['side'] == 'RIGHT'), None)

            if log_this_step:
                metrics_log.append({
                    'step': step, 'ego_vid': ego_vid,
                    'x': ego.x, 'y': ego.y,
                    'speed': ego.speed,
                    'accel': ego.accel,
                    'decel': ego.decel,
                    'derived_heading': ego.heading,
                    'derived_yaw_rate': ego.yaw_rate,
                    'heading_deg': np.degrees(ego.heading),
                    'yaw_rate': ego.yaw_rate,
                    'max_gap': max_gap, 'rel_speed': rel_speed,
                    'max_plr': max_plr, 'k_lost_max': k_lost_max,
                    'target_angle': target_angle,
                    'cri_left': result['cri_left'], 'cri_right': result['cri_right'],
                    'P_left':        target_left['P']              if target_left  else 0.0,
                    'R_decel_left':  target_left['R_decel']        if target_left  else 0.0,
                    'R_ttc_left':    target_left['R_ttc']          if target_left  else 0.0,
                    'R_intent_left': target_left['R_intent']       if target_left  else 0.0,
                    'plr_mult_left': target_left['plr_multiplier'] if target_left  else 1.0,
                    'severity_gate_left':  target_left['severity_gate']  if target_left  else 0.0,
                    'in_zone_left':        int(target_left['in_zone'])   if target_left  else 0,
                    'P_right':        target_right['P']              if target_right else 0.0,
                    'R_decel_right':  target_right['R_decel']        if target_right else 0.0,
                    'R_ttc_right':    target_right['R_ttc']          if target_right else 0.0,
                    'R_intent_right': target_right['R_intent']       if target_right else 0.0,
                    'plr_mult_right': target_right['plr_multiplier'] if target_right else 1.0,
                    'severity_gate_right': target_right['severity_gate'] if target_right else 0.0,
                    'in_zone_right':       int(target_right['in_zone'])  if target_right else 0,
                    'alert_left': al, 'alert_right': ar,
                    'baseline_left':  base_result['alert_left'],
                    'baseline_right': base_result['alert_right'],
                    'static_left':    base_result['static_left'],
                    'static_right':   base_result['static_right'],
                    'ground_truth_collision': 1 if ego_vid in collision_vids else 0,
                    'num_targets': result['num_targets'],
                    'signals': 0,  # Not available in 5-field BSM
                    'scenario_type': active_scenario,
                    'ai_alert':        ai_result.get('ai_alert', 'N/A'),
                    'ai_confidence':   ai_result.get('ai_confidence', 0.0),
                    'ai_critical_prob': ai_result.get('ai_critical_prob', 0.0),
                })

            if al != 'SAFE' or ar != 'SAFE':
                alerts_log.append({
                    'step': step, 'ego_vid': ego_vid,
                    'cri_left': result['cri_left'], 'cri_right': result['cri_right'],
                    'alert_left': al, 'alert_right': ar,
                    'scenario_type': active_scenario,
                    'top_threat': result['target_details'][0]['target_vid'] if result['target_details'] else '',
                    'top_cri': max(result['cri_left'], result['cri_right']),
                })

            if len(step_vehs) < 200:
                tops = sorted(result['target_details'], key=lambda t: t['cri'], reverse=True)[:3]
                step_vehs[ego_vid] = {
                    'x': float(ego.x), 'y': float(ego.y),
                    'speed': round(float(ego.speed), 2),
                    'cri_left': round(float(result['cri_left']), 4),
                    'cri_right': round(float(result['cri_right']), 4),
                    'alert_left': al, 'alert_right': ar,
                    'ai_alert': ai_result.get('ai_alert', 'N/A'),
                    'ai_confidence': round(float(ai_result.get('ai_confidence', 0.0)), 3),
                    'num_targets': result['num_targets'],
                    'top_threats': [
                        {'vid': t['target_vid'], 'cri': round(float(t['cri']), 4),
                         'side': t['side'], 'P': round(float(t['P']), 4),
                         'R_decel': round(float(t['R_decel']), 4), 'R_ttc': round(float(t['R_ttc']), 4),
                         'R_ttc_lon': round(float(t.get('R_ttc_lon', 0.0)), 4),
                         'R_ttc_lat': round(float(t.get('R_ttc_lat', 0.0)), 4),
                         'R_intent': round(float(t['R_intent']), 4),
                         'd_gap': round(float(t['d_gap']), 2), 'plr': round(float(t['plr']), 3)}
                        for t in tops
                    ]
                }

        live['step'] = step
        live['vehicles'] = step_vehs
        live['active_count'] = n_active
        live['scenario'] = active_scenario
        live['comm_links'] = live['comm_links'][-200:] if len(live['comm_links']) > 200 else live['comm_links']
        live['alert_counts'] = {
            'safe': cum_safe, 'caution': cum_caution,
            'warning': cum_warning, 'critical': cum_critical
        }
        live['total_alerts_logged'] = len(alerts_log)
        live['elapsed'] = float(round(float(time.time() - t0), 1))
        live['params'] = {'ALPHA': Params.ALPHA, 'BETA': Params.BETA,
                          'GAMMA': Params.GAMMA, 'THETA_3': Params.THETA_3}
        
        if step % Config.LIVE_UPDATE_INTERVAL == 0:
            try:
                _tmp = LIVE_FILE + '.tmp'
                with open(_tmp, 'w') as f:
                    json.dump(live, f)
                os.replace(_tmp, LIVE_FILE)
            except Exception:
                pass

        if step % Config.FILE_WRITE_INTERVAL == 0 and step > 0:
            if metrics_log:
                pd.DataFrame(metrics_log).to_csv(METRICS_FILE, index=False)
            if alerts_log:
                pd.DataFrame(alerts_log).to_csv(ALERTS_FILE, index=False)

        if step % Config.STALE_CLEANUP_INTERVAL == 0 and step > 0:
            for eng in engines.values():
                eng.cleanup_stale_trackers(max_stale_steps=15)

        if step % Config.LOG_INTERVAL == 0:
            elapsed = float(time.time() - t0)
            eta = float((elapsed / max(step, 1)) * (max_steps - step))
            alerted = step_caution + step_warning + step_critical
            scenario_tag = f" [{active_scenario}]" if active_scenario != "normal" else ""
            print(f"  Step {step:>5}/{max_steps} | "
                  f"Active: {n_active:>3} | BSD: {len(ego_ids):>3} | "
                  f"Alerts: {alerted:>2} (C:{step_caution} W:{step_warning} X:{step_critical}){scenario_tag} | "
                  f"{elapsed:.0f}s (ETA {eta:.0f}s)")


    # ============================================================
    # FINAL
    # ============================================================
    traci.close()
    elapsed = float(time.time() - t0)

    if metrics_log:
        pd.DataFrame(metrics_log).to_csv(METRICS_FILE, index=False)
    if alerts_log:
        pd.DataFrame(alerts_log).to_csv(ALERTS_FILE, index=False)
    
    live['step'] = max_steps
    live['elapsed'] = float(round(elapsed, 1))
    live['finished'] = True
    with open(LIVE_FILE, 'w') as f:
        json.dump(live, f)

    print("\n" + "=" * 70)
    print(">>> SIMULATION COMPLETE")
    print(f"   Steps:    {max_steps}")
    print(f"   Time:     {elapsed:.1f}s ({elapsed/60:.1f}min)")
    print(f"   Metrics:  {len(metrics_log)} rows")
    print(f"   Alerts:   {len(alerts_log)} events")
    
    if metrics_log:
        df = pd.DataFrame(metrics_log)
        for side in ['left', 'right']:
            col = f'alert_{side}'
            if col in df.columns:
                counts = df[col].value_counts().to_dict()
                print(f"   {side.upper()}: {counts}")
        # Scenario breakdown
        if 'scenario_type' in df.columns:
            sc_counts = df['scenario_type'].value_counts().to_dict()
            print(f"   Scenarios: {sc_counts}")

    print("=" * 70)
    print(">>> Run: streamlit run dashboard.py")
    print("=" * 70)


if __name__ == "__main__":
    main()

