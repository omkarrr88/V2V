"""
V2V BSD — Scenario Injector System (V3.0)
==========================================
Three injector subsystems:
1. Original demo injector — Forces blind-spot-specific dangerous situations
2. TSVInjector — Traffic Signal Violation scenarios (§9.1)
3. HNRInjector — Hilly Narrow Road scenarios (§9.2)
"""

import numpy as np
import sumolib
from typing import List, Tuple

# We import traci inside functions to prevent Libsumo/TraCI startup conflicts

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
        except Exception:
            pass  # Route may already exist — expected
        
        traci.vehicle.add(vid, route_id, departLane=str(lane), 
                         departPos=str(max(0, pos)), departSpeed=str(max(1, speed)),
                         typeID=vtype)
        traci.vehicle.setSpeedMode(vid, 0)
        traci.vehicle.setLaneChangeMode(vid, 0)
        return True
    except Exception as e:
        # TraCI calls can legitimately fail when vehicles depart mid-step
        if not any(s in str(e) for s in ['Vehicle', 'not found', 'departed', 'already exists']):
            print(f"[WARN] Scenario injector: {type(e).__name__}: {e}")
        return False

def _get_random_multilane_edge(net) -> Tuple[str, int]:
    edges = [e for e in net.getEdges() if e.getLaneNumber() >= 2 and e.getLength() > 100]
    if not edges: return None, 0
    e = np.random.choice(edges)
    return e.getID(), e.getLaneNumber()


# ============================================================
# ORIGINAL DEMO INJECTOR (kept intact)
# ============================================================
def inject_blind_spot_scenario(step: int, net, traci):
    if step % 80 != 0: return
    
    edge_id, nlanes = _get_random_multilane_edge(net)
    if not edge_id: return
    
    edge = net.getEdge(edge_id)
    pos = edge.getLength() * 0.2
    
    scenario_type = np.random.choice([
        "FAST_OVERTAKE", 
        "LANE_CHANGE_CUT", 
        "SUDDEN_BRAKE_BS", 
        "BLIND_DRIFT"
    ])
    
    vid_ego = _next_id()
    vid_tgt = _next_id()
    
    if scenario_type == "FAST_OVERTAKE":
        _safe_add_vehicle(traci, vid_ego, f"r_{vid_ego}", edge_id, 0, pos + 50, 15.0)
        _safe_add_vehicle(traci, vid_tgt, f"r_{vid_tgt}", edge_id, 1, pos, 30.0)
        traci.vehicle.setColor(vid_tgt, (255, 0, 0, 255))
        
    elif scenario_type == "LANE_CHANGE_CUT":
        _safe_add_vehicle(traci, vid_ego, f"r_{vid_ego}", edge_id, 1, pos + 20, 20.0)
        _safe_add_vehicle(traci, vid_tgt, f"r_{vid_tgt}", edge_id, 0, pos + 10, 22.0)
        traci.vehicle.changeLane(vid_tgt, 1, 2.0)
        traci.vehicle.setSignals(vid_tgt, 2)
        
    elif scenario_type == "SUDDEN_BRAKE_BS":
        _safe_add_vehicle(traci, vid_ego, f"r_{vid_ego}", edge_id, 0, pos + 40, 25.0)
        _safe_add_vehicle(traci, vid_tgt, f"r_{vid_tgt}", edge_id, 1, pos + 35, 25.0)
        traci.vehicle.setParameter(vid_tgt, "bsd_role", "braker")
        
    elif scenario_type == "BLIND_DRIFT":
        _safe_add_vehicle(traci, vid_ego, f"r_{vid_ego}", edge_id, 0, pos + 30, 20.0)
        _safe_add_vehicle(traci, vid_tgt, f"r_{vid_tgt}", edge_id, 1, pos + 28, 20.0)
        traci.vehicle.setSignals(vid_ego, 1)
        traci.vehicle.changeLane(vid_ego, 1, 5.0)

def force_vehicle_interactions(step: int, net, traci):
    vids = traci.vehicle.getIDList()
    for vid in vids:
        if not vid.startswith("bsd_demo_"): continue
        
        if traci.vehicle.getParameter(vid, "bsd_role") == "braker":
            if step % 20 == 0:
                traci.vehicle.setSpeed(vid, 5.0)
            elif step % 40 == 0:
                traci.vehicle.setSpeed(vid, 25.0)
                
        if step % 50 == 0:
            s = traci.vehicle.getSpeed(vid)
            traci.vehicle.setSpeed(vid, max(5, s + np.random.uniform(-10, 10)))

    if step % 100 == 0 and vids:
        lucky_vid = np.random.choice(vids)
        try:
            nlanes = net.getEdge(traci.vehicle.getRoadID(lucky_vid)).getLaneNumber()
            if nlanes >= 2:
                curr = traci.vehicle.getLaneIndex(lucky_vid)
                target = 1 - curr if nlanes == 2 else np.random.choice([l for l in range(nlanes) if l != curr])
                traci.vehicle.changeLane(lucky_vid, target, 2.0)
        except Exception: pass


