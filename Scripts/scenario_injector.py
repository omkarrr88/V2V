"""
V2V BSD — Scenario Injector
==============================
Injects specific blind spot test scenarios directly into the running SUMO
simulation using TraCI. Creates vehicles in adjacent lanes, forces lane
changes, and sets up dangerous/safe situations to test all 4 alert levels.

This runs INSIDE the simulation loop, called from v2v_bsd_simulation.py.
"""

import traci
import numpy as np
import sumolib
from typing import List, Tuple

# Multi-lane edges on Atal Setu bridge (long, multi-lane = ideal blind spot testing)
# These are the longest 2+ lane edges identified from the network
BRIDGE_EDGES = [
    "265939226#3",    # 4266m, 2 lanes — main bridge span
    "265939225#0",    # 4263m, 2 lanes — reverse direction
    "265939225#3",    # 2000m, 2 lanes
    "265939226#0",    # 1813m, 2 lanes
    "315422881#0",    # 1024m, 2 lanes
    "936649873#0",    # 615m, 2 lanes
    "700751614#1",    # 301m, 2 lanes
    "936649873#8",    # 245m, 2 lanes
    "692196517#3",    # 218m, 2 lanes
    "936649873#3",    # 232m, 2 lanes
]

# Scenario counter
_scenario_counter = 0


def _next_id() -> str:
    global _scenario_counter
    _scenario_counter += 1
    return f"bsd_test_{_scenario_counter}"


def _safe_add_vehicle(vid: str, route_id: str, edge: str, lane: int, 
                       pos: float, speed: float, vtype: str = "DEFAULT_VEHTYPE") -> bool:
    """Safely add a vehicle. Returns True if successfully added."""
    try:
        # Create route if needed
        try:
            traci.route.add(route_id, [edge])
        except traci.exceptions.TraCIException:
            pass  # Route already exists
        
        traci.vehicle.add(vid, route_id, departLane=str(lane), 
                         departPos=str(pos), departSpeed=str(speed),
                         typeID=vtype)
        return True
    except traci.exceptions.TraCIException:
        return False


def _find_valid_edge(net) -> Tuple[str, int]:
    """Find a multi-lane edge that exists and has vehicles or space."""
    for edge_id in BRIDGE_EDGES:
        try:
            edge = net.getEdge(edge_id)
            if edge.getLaneNumber() >= 2 and edge.getLength() > 100:
                return edge_id, edge.getLaneNumber()
        except Exception:
            continue
    return None, 0


