"""
V2V Blind Spot Detection — SUMO Simulation Runner
===================================================
Connects SUMO simulator via TraCI to the V2.4 BSD mathematical model engine.
Processes all vehicles, computes CRI per ego vehicle, and logs data for dashboard.
Includes: Scenario Injector + AI Model Hybrid Prediction.

Usage:
    python v2v_bsd_simulation.py [--gui] [--steps N] [--ego VID]
"""

import os
import sys
import json
import time
import argparse
import numpy as np
import pandas as pd
import random
import traci
import sumolib
from pathlib import Path
from collections import defaultdict

from bsd_engine import BSDEngine, VehicleState, Params, AlertLevel
from scenario_injector import inject_blind_spot_scenario, force_vehicle_interactions
from train_ai_model import BSDPredictor


# ============================================================
# CONFIGURATION
# ============================================================
SUMO_CFG     = "../Maps/atal_v2v.sumocfg"
NET_FILE     = "../Maps/atal.net.xml"
OUTPUT_DIR   = "../Outputs"
METRICS_FILE = os.path.join(OUTPUT_DIR, "bsd_metrics.csv")
ALERTS_FILE  = os.path.join(OUTPUT_DIR, "bsd_alerts.csv")
DETAILS_FILE = os.path.join(OUTPUT_DIR, "bsd_details.json")
LIVE_FILE    = os.path.join(OUTPUT_DIR, "bsd_live.json")

# How often to process BSD (every N simulation steps)
# With 0.1s step and BSM at 10 Hz → process every step
BSD_INTERVAL = 1

# Communication range for BSM reception
COMM_RANGE   = Params.R_COMM   # 300m

# Simulated packet loss probability
PACKET_DROP_PROB = 0.05

# Default vehicle parameters (when SUMO doesn't provide them)
DEFAULT_LENGTH  = 4.5
DEFAULT_WIDTH   = 1.8
DEFAULT_MASS    = 1800.0
DEFAULT_MU      = 0.7


def parse_args():
    parser = argparse.ArgumentParser(description="V2V BSD SUMO Simulation")
    parser.add_argument("--gui", action="store_true", default=True, help="Use SUMO-GUI")
    parser.add_argument("--no-gui", action="store_true", help="Use headless SUMO")
    parser.add_argument("--steps", type=int, default=3600, help="Max simulation steps")
    parser.add_argument("--ego", type=str, default=None, help="Specific ego vehicle ID (default: all)")
    return parser.parse_args()


def heading_from_sumo_angle(sumo_angle_deg: float) -> float:
    """
    Convert SUMO angle (degrees CW from North) to math convention (radians CCW from +X).
    θ_math = π/2 − θ_SUMO · π/180
    """
    return np.pi / 2.0 - sumo_angle_deg * np.pi / 180.0


def get_vehicle_state(vid: str, step: int, prev_headings: dict) -> VehicleState:
    """Extract full vehicle state from SUMO via TraCI."""
    try:
        pos = traci.vehicle.getPosition(vid)
        speed = traci.vehicle.getSpeed(vid)
        accel = traci.vehicle.getAcceleration(vid)
        sumo_angle = traci.vehicle.getAngle(vid)
        heading = heading_from_sumo_angle(sumo_angle)
        length = traci.vehicle.getLength(vid)
        width = traci.vehicle.getWidth(vid)
        signals = traci.vehicle.getSignals(vid)
        
        # Yaw rate: Δθ/Δt from consecutive headings
        yaw_rate = 0.0
        if vid in prev_headings:
            delta_theta = heading - prev_headings[vid]
            # Normalize to [-π, π]
            delta_theta = (delta_theta + np.pi) % (2 * np.pi) - np.pi
            yaw_rate = delta_theta / Params.DT
        prev_headings[vid] = heading

        # Mass: try SUMO parameter, fallback to default
        try:
            mass = float(traci.vehicle.getParameter(vid, "mass"))
        except (traci.exceptions.TraCIException, ValueError):
            mass = DEFAULT_MASS

        # Vehicle type classification
        vtype = traci.vehicle.getTypeID(vid)
        if 'truck' in vtype.lower() or 'trailer' in vtype.lower():
            vehicle_type = 'truck'
        elif 'suv' in vtype.lower() or 'bus' in vtype.lower():
            vehicle_type = 'suv'
        else:
            vehicle_type = 'sedan'

        return VehicleState(
            vid=vid,
            x=pos[0], y=pos[1],
            speed=max(0, speed),
            accel=accel,
            heading=heading,
            yaw_rate=yaw_rate,
            length=length if length > 0 else DEFAULT_LENGTH,
            width=width if width > 0 else DEFAULT_WIDTH,
            mass=mass,
            mu=DEFAULT_MU,
            signals=signals,
            vehicle_type=vehicle_type,
            timestamp=step,
        )
    except traci.exceptions.TraCIException:
        return None