# ============================================================
# TSV INJECTOR — Traffic Signal Violation (§9.1)
# ============================================================
class TSVInjector:
    """
    Monitors traffic lights and creates red-light-running violations.
    When a traffic light turns red, approaching vehicles within 50m
    have a 30% chance of being designated as violators.
    """
    
    def __init__(self, p_violator: float = 0.3, approach_distance: float = 50.0):
        self.p_violator = p_violator
        self.approach_distance = approach_distance
        self._active_violators = set()
        self._last_tl_states = {}

    def step(self, step: int, net, traci):
        """Check traffic lights and potentially inject violators."""
        try:
            tl_ids = traci.trafficlight.getIDList()
        except Exception:
            return

        for tl_id in tl_ids:
            try:
                state = traci.trafficlight.getRedYellowGreenState(tl_id)
                prev_state = self._last_tl_states.get(tl_id, '')
                self._last_tl_states[tl_id] = state

                # Detect transition to red phase
                if 'r' in state and 'r' not in prev_state:
                    self._inject_violators_at_tl(tl_id, net, traci)
            except Exception:
                continue

        # Clean up departed violators
        try:
            active_vids = set(traci.vehicle.getIDList())
            self._active_violators &= active_vids
        except Exception:
            pass

    def _inject_violators_at_tl(self, tl_id: str, net, traci):
        """Designate some approaching vehicles as red-light violators."""
        try:
            controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
            controlled_edges = set()
            for lane_id in controlled_lanes:
                edge_id = lane_id.rsplit('_', 1)[0]
                controlled_edges.add(edge_id)
        except Exception:
            return

        try:
            vids = traci.vehicle.getIDList()
        except Exception:
            return

        for vid in vids:
            if vid in self._active_violators:
                continue
            try:
                road = traci.vehicle.getRoadID(vid)
                if road not in controlled_edges:
                    continue
                
                # Check if within approach distance of stop line
                lane_pos = traci.vehicle.getLanePosition(vid)
                lane_id = traci.vehicle.getLaneID(vid)
                try:
                    lane_length = net.getLane(lane_id).getLength()
                except Exception:
                    lane_length = 200.0
                
                dist_to_end = lane_length - lane_pos
                if dist_to_end > self.approach_distance:
                    continue
                
                # Randomly designate as violator
                if np.random.random() < self.p_violator:
                    speed = traci.vehicle.getSpeed(vid)
                    if speed > 2.0:  # Only violate if actually moving
                        traci.vehicle.setSpeedMode(vid, 0)  # Ignore traffic lights
                        traci.vehicle.setSpeed(vid, speed)   # Maintain speed through red
                        self._active_violators.add(vid)
                        traci.vehicle.setColor(vid, (255, 50, 50, 255))  # Red = violator
            except Exception:
                continue


# ============================================================
# HNR INJECTOR — Hilly Narrow Road (§9.2)
# ============================================================
class HNRInjector:
    """
    Detects vehicles entering tight bend sections and simulates
    cautious mountain driving with occasional overtaking attempts.
    """
    
    def __init__(self, slow_speed_range=(5.5, 11.0), overtake_probability=0.1):
        """
        Args:
            slow_speed_range: (min, max) speed in m/s for cautious driving
            overtake_probability: chance per step of a vehicle attempting to overtake
        """
        self.slow_speed_range = slow_speed_range
        self.overtake_probability = overtake_probability
        self._slowed_vehicles = set()

    def step(self, step: int, net, traci, bend_edges=None):
        """
        Slow vehicles on tight bends and occasionally trigger overtaking.
        
        Args:
            bend_edges: Set of edge IDs that are tight bends.
                        If None, detects edges with short length (< 50m) as bends.
        """
        if bend_edges is None:
            # Auto-detect short edges as potential bend segments
            bend_edges = set()
            for edge in net.getEdges():
                if edge.getLength() < 50.0:
                    bend_edges.add(edge.getID())

        try:
            vids = traci.vehicle.getIDList()
        except Exception:
            return

        for vid in vids:
            try:
                road = traci.vehicle.getRoadID(vid)
                if road in bend_edges:
                    if vid not in self._slowed_vehicles:
                        # Slow down vehicle entering a bend
                        target_speed = np.random.uniform(*self.slow_speed_range)
                        traci.vehicle.slowDown(vid, target_speed, 3.0)
                        self._slowed_vehicles.add(vid)
                    
                    # Occasionally trigger an overtaking attempt
                    if np.random.random() < self.overtake_probability:
                        try:
                            nlanes = net.getEdge(road).getLaneNumber()
                            if nlanes >= 2:
                                curr_lane = traci.vehicle.getLaneIndex(vid)
                                target_lane = 1 - curr_lane if nlanes == 2 else min(curr_lane + 1, nlanes - 1)
                                traci.vehicle.changeLane(vid, target_lane, 3.0)
                        except Exception:
                            pass
                else:
                    # Vehicle left bend region — remove slow-down tracking
                    self._slowed_vehicles.discard(vid)
            except Exception:
                continue

        # Clean up departed vehicles
        try:
            active_vids = set(traci.vehicle.getIDList())
            self._slowed_vehicles &= active_vids
        except Exception:
            pass
