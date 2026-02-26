"""
V2V Blind Spot Detection — SUMO Simulation Runner (Ultra-Fast)
===============================================================
Connects SUMO via TraCI to V3.0 BSD mathematical model engine.

SPEED OPTIMIZATIONS FOR 3600 STEPS IN 5-10 MINUTES:
  1. BSD processing every 10th step (1.0s) — still faster than BSM rate
  2. Only process vehicles that HAVE neighbors within 300m (skip isolated)  
  3. Cap processing at 30 vehicles per BSD step (random sample)
  4. Spatial grid O(N) neighbor lookup
  5. Batch collect states — minimize TraCI round-trips
  6. Write live data every 50 steps only
  7. Differential coloring — only update when alert changes
  8. NO scenario injector overhead (routes handle scenarios)
"""

import os
import sys

# Configure stdout to handle utf-8 safely in Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


# ==============================================================================
# ── STEP 1: CRITICAL DLL & ENVIRONMENT FIX (MUST BE FIRST) ────────────────────
# ==============================================================================
# We must sanitize the environment and load SUMO DLLs BEFORE any other imports
# (like numpy/pandas) to prevent "DLL Hell" or version conflicts.

import ctypes as _ctypes
import importlib.util as _util

# 1. ELIMINATE CONFLICTS (PostgreSQL/PostGIS/System SUMO)
# Clear older environment variables that might confuse the 1.26.0 loader
for env_var in ["PROJ_LIB", "PROJ_DATA", "SUMO_HOME"]:
    os.environ.pop(env_var, None)

# 2. SANITIZE PATH
# Remove any Postgre/PostGIS/System Sumo paths from current process PATH 
# This prevents picking up an incompatible 'proj.dll' from the system.
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
    # Prepend our correct bin dir to the clean path
    os.environ["PATH"] = _ECLIPSE_SUMO_BIN + os.pathsep + os.pathsep.join(_clean_path)
    
    # Register with Python's DLL directory search (Python 3.8+)
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(_ECLIPSE_SUMO_BIN)
        except Exception:
            pass
    
    # 3. PRE-LOAD DLLs (Atomic pinning)
    # Force the process to use OUR versions of these often-conflicted DLLs
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
# Libsumo does not support GUI on Windows. If the user wants GUI, we MUST use TraCI.
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
# Add the Scripts directory to the path for relative imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Prevent DLL Clashes: 'sumo' ships conflicting versions of parquet/zlib/arrow.
# Since sklearn/xgboost don't strictly require pyarrow, we block it from loading.
sys.modules["pyarrow"] = None  # type: ignore

import json
import time

import argparse
import numpy as np  # type: ignore
import pandas as pd  # type: ignore
import random
import sumolib  # type: ignore
from pathlib import Path

from bsd_engine import BSDEngine, VehicleState, Params, AlertLevel  # type: ignore
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

# Maximum targets any single ego vehicle processes per BSD step.
# Dramatically reduces O(N²) growth when 80+ vehicles are on-road.
MAX_TARGETS_PER_EGO = 15
# V3.0 SCIENTIFIC PURITY: Math engine runs every step. With step-length=0.1s, 
# this perfectly matches the 10 Hz BSM physical requirement of the equations.
BSD_INTERVAL     = 1
COMM_RANGE       = 300.0    # V2V communication range (meters)
PACKET_DROP      = 0.05     # 5% packet loss

class GilbertElliottChannel:
    """
    2-state Markov channel: GOOD (low loss) and BAD (high loss/burst).
    Transitions are governed by p (G→B) and q (B→G).
    """
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
    """
    Euro NCAP Surrogate Safety Baseline (TTC Thresholding) and static box comparison.
    """
    TTC_WARNING = 2.5
    TTC_CRITICAL = 1.5
    
    def check(self, ego: VehicleState, targets: dict[str, VehicleState], engine) -> dict:
        alert_left = alert_right = "SAFE"
        static_left = static_right = "SAFE"
        for vid, target in targets.items():
            x_rel, y_rel = engine._to_ego_frame(ego, target.x, target.y)
            # Only consider targets in adjacent lanes and behind/next to ego
            if 0.9 <= abs(x_rel) <= 4.4 and -15.0 <= y_rel <= ego.length / 2.0:
                side = "RIGHT" if x_rel > 0 else "LEFT"
                
                # Static Box Baseline (3.5m x 8.0m zone)
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
                    
        return {'alert_left': alert_left, 'alert_right': alert_right, 'static_left': static_left, 'static_right': static_right}

