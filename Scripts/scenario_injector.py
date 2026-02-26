"""
V2V BSD — High-Intensity Scenario Injector (PRO VERSION)
==========================================================
Creates "Heart-Attack" level dangerous situations for researchers.
- Forces vehicles into blind spots with speed differentials.
- Disables TraCI safety checks to allow "suicidal" lane changes.
- Spawns erratic vehicles that brake suddenly in blind spots.
"""

import numpy as np
import sumolib
from typing import List, Tuple

# We import traci inside functions to prevent Libsumo/TraCI startup conflicts
# and allow the main script to decide the implementation.

# Scenario counter
_scenario_counter = 0

def _next_id() -> str:
    global _scenario_counter
    _scenario_counter += 1
    return f"bsd_demo_{_scenario_counter}"

def _safe_add_vehicle(traci, vid: str, route_id: str, edge: str, lane: int, 
                       pos: float, speed: float, vtype: str = "sedan") -> bool:
    try:
        try:
            traci.route.add(route_id, [edge])
        except: pass
        
        traci.vehicle.add(vid, route_id, departLane=str(lane), 
                         departPos=str(max(0, pos)), departSpeed=str(max(1, speed)),
                         typeID=vtype)
        # DISABLE SAFETY FOR DEMO VEHICLES (Allow risky behavior)
        traci.vehicle.setSpeedMode(vid, 0)
        traci.vehicle.setLaneChangeMode(vid, 0)
        return True
    except: return False

def _get_random_multilane_edge(net) -> Tuple[str, int]:
    edges = [e for e in net.getEdges() if e.getLaneNumber() >= 2 and e.getLength() > 100]
    if not edges: return None, 0
    e = np.random.choice(edges)
    return e.getID(), e.getLaneNumber()

def inject_blind_spot_scenario(step: int, net, traci):
    if step % 80 != 0: return # Every 8 seconds
    
    edge_id, nlanes = _get_random_multilane_edge(net)
    if not edge_id: return
    
    edge = net.getEdge(edge_id)
    pos = edge.getLength() * 0.2
    
    # Randomly pick a "Critical" or "Warning" scenario
    scenario_type = np.random.choice([
        "FAST_OVERTAKE", 
        "LANE_CHANGE_CUT", 
        "SUDDEN_BRAKE_BS", 
        "BLIND_DRIFT"
    ])
    
    vid_ego = _next_id()
    vid_tgt = _next_id()
    
    if scenario_type == "FAST_OVERTAKE":
        # Ego is cruising, target zooms from behind into blind spot
        _safe_add_vehicle(traci, vid_ego, f"r_{vid_ego}", edge_id, 0, pos + 50, 15.0)
        _safe_add_vehicle(traci, vid_tgt, f"r_{vid_tgt}", edge_id, 1, pos, 30.0)
        traci.vehicle.setColor(vid_tgt, (255, 0, 0, 255)) # Red = Hazard
        
    elif scenario_type == "LANE_CHANGE_CUT":
        # Target cut directly into ego's path/blind spot
        _safe_add_vehicle(traci, vid_ego, f"r_{vid_ego}", edge_id, 1, pos + 20, 20.0)
        _safe_add_vehicle(traci, vid_tgt, f"r_{vid_tgt}", edge_id, 0, pos + 10, 22.0)
        traci.vehicle.changeLane(vid_tgt, 1, 2.0) # Move toward ego
        traci.vehicle.setSignals(vid_tgt, 2) # Left blinker
        
    elif scenario_type == "SUDDEN_BRAKE_BS":
        # Target in blind spot suddenly slams brakes
        _safe_add_vehicle(traci, vid_ego, f"r_{vid_ego}", edge_id, 0, pos + 40, 25.0)
        _safe_add_vehicle(traci, vid_tgt, f"r_{vid_tgt}", edge_id, 1, pos + 35, 25.0)
        # We'll handle the brake in force_vehicle_interactions
        traci.vehicle.setParameter(vid_tgt, "bsd_role", "braker")
        
    elif scenario_type == "BLIND_DRIFT":
        # Ego drifts into target in blind spot
        _safe_add_vehicle(traci, vid_ego, f"r_{vid_ego}", edge_id, 0, pos + 30, 20.0)
        _safe_add_vehicle(traci, vid_tgt, f"r_{vid_tgt}", edge_id, 1, pos + 28, 20.0)
        traci.vehicle.setSignals(vid_ego, 1) # Right blinker
        traci.vehicle.changeLane(vid_ego, 1, 5.0) # Drift into target

def force_vehicle_interactions(step: int, net, traci):
    vids = traci.vehicle.getIDList()
    for vid in vids:
        if not vid.startswith("bsd_demo_"): continue
        
        # Part 1: Handle erratic braking
        if traci.vehicle.getParameter(vid, "bsd_role") == "braker":
            if step % 20 == 0:
                traci.vehicle.setSpeed(vid, 5.0) # Slam brakes
            elif step % 40 == 0:
                traci.vehicle.setSpeed(vid, 25.0) # speed up again
                
        # Part 2: Sudden speed variations to keep CRI dynamic
        if step % 50 == 0:
            s = traci.vehicle.getSpeed(vid)
            traci.vehicle.setSpeed(vid, max(5, s + np.random.uniform(-10, 10)))

    # Part 3: Randomly force lane changes for NON-DEMO vehicles too
    # This makes the "Saturation" traffic also dangerous
    if step % 100 == 0 and vids:
        lucky_vid = np.random.choice(vids)
        try:
            nlanes = net.getEdge(traci.vehicle.getRoadID(lucky_vid)).getLaneNumber()
            if nlanes >= 2:
                curr = traci.vehicle.getLaneIndex(lucky_vid)
                target = 1 - curr if nlanes == 2 else np.random.choice([l for l in range(nlanes) if l != curr])
                traci.vehicle.changeLane(lucky_vid, target, 2.0)
        except: pass