def color_for_alert(alert_left: str, alert_right: str) -> tuple:
    """Pick vehicle color based on highest alert level."""
    levels = {'SAFE': 0, 'CAUTION': 1, 'WARNING': 2, 'CRITICAL': 3}
    max_level = max(levels.get(alert_left, 0), levels.get(alert_right, 0))
    
    colors = {
        0: (0, 200, 0, 255),      # Green — SAFE
        1: (255, 200, 0, 255),     # Yellow — CAUTION
        2: (255, 100, 0, 255),     # Orange — WARNING
        3: (255, 0, 0, 255),       # Red — CRITICAL
    }
    return colors.get(max_level, (128, 128, 128, 255))


def main():
    args = parse_args()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ============================================================
    # START SUMO
    # ============================================================
    sumo_binary = "sumo-gui" if args.gui and not args.no_gui else "sumo"
    sumo_cmd = [sumo_binary, "-c", SUMO_CFG, "--start"]

    print("=" * 70)
    print("🚗 V2V Blind Spot Detection — SUMO Simulation")
    print("   Mathematical Model V2.4 Implementation")
    print("=" * 70)
    print(f"   Binary:     {sumo_binary}")
    print(f"   Config:     {SUMO_CFG}")
    print(f"   Max Steps:  {args.steps}")
    print(f"   Comm Range: {COMM_RANGE}m")
    print(f"   PKT Drop:   {PACKET_DROP_PROB*100:.0f}%")
    print("=" * 70)

    traci.start(sumo_cmd)
    print("✅ SUMO started successfully!")

    # ============================================================
    # LOAD NETWORK & AI MODEL
    # ============================================================
    net = sumolib.net.readNet(NET_FILE)
    print(f"📡 Network loaded: {len(net.getEdges())} edges")

    ai_predictor = BSDPredictor()
    has_ai = ai_predictor.model is not None

    # ============================================================
    # INITIALIZE BSD ENGINES (one per ego vehicle)
    # ============================================================
    engines: dict[str, BSDEngine] = {}
    prev_headings: dict[str, float] = {}
    scenario_log = []

    # Logging
    metrics_log = []
    alerts_log = []
    live_data = {
        'step': 0,
        'vehicles': {},
        'has_ai': has_ai,
        'params': {
            'L_base': Params.L_BASE, 'lambda': Params.LAMBDA_SCALE,
            'W_lane': Params.W_LANE, 'sigma_gps': Params.SIGMA_GPS,
            'alpha': Params.ALPHA, 'beta': Params.BETA, 'gamma': Params.GAMMA,
            'theta1': Params.THETA_1, 'theta2': Params.THETA_2, 'theta3': Params.THETA_3,
            'R_comm': Params.R_COMM, 'F_BSM': Params.F_BSM,
            'pkt_drop': PACKET_DROP_PROB, 'epsilon_PLR': Params.EPSILON,
        }
    }

    max_steps = args.steps
    start_time = time.time()

    # ============================================================
    # SIMULATION LOOP
    # ============================================================
    print("🔄 Running simulation...")
    
    for step in range(max_steps):
        traci.simulationStep()

        # Inject blind spot test scenarios periodically
        injected = inject_blind_spot_scenario(step, net)
        if injected:
            scenario_log.extend(injected)

        # Force vehicle interactions for scenario vehicles
        force_vehicle_interactions(step)

        if step % BSD_INTERVAL != 0:
            continue

        vehicle_ids = list(traci.vehicle.getIDList())
        if not vehicle_ids:
            continue

        # Filter to specific ego if requested
        ego_ids = [args.ego] if args.ego and args.ego in vehicle_ids else vehicle_ids

        # Collect all vehicle states
        all_states: dict[str, VehicleState] = {}
        for vid in vehicle_ids:
            state = get_vehicle_state(vid, step, prev_headings)
            if state is not None:
                all_states[vid] = state

        if not all_states:
            continue

        # 🚀 OPTIMIZATION: Spatial Grid for V2V range detection
        # Group vehicles by 300m grid cells to avoid O(N^2) checks
        grid: dict[tuple[int, int], list[str]] = {}
        grid_size = Params.R_COMM # 300m
        for vid, state in all_states.items():
            cell = (int(state.x // grid_size), int(state.y // grid_size))
            if cell not in grid: grid[cell] = []
            grid[cell].append(vid)

        # Per-vehicle live data for this step
        step_vehicles = {}
        last_alerts = {} # To reduce setColor TraCI overhead

        # Process each ego vehicle
        for ego_vid in ego_ids:
            if ego_vid not in all_states:
                continue

            ego_state = all_states[ego_vid]
            
            # Find neighbors in communication range using grid
            ego_cell = (int(ego_state.x // grid_size), int(ego_state.y // grid_size))
            candidate_vids = []
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    neighbor_cell = (ego_cell[0] + dx, ego_cell[1] + dy)
                    if neighbor_cell in grid:
                        candidate_vids.extend(grid[neighbor_cell])
            
            # 🚀 SPEED OPTIMIZATION: Skip BSD processing if no nearby vehicles
            if len(candidate_vids) <= 1: # Only self is in grid
                if ego_vid in engines:
                    # Maintain tracker state but skip heavy math
                    engines[ego_vid].process_step(ego_state, {}, set())
                continue

            # Filter targets to communication range and packet loss
            neighbor_states = {}
            received_vids = set()
            
            for t_vid in candidate_vids:
                if t_vid == ego_vid:
                    continue
                
                t_state = all_states[t_vid]
                dist_sq = (ego_state.x - t_state.x)**2 + (ego_state.y - t_state.y)**2
                if dist_sq <= grid_size**2:
                    neighbor_states[t_vid] = t_state
                    if np.random.random() > PACKET_DROP_PROB:
                        received_vids.add(t_vid)

            # Run BSD Engine
            if ego_vid not in engines:
                engines[ego_vid] = BSDEngine()
            
            result = engines[ego_vid].process_step(ego_state, neighbor_states, received_vids)

            # 🚀 SPEED OPTIMIZATION: Only setColor if alert state changed
            alert_key = f"{result['alert_left']}_{result['alert_right']}"
            if last_alerts.get(ego_vid) != alert_key:
                try:
                    alert_color = color_for_alert(result['alert_left'], result['alert_right'])
                    traci.vehicle.setColor(ego_vid, alert_color)
                    last_alerts[ego_vid] = alert_key
                except:
                    pass

            # AI prediction (hybrid)
            ai_result = {'ai_alert': 'N/A', 'ai_confidence': 0.0}
            if has_ai:
                ai_result = ai_predictor.predict(
                    speed=ego_state.speed, accel=ego_state.accel,
                    yaw_rate=ego_state.yaw_rate, num_targets=result['num_targets'],
                    cri_left=result['cri_left'], cri_right=result['cri_right'],
                    signals=ego_state.signals,
                )

            # Log metrics
            metrics_log.append({
                'step': step,
                'ego_vid': ego_vid,
                'x': ego_state.x,
                'y': ego_state.y,
                'speed': ego_state.speed,
                'accel': ego_state.accel,
                'heading_deg': np.degrees(ego_state.heading),
                'yaw_rate': ego_state.yaw_rate,
                'cri_left': result['cri_left'],
                'cri_right': result['cri_right'],
                'alert_left': result['alert_left'],
                'alert_right': result['alert_right'],
                'num_targets': result['num_targets'],
                'signals': ego_state.signals,
                'ai_alert': ai_result.get('ai_alert', 'N/A'),
                'ai_confidence': ai_result.get('ai_confidence', 0.0),
            })

            # Log alerts
            if result['alert_left'] != 'SAFE' or result['alert_right'] != 'SAFE':
                alerts_log.append({
                    'step': step,
                    'ego_vid': ego_vid,
                    'cri_left': result['cri_left'],
                    'cri_right': result['cri_right'],
                    'alert_left': result['alert_left'],
                    'alert_right': result['alert_right'],
                    'top_threat': result['target_details'][0]['target_vid'] if result['target_details'] else 'none',
                    'top_cri': max(result['cri_left'], result['cri_right']),
                })

            # Live data for dashboard
            top_targets = sorted(result['target_details'], key=lambda t: t['cri'], reverse=True)[:3]
            step_vehicles[ego_vid] = {
                'x': ego_state.x, 'y': ego_state.y,
                'speed': round(ego_state.speed, 2),
                'cri_left': round(result['cri_left'], 4),
                'cri_right': round(result['cri_right'], 4),
                'alert_left': result['alert_left'],
                'alert_right': result['alert_right'],
                'ai_alert': ai_result.get('ai_alert', 'N/A'),
                'ai_confidence': round(ai_result.get('ai_confidence', 0.0), 3),
                'num_targets': result['num_targets'],
                'top_threats': [
                    {
                        'vid': t['target_vid'],
                        'cri': round(t['cri'], 4),
                        'side': t['side'],
                        'P': round(t['P'], 4),
                        'R_decel': round(t['R_decel'], 4),
                        'R_ttc': round(t['R_ttc'], 4),
                        'R_intent': round(t['R_intent'], 4),
                        'd_gap': round(t['d_gap'], 2),
                        'plr': round(t['plr'], 3),
                    }
                    for t in top_targets
                ]
            }

        # Update live data
        live_data['step'] = step
        live_data['vehicles'] = step_vehicles
        live_data['active_count'] = len(vehicle_ids)
        live_data['alert_counts'] = {
            'safe': sum(1 for v in step_vehicles.values() if v['alert_left'] == 'SAFE' and v['alert_right'] == 'SAFE'),
            'caution': sum(1 for v in step_vehicles.values() if 'CAUTION' in [v['alert_left'], v['alert_right']]),
            'warning': sum(1 for v in step_vehicles.values() if 'WARNING' in [v['alert_left'], v['alert_right']]),
            'critical': sum(1 for v in step_vehicles.values() if 'CRITICAL' in [v['alert_left'], v['alert_right']]),
        }

        # Write live data periodically
        if step % 10 == 0:
            try:
                with open(LIVE_FILE, 'w') as f:
                    json.dump(live_data, f)
            except Exception:
                pass

        # Save CSVs periodically
        if step % 100 == 0 and step > 0:
            if metrics_log:
                pd.DataFrame(metrics_log).to_csv(METRICS_FILE, index=False)
            if alerts_log:
                pd.DataFrame(alerts_log).to_csv(ALERTS_FILE, index=False)

            elapsed = time.time() - start_time
            alerted = sum(1 for v in step_vehicles.values() 
                         if v['alert_left'] != 'SAFE' or v['alert_right'] != 'SAFE')
            print(f"  📊 Step {step:>5}/{max_steps} | "
                  f"Active: {len(vehicle_ids):>3} | "
                  f"Alerted: {alerted:>3} | "
                  f"Elapsed: {elapsed:.1f}s")

        # Cleanup stale trackers periodically
        if step % 500 == 0:
            for engine in engines.values():
                engine.cleanup_stale_trackers()
            # Remove engines for departed vehicles
            active = set(vehicle_ids)
            to_remove = [vid for vid in engines if vid not in active]
            for vid in to_remove:
                del engines[vid]

    # ============================================================
    # CLEANUP & FINAL REPORT
    # ============================================================
    traci.close()

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("🏁 Simulation Complete!")
    print(f"   Total Steps:    {max_steps}")
    print(f"   Elapsed Time:   {elapsed:.1f}s")
    print(f"   Metrics Logged: {len(metrics_log)}")
    print(f"   Alerts Logged:  {len(alerts_log)}")

    # Final save
    if metrics_log:
        df_metrics = pd.DataFrame(metrics_log)
        df_metrics.to_csv(METRICS_FILE, index=False)
        print(f"   📄 Metrics saved to {METRICS_FILE}")

        # Summary stats
        print(f"\n   ─── Alert Distribution ───")
        for side in ['left', 'right']:
            col = f'alert_{side}'
            counts = df_metrics[col].value_counts()
            print(f"   {side.upper()}: {dict(counts)}")

    if alerts_log:
        pd.DataFrame(alerts_log).to_csv(ALERTS_FILE, index=False)
        print(f"   📄 Alerts saved to {ALERTS_FILE}")

    if scenario_log:
        print(f"   🎬 Scenarios injected: {len(scenario_log)}")

    print("\n" + "=" * 70)
    print("✅ V2V BSD Simulation Complete!")
    print("📌 Next: Run 'streamlit run dashboard.py' to view the dashboard")
    print("=" * 70)


if __name__ == "__main__":
    main()