DEFAULT_LENGTH = 4.5
DEFAULT_WIDTH  = 1.8
DEFAULT_MASS   = 1800.0


def parse_args():
    p = argparse.ArgumentParser(description="V2V BSD Simulation")
    p.add_argument("--gui", action="store_true", default=True)
    p.add_argument("--no-gui", action="store_true")
    p.add_argument("--steps", type=int, default=3600)
    p.add_argument("--alpha", type=float, default=None)
    p.add_argument("--beta", type=float, default=None)
    p.add_argument("--gamma", type=float, default=None)
    p.add_argument("--no-lat-ttc", action="store_true")
    p.add_argument("--sigma-gps", type=float, default=None)
    p.add_argument("--ttc-crit", type=float, default=None)
    p.add_argument("--theta-3", type=float, default=None)
    p.add_argument("--plr-g2b", type=float, default=None)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def heading_from_sumo(angle_deg):
    return np.pi / 2.0 - angle_deg * np.pi / 180.0

from typing import Dict, Tuple
V_STATE_CACHE = {}
GNSS_STATE: Dict[str, Tuple[float, float]] = {}  # vid -> (cumulative_x_error, cumulative_y_error)

def get_state(vid, step, prev_h, sub_data=None, sigma_gps=1.5):
    try:
        if sub_data is not None:
            # TraCI omits unchanged variables in subscriptions. Use cache to fill gaps.
            if vid not in V_STATE_CACHE:
                V_STATE_CACHE[vid] = {}
            for k, v in sub_data.items():
                V_STATE_CACHE[vid][k] = v
                
            cache = V_STATE_CACHE[vid]
            
            pos = cache.get(tc.VAR_POSITION, (0.0, 0.0))
            spd = cache.get(tc.VAR_SPEED, 0.0)
            acc = cache.get(tc.VAR_ACCELERATION, 0.0)
            ang = cache.get(tc.VAR_ANGLE, 0.0)
            length = cache.get(tc.VAR_LENGTH, DEFAULT_LENGTH)
            width = cache.get(tc.VAR_WIDTH, DEFAULT_WIDTH)
            signals = cache.get(tc.VAR_SIGNALS, 0)
            vtype = cache.get(tc.VAR_TYPE, "sedan").lower()
        else:
            pos = traci.vehicle.getPosition(vid)
            spd = traci.vehicle.getSpeed(vid)
            acc = traci.vehicle.getAcceleration(vid)
            ang = traci.vehicle.getAngle(vid)
            length = traci.vehicle.getLength(vid)
            width = traci.vehicle.getWidth(vid)
            signals = traci.vehicle.getSignals(vid)
            vtype = traci.vehicle.getTypeID(vid).lower()
        
        hdg = heading_from_sumo(ang)
        
        # GNSS Noise: Correlated random walk (1st-order Gauss-Markov process)
        # Correlation time τ_corr = 10s → decay = exp(-0.1/10) ≈ 0.990
        # This models slowly-varying GNSS error (atmospheric, satellite geometry)
        TAU_CORR = 10.0   # seconds — GPS error correlation time
        SIGMA_DRIVE = sigma_gps * np.sqrt(1.0 - np.exp(-2.0 * 0.1 / TAU_CORR))
        prev_err = GNSS_STATE.get(vid, (0.0, 0.0))
        decay = np.exp(-0.1 / TAU_CORR)
        err_x = decay * prev_err[0] + np.random.normal(0, SIGMA_DRIVE)
        err_y = decay * prev_err[1] + np.random.normal(0, SIGMA_DRIVE)
        GNSS_STATE[vid] = (err_x, err_y)
        pos_x = pos[0] + err_x
        pos_y = pos[1] + err_y

        yr = 0.0
        if vid in prev_h:
            d = hdg - prev_h[vid]
            d = (d + np.pi) % (2 * np.pi) - np.pi
            yr = d / (0.1 * BSD_INTERVAL)
        prev_h[vid] = hdg

        if 'truck' in vtype:
            vt, mass = 'truck', 10000.0
        elif 'suv' in vtype:
            vt, mass = 'suv', 2200.0
        else:
            vt, mass = 'sedan', 1800.0

        return VehicleState(
            vid=vid, x=pos_x, y=pos_y,
            speed=max(0, spd), accel=acc, heading=hdg,
            yaw_rate=yr,
            length=length if length > 0 else DEFAULT_LENGTH,
            width=width if width > 0 else DEFAULT_WIDTH,
            mass=mass, mu=0.7, signals=signals,
            vehicle_type=vt, timestamp=step,
        )
    except Exception as e:
        return None