def inject_blind_spot_scenario(step: int, net, scenario_type: str = "auto") -> List[dict]:
    """
    Inject blind spot test scenarios into the simulation.
    
    Args:
        step: Current simulation step
        net: sumolib Net object
        scenario_type: "auto" cycles through all, or specify one
        
    Returns:
        List of injected scenario descriptions for logging
    """
    injected = []
    
    if scenario_type == "auto":
        # Cycle through scenarios at different intervals
        cycle = (step // 200) % 8
        scenario_fns = [
            _inject_adjacent_cruise,      # 0: Two cars side by side → CAUTION
            _inject_closing_blind_spot,     # 1: Fast car overtaking → WARNING
            _inject_lane_change_into_bs,    # 2: Lane change into blind spot → CRITICAL
            _inject_safe_separation,        # 3: Cars well separated → SAFE
            _inject_truck_blind_spot,       # 4: Truck in blind spot → WARNING (mass)
            _inject_intent_blinker,         # 5: Blinker + drift → CRITICAL
            _inject_high_speed_approach,    # 6: High-speed TTC → CRITICAL
            _inject_multi_vehicle_bs,       # 7: Multiple cars in blind spot
        ]
        
        if step % 200 == 0:  # Inject new scenario every 20 seconds (200 × 0.1s)
            fn = scenario_fns[cycle]
            result = fn(step, net)
            if result:
                injected.extend(result)
    
    return injected


def _inject_adjacent_cruise(step: int, net) -> List[dict]:
    """
    Scenario: Two vehicles cruising side by side in adjacent lanes.
    Expected: CAUTION level (P > 0, R_decel moderate, R_ttc low)
    """
    edge_id, nlanes = _find_valid_edge(net)
    if edge_id is None or nlanes < 2:
        return []
    
    edge = net.getEdge(edge_id)
    pos = min(edge.getLength() * 0.3, 500)
    speed = 22.0  # ~80 km/h
    
    vid_ego = _next_id()
    vid_target = _next_id()
    route_ego = f"route_sc_{vid_ego}"
    route_target = f"route_sc_{vid_target}"
    
    results = []
    if _safe_add_vehicle(vid_ego, route_ego, edge_id, 0, pos, speed):
        results.append({'vid': vid_ego, 'role': 'ego', 'scenario': 'adjacent_cruise',
                       'expected_alert': 'CAUTION', 'lane': 0, 'speed': speed})
    
    if _safe_add_vehicle(vid_target, route_target, edge_id, 1, pos - 3, speed - 1):
        results.append({'vid': vid_target, 'role': 'target', 'scenario': 'adjacent_cruise',
                       'expected_alert': 'CAUTION', 'lane': 1, 'speed': speed - 1})
        
        # Color the ego yellow to make CAUTION visible
        try:
            traci.vehicle.setColor(vid_ego, (255, 200, 0, 255))  # Yellow
        except:
            pass
    
    return results


def _inject_closing_blind_spot(step: int, net) -> List[dict]:
    """
    Scenario: Fast vehicle approaching from behind in blind spot.
    Expected: WARNING level (R_ttc elevated due to closing speed)
    """
    edge_id, nlanes = _find_valid_edge(net)
    if edge_id is None or nlanes < 2:
        return []
    
    edge = net.getEdge(edge_id)
    pos = min(edge.getLength() * 0.4, 600)
    
    vid_ego = _next_id()
    vid_fast = _next_id()
    
    results = []
    if _safe_add_vehicle(vid_ego, f"route_sc_{vid_ego}", edge_id, 0, pos, 20.0):
        results.append({'vid': vid_ego, 'role': 'ego', 'scenario': 'closing_blind_spot',
                       'expected_alert': 'WARNING', 'lane': 0, 'speed': 20.0})
    
    # Fast car in lane 1, behind, closing rapidly
    if _safe_add_vehicle(vid_fast, f"route_sc_{vid_fast}", edge_id, 1, pos - 15, 30.0):
        results.append({'vid': vid_fast, 'role': 'target', 'scenario': 'closing_blind_spot',
                       'expected_alert': 'WARNING', 'lane': 1, 'speed': 30.0})
    
    return results


def _inject_lane_change_into_bs(step: int, net) -> List[dict]:
    """
    Scenario: Vehicle changes lane directly into another vehicle's blind spot.
    Expected: CRITICAL (high P + R_decel + R_ttc → CRI > 0.80)
    """
    edge_id, nlanes = _find_valid_edge(net)
    if edge_id is None or nlanes < 2:
        return []
    
    edge = net.getEdge(edge_id)
    pos = min(edge.getLength() * 0.5, 700)
    
    vid_ego = _next_id()
    vid_target = _next_id()
    
    results = []
    if _safe_add_vehicle(vid_ego, f"route_sc_{vid_ego}", edge_id, 0, pos, 25.0):
        results.append({'vid': vid_ego, 'role': 'ego', 'scenario': 'lane_change_bs',
                       'expected_alert': 'CRITICAL', 'lane': 0, 'speed': 25.0})
    
    # Target right in the blind spot zone, very close
    if _safe_add_vehicle(vid_target, f"route_sc_{vid_target}", edge_id, 1, pos - 2.0, 24.0):
        results.append({'vid': vid_target, 'role': 'target', 'scenario': 'lane_change_bs',
                       'expected_alert': 'CRITICAL', 'lane': 1, 'speed': 24.0})
        
        # Force ego to signal lane change toward threat
        try:
            traci.vehicle.setSignals(vid_ego, 1)  # Right blinker
        except:
            pass
    
    return results


def _inject_safe_separation(step: int, net) -> List[dict]:
    """
    Scenario: Vehicles well separated (different speeds, different positions).
    Expected: SAFE (P near 0, all R values low)
    """
    edge_id, nlanes = _find_valid_edge(net)
    if edge_id is None or nlanes < 2:
        return []
    
    edge = net.getEdge(edge_id)
    pos = min(edge.getLength() * 0.3, 400)
    
    vid1 = _next_id()
    vid2 = _next_id()
    
    results = []
    if _safe_add_vehicle(vid1, f"route_sc_{vid1}", edge_id, 0, pos, 22.0):
        results.append({'vid': vid1, 'role': 'ego', 'scenario': 'safe_separation',
                       'expected_alert': 'SAFE', 'lane': 0, 'speed': 22.0})
    
    # Target far ahead, not in blind spot
    if _safe_add_vehicle(vid2, f"route_sc_{vid2}", edge_id, 1, pos + 80, 22.0):
        results.append({'vid': vid2, 'role': 'target', 'scenario': 'safe_separation',
                       'expected_alert': 'SAFE', 'lane': 1, 'speed': 22.0})
    
    return results


def _inject_truck_blind_spot(step: int, net) -> List[dict]:
    """
    Scenario: Heavy truck in blind spot (mass affects R_decel).
    Expected: WARNING (high R_decel due to truck mass)
    """
    edge_id, nlanes = _find_valid_edge(net)
    if edge_id is None or nlanes < 2:
        return []
    
    edge = net.getEdge(edge_id)
    pos = min(edge.getLength() * 0.4, 500)
    
    vid_ego = _next_id()
    vid_truck = _next_id()
    
    results = []
    if _safe_add_vehicle(vid_ego, f"route_sc_{vid_ego}", edge_id, 0, pos, 20.0):
        results.append({'vid': vid_ego, 'role': 'ego', 'scenario': 'truck_blind_spot',
                       'expected_alert': 'WARNING', 'lane': 0, 'speed': 20.0})
    
    # Heavy truck in adjacent lane, slightly behind
    if _safe_add_vehicle(vid_truck, f"route_sc_{vid_truck}", edge_id, 1, pos - 5, 19.0):
        try:
            traci.vehicle.setLength(vid_truck, 12.0)
            traci.vehicle.setWidth(vid_truck, 2.5)
            traci.vehicle.setParameter(vid_truck, "mass", "15000")
            traci.vehicle.setColor(vid_truck, (100, 100, 255, 255))  # Blue truck
        except:
            pass
        results.append({'vid': vid_truck, 'role': 'truck_target', 'scenario': 'truck_blind_spot',
                       'expected_alert': 'WARNING', 'lane': 1, 'speed': 19.0})
    
    return results


def _inject_intent_blinker(step: int, net) -> List[dict]:
    """
    Scenario: Ego has blinker on AND is drifting toward blind spot target.
    Expected: CRITICAL (R_intent = 1.0, plus P and R_ttc)
    """
    edge_id, nlanes = _find_valid_edge(net)
    if edge_id is None or nlanes < 2:
        return []
    
    edge = net.getEdge(edge_id)
    pos = min(edge.getLength() * 0.5, 600)
    
    vid_ego = _next_id()
    vid_target = _next_id()
    
    results = []
    if _safe_add_vehicle(vid_ego, f"route_sc_{vid_ego}", edge_id, 0, pos, 22.0):
        # Set right blinker and try to force lane change
        try:
            traci.vehicle.setSignals(vid_ego, 1)  # Right blinker
            traci.vehicle.changeLane(vid_ego, 1, 5.0)  # Try to change to lane 1
        except:
            pass
        results.append({'vid': vid_ego, 'role': 'ego_intent', 'scenario': 'intent_blinker',
                       'expected_alert': 'CRITICAL', 'lane': 0, 'speed': 22.0})
    
    if _safe_add_vehicle(vid_target, f"route_sc_{vid_target}", edge_id, 1, pos - 3, 21.0):
        results.append({'vid': vid_target, 'role': 'target', 'scenario': 'intent_blinker',
                       'expected_alert': 'CRITICAL', 'lane': 1, 'speed': 21.0})
    
    return results


def _inject_high_speed_approach(step: int, net) -> List[dict]:
    """
    Scenario: High-speed vehicle rapidly closing from behind in blind spot.
    Expected: CRITICAL (very low TTC → R_ttc = 1.0)
    """
    edge_id, nlanes = _find_valid_edge(net)
    if edge_id is None or nlanes < 2:
        return []
    
    edge = net.getEdge(edge_id)
    pos = min(edge.getLength() * 0.3, 500)
    
    vid_ego = _next_id()
    vid_fast = _next_id()
    
    results = []
    if _safe_add_vehicle(vid_ego, f"route_sc_{vid_ego}", edge_id, 0, pos, 15.0):
        results.append({'vid': vid_ego, 'role': 'ego', 'scenario': 'high_speed_approach',
                       'expected_alert': 'CRITICAL', 'lane': 0, 'speed': 15.0})
    
    # Very fast car approaching from behind
    if _safe_add_vehicle(vid_fast, f"route_sc_{vid_fast}", edge_id, 1, pos - 8, 35.0):
        try:
            traci.vehicle.setColor(vid_fast, (255, 0, 0, 255))  # Red = danger
        except:
            pass
        results.append({'vid': vid_fast, 'role': 'fast_target', 'scenario': 'high_speed_approach',
                       'expected_alert': 'CRITICAL', 'lane': 1, 'speed': 35.0})
    
    return results


def _inject_multi_vehicle_bs(step: int, net) -> List[dict]:
    """
    Scenario: Multiple vehicles surrounding the ego in blind spots.
    Expected: WARNING/CRITICAL on BOTH sides
    """
    edge_id, nlanes = _find_valid_edge(net)
    if edge_id is None or nlanes < 2:
        return []
    
    edge = net.getEdge(edge_id)
    pos = min(edge.getLength() * 0.4, 500)
    
    results = []
    
    # Ego in lane 0 (or middle lane if 3 lanes)
    vid_ego = _next_id()
    ego_lane = 0 if nlanes == 2 else 1
    if _safe_add_vehicle(vid_ego, f"route_sc_{vid_ego}", edge_id, ego_lane, pos, 20.0):
        results.append({'vid': vid_ego, 'role': 'ego', 'scenario': 'multi_vehicle_bs',
                       'expected_alert': 'WARNING', 'lane': ego_lane, 'speed': 20.0})
    
    # Target in adjacent lane(s)
    for offset_lane in range(nlanes):
        if offset_lane == ego_lane:
            continue
        vid_t = _next_id()
        t_pos = pos - 4 + np.random.uniform(-2, 2)
        t_speed = 20.0 + np.random.uniform(-3, 3)
        if _safe_add_vehicle(vid_t, f"route_sc_{vid_t}", edge_id, offset_lane, 
                              max(10, t_pos), max(5, t_speed)):
            results.append({'vid': vid_t, 'role': 'target', 'scenario': 'multi_vehicle_bs',
                           'expected_alert': 'WARNING', 'lane': offset_lane, 'speed': t_speed})
    
    return results


def force_vehicle_interactions(step: int):
    """
    Called every step to maintain active scenario vehicles' behaviors.
    Also force-spawns companion vehicles right into blind spots of existing
    vehicles on multi-lane edges to guarantee all alert levels are visible.
    """
    try:
        vehicles = traci.vehicle.getIDList()
        
        # ── Part 1: Maintain existing scenario vehicles ──
        for vid in vehicles:
            if not vid.startswith("bsd_test_"):
                continue
            
            # Periodically toggle signals on scenario vehicles for intent testing
            if step % 50 == 0 and np.random.random() < 0.3:
                try:
                    signal = np.random.choice([0, 1, 2])  # none, right, left
                    traci.vehicle.setSignals(vid, signal)
                except:
                    pass
            
            # Force speed changes to create closing/separating
            if step % 30 == 0 and np.random.random() < 0.3:
                try:
                    current_speed = traci.vehicle.getSpeed(vid)
                    delta = np.random.uniform(-5, 5)
                    new_speed = max(5, min(35, current_speed + delta))
                    traci.vehicle.setSpeed(vid, new_speed)
                except:
                    pass

        # ── Part 2: Force blind spot companions on existing vehicles ──
        # Every 100 steps (10 seconds), find vehicles on multi-lane edges
        # and force-spawn a companion in their blind spot
        if step % 100 == 0 and step >= 100:
            _force_spawn_blind_spot_companions(step, vehicles)
            
    except:
        pass


def _force_spawn_blind_spot_companions(step: int, vehicles: list):
    """
    Find existing vehicles on multi-lane edges and spawn companions
    directly in their blind spot zones to force CRI elevation.
    """
    spawned = 0
    max_spawns = 3  # Max per cycle

    for vid in vehicles:
        if spawned >= max_spawns:
            break
        if vid.startswith("bsd_test_"):
            continue  # Skip existing test vehicles
        
        try:
            # Get vehicle's edge and lane
            edge_id = traci.vehicle.getRoadID(vid)
            if edge_id.startswith(":"):
                continue  # Skip junctions
            
            lane_id = traci.vehicle.getLaneID(vid)
            lane_idx = traci.vehicle.getLaneIndex(vid)
            
            # Check if edge has multiple lanes safely using net object if possible
            # Fallback to TraCI check
            lane_count = 0
            try:
                # Use a more reliable way to count lanes
                for i in range(8):
                    try:
                        traci.lane.getLength(f"{edge_id}_{i}")
                        lane_count = i + 1
                    except:
                        break
            except:
                continue
            
            # Get target vehicle position
            try:
                pos = traci.vehicle.getPosition(vid)
                speed = traci.vehicle.getSpeed(vid)
                angle = traci.vehicle.getAngle(vid)
                lane_pos = traci.vehicle.getLanePosition(vid)
            except:
                continue
            
            if speed < 2.0:
                continue  # Skip stopped vehicles
            
            # Determine which adjacent lane to use safely
            target_lane = 1 if lane_idx == 0 else lane_idx - 1
            if target_lane >= lane_count or target_lane < 0:
                target_lane = "best"
            
            # Spawn companion in different blind spot positions based on step
            scenario = (step // 100) % 4
            companion_vid = _next_id()
            companion_route = f"route_sc_{companion_vid}"
            
            try:
                traci.route.add(companion_route, [edge_id])
            except: pass
            
            if scenario == 0:
                # Adjacent cruise — right beside, slightly behind
                offset_pos = max(10, lane_pos - 3)
                offset_speed = speed - 1
            elif scenario == 1:
                # High speed approach — behind, faster
                offset_pos = max(10, lane_pos - 12)
                offset_speed = speed + 10
            elif scenario == 2:
                # Very close — nearly touching
                offset_pos = max(10, lane_pos - 1)
                offset_speed = speed - 2
            else:
                # Matching speed, blind spot overlap
                offset_pos = max(10, lane_pos - 4)
                offset_speed = speed
            
            try:
                traci.vehicle.add(
                    companion_vid, companion_route,
                    departLane=str(target_lane) if isinstance(target_lane, int) else target_lane,
                    departPos=str(offset_pos),
                    departSpeed=str(max(3, offset_speed)),
                )
                
                if scenario == 2:
                    try:
                        if isinstance(target_lane, int) and target_lane > lane_idx:
                            traci.vehicle.setSignals(vid, 1)
                        else:
                            traci.vehicle.setSignals(vid, 2)
                    except: pass
                
                spawned += 1
            except:
                pass
                
        except:
            continue