def alert_color(al, ar):
    lvl = {'SAFE': 0, 'CAUTION': 1, 'WARNING': 2, 'CRITICAL': 3}
    m = max(lvl.get(al, 0), lvl.get(ar, 0))
    return [(0,200,0,255), (255,200,0,255), (255,100,0,255), (255,0,0,255)][m]


def main():
    args = parse_args()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    random.seed(args.seed)
    np.random.seed(args.seed)

    # Use eclipse-sumo's bundled binary when available (matches libsumo DLL exactly)
    _use_gui = args.gui and not args.no_gui
    if _ECLIPSE_SUMO_BIN:
        _exe = "sumo-gui.exe" if _use_gui else "sumo.exe"
        binary = os.path.join(_ECLIPSE_SUMO_BIN, _exe)
    else:
        binary = "sumo-gui" if _use_gui else "sumo"

    cmd = [
        binary, "-c", SUMO_CFG, "--start",
        # ── HIGH PLAYBACK SPEED MODE ──────────────────────────────────────
        "--step-length", "0.1",
        "--quit-on-end",         # Close GUI after completion
        # Suppress per-step terminal printing inside SUMO (significant I/O saving)
        "--no-step-log", "true",
        "--no-duration-log", "true",
        "--no-warnings", "true",
        "--seed", str(args.seed),
    ]

    print("=" * 70)
    print(">>> V2V Blind Spot Detection - SUMO Simulation")
    print("    Mathematical Model V3.0 | Ultra-Fast Mode")
    print("=" * 70)
    print(f"   Binary:     {binary}")
    print(f"   Max Steps:  {args.steps}")
    print(f"   Sim Time:   {args.steps * 0.1:.0f}s ({args.steps * 0.1 / 60:.1f} min)")
    print(f"   BSD Every:  {BSD_INTERVAL} steps (0.1 s/step -> 10 Hz BSM)")
    print(f"   Spatial filtering: neighbors-only (no vehicle cap)")
    print("=" * 70)

    traci.start(cmd)
    print(">>> SUMO started")

    net = sumolib.net.readNet(NET_FILE)
    print(f">>> Network: {len(net.getEdges())} edges")

    ai = BSDPredictor()
    has_ai = ai.model is not None

    from typing import Dict, List, Any
    engines: Dict[str, Any] = {}
    prev_h: Dict[str, Any] = {}
    last_colors: Dict[str, str] = {}
    metrics_log: List[Any] = []
    alerts_log: List[Any] = []
    channels: Dict[tuple, GilbertElliottChannel] = {}
    baseline_bsd = BaselineBSD()
    
    live = {
        'step': 0, 'vehicles': {}, 'has_ai': has_ai,
        'active_count': 0,
        'alert_counts': {'safe': 0, 'caution': 0, 'warning': 0, 'critical': 0},
        'comm_links': [], # List of (ego_vid, target_vid) for visualization
        'params': {
            'L_base': Params.L_BASE, 'lambda': Params.LAMBDA_SCALE,
            'W_lane': Params.W_LANE, 'sigma_gps': Params.SIGMA_GPS,
            'alpha': Params.ALPHA, 'beta': Params.BETA, 'gamma': Params.GAMMA,
            'theta1': Params.THETA_1, 'theta2': Params.THETA_2, 'theta3': Params.THETA_3,
            'R_comm': Params.R_COMM, 'F_BSM': Params.F_BSM,
        }
    }

    max_steps = args.steps
    use_gui = args.gui and not args.no_gui   # False in headless (--no-gui) runs
    t0 = time.time()

    # Cumulative counters for dashboard
    cum_safe = 0
    cum_caution = 0
    cum_warning = 0
    cum_critical = 0

    print(f">>> Simulation running... {'(with overrides)' if any([args.alpha, args.beta, args.gamma, args.sigma_gps, args.ttc_crit, args.theta_3, args.plr_g2b, args.no_lat_ttc]) else ''}")
    
    sigma_gps_val = args.sigma_gps if args.sigma_gps is not None else Params.SIGMA_GPS
    for step in range(max_steps):
        traci.simulationStep()

        # Only do BSD processing every N steps
        if step % BSD_INTERVAL != 0:
            continue

        # Check ground truth collisions (only every 10 steps — cheap guard)
        collision_vids: set = set()
        if step % 10 == 0:
            try:
                collisions = traci.simulation.getCollisions()
                collision_vids = {c.collider for c in collisions} | {c.victim for c in collisions}
            except Exception:
                pass

        # 1. Subscribe new vehicles as they depart
        departed = traci.simulation.getDepartedIDList()
        for vid in departed:
            traci.vehicle.subscribe(vid, [
                tc.VAR_POSITION, tc.VAR_SPEED, tc.VAR_ACCELERATION,
                tc.VAR_ANGLE, tc.VAR_LENGTH, tc.VAR_WIDTH,
                tc.VAR_SIGNALS, tc.VAR_TYPE
            ])
            if vid.startswith('bsp_') or vid.startswith('cls_'):
                traci.vehicle.setSpeedMode(vid, 0)       # Ignore all speed safety checks
                traci.vehicle.setLaneChangeMode(vid, 0)  # Ignore all lane-change safety checks

        # 2. Get bulk data for all vehicles in ONE TraCI call
        sub_results = traci.vehicle.getAllSubscriptionResults()
        
        vids = list(sub_results.keys())
        n_active = len(vids)
        if not vids:
            continue

        # 3. Evict stale data
        arrived = traci.simulation.getArrivedIDList()
        for vid in arrived:
            GNSS_STATE.pop(vid, None)
            V_STATE_CACHE.pop(vid, None)
            if 'ego_ids' in locals() and isinstance(ego_ids, set):
                ego_ids.discard(vid)

        active_set = set(vids)
        for stale_vid in list(V_STATE_CACHE.keys()):
            if stale_vid not in active_set:
                del V_STATE_CACHE[stale_vid]
        for stale_vid in list(GNSS_STATE.keys()):
            if stale_vid not in active_set:
                del GNSS_STATE[stale_vid]
        for stale_vid in list(prev_h.keys()):
            if stale_vid not in active_set:
                del prev_h[stale_vid]
        for stale_vid in list(engines.keys()):
            if stale_vid not in active_set:
                del engines[stale_vid]
        # Evict stale GE channel pairs for departed vehicles
        active_set_for_channels = set(vids)
        stale_channel_keys = [
            k for k in list(channels.keys())
            if k[0] not in active_set_for_channels or k[1] not in active_set_for_channels
        ]
        for k in stale_channel_keys:
            del channels[k]

        # Collect ALL vehicle states mathematically
        states: Dict[str, Any] = {}
        for v, data in sub_results.items():
            s = get_state(v, step, prev_h, sub_data=data, sigma_gps=sigma_gps_val)
            if s is not None:
                states[v] = s

        if not states:
            continue

        # Build spatial grid
        grid: Dict[tuple, list] = {}
        for v, s in states.items():
            if s is None: continue
            cell = (int(s.x // COMM_RANGE), int(s.y // COMM_RANGE))
            grid.setdefault(cell, []).append(v)

        # Filter to process only those with neighbors
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

        # -------------------------------------------------------------
        # DEMONSTRATION SCENARIO INJECTION
        # -------------------------------------------------------------
        # Inject tactical scenarios (Side-by-side, Overtaking, Cutting)
        scenario_injector.inject_blind_spot_scenario(step, net, traci)
        # Force interactions between vehicles to maintain dangerous behaviors
        scenario_injector.force_vehicle_interactions(step, net, traci)

        # ── Per-vehicle BSD processing ──
        step_vehs: Dict[str, Any] = {}
        step_caution = int(0)
        step_warning = int(0)
        step_critical = int(0)

        # Accumulate AI feature rows for batch inference (much faster than per-vehicle)
        ai_batch_keys: list = []   # ego_vid, in order
        ai_batch_rows: list = []   # feature dicts
        interim_results: list = [] # (ego_vid, bsd_result, ego_state, target_details_extra)

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
            
            # Filter: within range + bounding box heuristic + packet loss
            neighbors: Dict[str, Any] = {}
            received = set()
            for tv in candidates:
                if tv == ego_vid:
                    continue
                ts = states.get(tv)
                if ts is None:
                    continue
                
                # Fast distance squared check
                dsq = (ego.x - ts.x)**2 + (ego.y - ts.y)**2
                if dsq <= COMM_RANGE**2:
                    neighbors[tv] = ts
                    
                    # Bounding box heuristic: Ignore vehicles >40m ahead/behind or >12m lateral
                    # (Cheaper than transforming every vehicle to ego frame inside BSDEngine)
                    if dsq > 1600: # Fast pre-check: if distance > 40m, definitely outside blind spot
                        continue
                        
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

            # ── CAP neighbors to N closest to prevent O(N²) explosion ──
            if len(neighbors) > MAX_TARGETS_PER_EGO:
                neighbors = dict(
                    sorted(neighbors.items(),
                           key=lambda kv: (ego.x - kv[1].x)**2 + (ego.y - kv[1].y)**2
                    )[:MAX_TARGETS_PER_EGO]
                )
                received = received & set(neighbors.keys())

            # Run BSD engine (only instantiating if needed)
            if ego_vid not in engines:
                engines[ego_vid] = BSDEngine(
                    alpha=args.alpha, beta=args.beta, gamma=args.gamma,
                    use_lateral_ttc=not args.no_lat_ttc,
                    sigma_gps=args.sigma_gps, ttc_crit=args.ttc_crit, theta_3=args.theta_3
                )
            result = engines[ego_vid].process_step(ego, neighbors, received)
            
            # Run Baseline BSD
            base_result = baseline_bsd.check(ego, neighbors, engines[ego_vid])

            al = result['alert_left']
            ar = result['alert_right']
            
            # Color update — skip in headless (--no-gui) mode. 
            # To maintain the "High Playback Speed" visual effect, we only paint vehicles every 5 steps
            # (TCP coloring calls are the main cause of GUI lag, not the Python math engine!)
            if use_gui and (step % 5 == 0):
                key = f"{al}_{ar}"
                if last_colors.get(ego_vid) != key:
                    try:
                        traci.vehicle.setColor(ego_vid, alert_color(al, ar))
                        last_colors[ego_vid] = key
                    except:
                        pass

            # Count alerts
            if al == 'SAFE' and ar == 'SAFE':
                cum_safe += 1
            elif al == 'CRITICAL' or ar == 'CRITICAL':
                step_critical += 1
                cum_critical += 1
            elif al == 'WARNING' or ar == 'WARNING':
                step_warning += 1
                cum_warning += 1
            else:
                step_caution += 1
                cum_caution += 1

            # Track successful communication for V2V visualization
            if received:
                for target_vid in received:
                    live['comm_links'].append({'ego': ego_vid, 'target': target_vid})

            # AI prediction — accumulate features for batch inference
            target_details = result.get('target_details', [])
            max_gap  = min([t.get('d_gap', 100.0) for t in target_details]) if target_details else 100.0
            max_plr  = max([t.get('plr', 0.0)    for t in target_details]) if target_details else 0.0

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

            # Collect for batch prediction
            ai_batch_keys.append(ego_vid)
            ai_batch_rows.append({
                'speed': ego.speed, 'accel': ego.accel, 'yaw_rate': ego.yaw_rate,
                'num_targets': result['num_targets'],
                'signals': ego.signals,
                'max_gap': max_gap, 'rel_speed': rel_speed,
                'max_plr': max_plr, 'k_lost_max': k_lost_max,
                'speed_kmh': ego.speed * 3.6,
                'abs_accel': abs(ego.accel), 'abs_yaw_rate': abs(ego.yaw_rate),
                'is_braking': 1 if ego.accel < -1.0 else 0,
                'is_signaling': 1 if ego.signals > 0 else 0,
                'has_targets': 1 if result['num_targets'] > 0 else 0,
                'speed_category': 0 if ego.speed < 5 else (1 if ego.speed < 20 else 2),
                'closing_speed': rel_speed,
                'target_angle': target_angle,
            })
            # Store intermediate per-vehicle data for metrics assembly
            interim_results.append((ego_vid, result, ego, target_details, max_gap, rel_speed, max_plr, k_lost_max, al, ar, base_result, target_angle))


        # ── Batch AI prediction (one XGBoost call for all vehicles) ──
        ai_results_map: Dict[str, Any] = {}
        if has_ai and ai_batch_rows:
            batch_out = ai.batch_predict(ai_batch_rows)
            for k, v in zip(ai_batch_keys, batch_out):
                ai_results_map[k] = v

        # ── Assemble metrics and live data from interim results ──
        log_this_step = (step % (BSD_INTERVAL * 2) == 0)
        for (ego_vid, result, ego, target_details, max_gap, rel_speed, max_plr, k_lost_max, al, ar, base_result, target_angle) in interim_results:
            ai_result = ai_results_map.get(ego_vid, {'ai_alert': 'N/A', 'ai_confidence': 0.0, 'ai_critical_prob': 0.0})

            sorted_details = sorted(target_details, key=lambda x: x['cri'], reverse=True)
            target_left  = next((t for t in sorted_details if t['side'] == 'LEFT'),  None)
            target_right = next((t for t in sorted_details if t['side'] == 'RIGHT'), None)

            if log_this_step:
                metrics_log.append({
                    'step': step, 'ego_vid': ego_vid,
                    'x': ego.x, 'y': ego.y,
                    'speed': ego.speed, 'accel': ego.accel,
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
                    'P_right':        target_right['P']              if target_right else 0.0,
                    'R_decel_right':  target_right['R_decel']        if target_right else 0.0,
                    'R_ttc_right':    target_right['R_ttc']          if target_right else 0.0,
                    'R_intent_right': target_right['R_intent']       if target_right else 0.0,
                    'plr_mult_right': target_right['plr_multiplier'] if target_right else 1.0,
                    'alert_left': al, 'alert_right': ar,
                    'baseline_left':  base_result['alert_left'],
                    'baseline_right': base_result['alert_right'],
                    'static_left':    base_result['static_left'],
                    'static_right':   base_result['static_right'],
                    'ground_truth_collision': 1 if ego_vid in collision_vids else 0,
                    'num_targets': result['num_targets'],
                    'signals': ego.signals,
                    'ai_alert':        ai_result.get('ai_alert', 'N/A'),
                    'ai_confidence':   ai_result.get('ai_confidence', 0.0),
                    'ai_critical_prob': ai_result.get('ai_critical_prob', 0.0),
                })

            # Log non-SAFE alerts
            if al != 'SAFE' or ar != 'SAFE':
                alerts_log.append({
                    'step': step, 'ego_vid': ego_vid,
                    'cri_left': result['cri_left'], 'cri_right': result['cri_right'],
                    'alert_left': al, 'alert_right': ar,
                    'top_threat': result['target_details'][0]['target_vid'] if result['target_details'] else '',
                    'top_cri': max(result['cri_left'], result['cri_right']),
                })

            # Live data for dashboard (top 200 for 'WOW' factor)
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
                         'R_ttc_lon': round(float(t.get('R_ttc_lon', 0.0)), 4), 'R_ttc_lat': round(float(t.get('R_ttc_lat', 0.0)), 4),
                         'R_intent': round(float(t['R_intent']), 4),
                         'd_gap': round(float(t['d_gap']), 2), 'plr': round(float(t['plr']), 3)}
                        for t in tops
                    ]
                }
        live['step'] = step
        live['vehicles'] = step_vehs
        live['active_count'] = n_active
        # Keep only the most recent links
        live['comm_links'] = live['comm_links'][-200:] if len(live['comm_links']) > 200 else live['comm_links']
        live['alert_counts'] = {
            'safe': cum_safe, 'caution': cum_caution,
            'warning': cum_warning, 'critical': cum_critical
        }
        live['total_alerts_logged'] = len(alerts_log)
        live['elapsed'] = float(round(float(time.time() - t0), 1))
        
        live['params'] = {'ALPHA': Params.ALPHA, 'BETA': Params.BETA, 'GAMMA': Params.GAMMA, 'THETA_3': Params.THETA_3}
        
        # Write live JSON every 25 steps (2.5s real-world intervals)
        if step % 25 == 0:
            try:
                _tmp = LIVE_FILE + '.tmp'
                with open(_tmp, 'w') as f:
                    json.dump(live, f)
                os.replace(_tmp, LIVE_FILE)
            except Exception as e:
                pass   # Non-critical: dashboard will use last good state

        # Save CSVs every 500 steps
        if step % 500 == 0 and step > 0:
            if metrics_log:
                pd.DataFrame(metrics_log).to_csv(METRICS_FILE, index=False)
            if alerts_log:
                pd.DataFrame(alerts_log).to_csv(ALERTS_FILE, index=False)

        # Cleanup stale trackers every 50 steps (balance between ghost-tracker
        # accumulation and per-step overhead of iterating all engines)
        if step % 50 == 0 and step > 0:
            for eng in engines.values():
                eng.cleanup_stale_trackers(max_stale_steps=15)

        # Progress report every 100 steps
        if step % 100 == 0:
            elapsed = float(time.time() - t0)
            eta = float((elapsed / max(step, 1)) * (max_steps - step))
            alerted = step_caution + step_warning + step_critical
            print(f"  Step {step:>5}/{max_steps} | "
                  f"Active: {n_active:>3} | BSD: {len(ego_ids):>3} | "
                  f"Alerts: {alerted:>2} (C:{step_caution} W:{step_warning} X:{step_critical}) | "
                  f"{elapsed:.0f}s (ETA {eta:.0f}s)")
            print(f"  Step {step}: channels dict size = {len(channels)}")



    # ============================================================
    # FINAL
    # ============================================================
    traci.close()
    elapsed = float(time.time() - t0)

    # Final save
    if metrics_log:
        pd.DataFrame(metrics_log).to_csv(METRICS_FILE, index=False)
    if alerts_log:
        pd.DataFrame(alerts_log).to_csv(ALERTS_FILE, index=False)
    
    # Final live data
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

    print("=" * 70)
    print(">>> Run: streamlit run dashboard.py")
    print("=" * 70)


if __name__ == "__main__":
    main()
