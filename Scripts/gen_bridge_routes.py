"""
V2V BSD — Route Generator for All-Road Coverage
====================================================
Generates additional vehicles targeting multi-lane edges (Atal Setu bridge)
with multi-edge routes so vehicles actually drive through and interact.

Also ensures ALL roads in the network have traffic — no road should remain
empty for extended periods. Vehicles move in BOTH directions on all roads.

Real-life scenario: Mixed traffic (sedans, SUVs, trucks) with varied departure
speeds and different vehicle types for realistic V2V communication scenarios.
"""
import os
import sys
import random
import numpy as np

# Add SUMO tools to path
if 'SUMO_HOME' in os.environ:
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
import sumolib


def generate_comprehensive_routes():
    """
    Generate route file with:
    1. Dense traffic on multi-lane bridge edges (blind spot scenarios)
    2. Coverage of ALL edges in the network (no empty roads)
    3. Mixed vehicle types (sedan, SUV, truck)
    4. Bidirectional traffic
    5. Varied speeds and departure intervals
    """
    net = sumolib.net.readNet("../Maps/atal.net.xml")
    all_edges = [e for e in net.getEdges() if not e.getID().startswith(":")]
    
    # Categorize edges
    multi_lane_edges = [e for e in all_edges if e.getLaneNumber() >= 2 and e.getLength() > 50]
    single_lane_edges = [e for e in all_edges if e.getLaneNumber() == 1 and e.getLength() > 20]
    long_edges = [e for e in all_edges if e.getLength() > 200]
    
    print(f"Network: {len(all_edges)} total edges")
    print(f"  Multi-lane: {len(multi_lane_edges)}")
    print(f"  Single-lane: {len(single_lane_edges)}")
    print(f"  Long (>200m): {len(long_edges)}")
    
    # Build adjacency for multi-edge routes
    def find_route_from_edge(start_edge, min_length=2, max_length=8):
        """Find a valid multi-edge route starting from the given edge."""
        route = [start_edge]
        current = start_edge
        visited = {start_edge.getID()}
        
        for _ in range(max_length - 1):
            outgoing = current.getOutgoing()
            next_edges = []
            for conn_edge in outgoing:
                if conn_edge.getID() not in visited and not conn_edge.getID().startswith(":"):
                    next_edges.append(conn_edge)
            
            if not next_edges:
                break
            
            # Prefer longer edges and multi-lane edges
            weights = []
            for e in next_edges:
                w = 1.0
                if e.getLaneNumber() >= 2:
                    w *= 3.0  # Prefer multi-lane
                if e.getLength() > 200:
                    w *= 2.0  # Prefer long edges
                weights.append(w)
            
            total = sum(weights)
            weights = [w/total for w in weights]
            chosen = random.choices(next_edges, weights=weights, k=1)[0]
            route.append(chosen)
            visited.add(chosen.getID())
            current = chosen
            
            if len(route) >= min_length:
                if random.random() < 0.3:  # 30% chance to stop extending
                    break
        
        return route
    
    routes_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    routes_xml += '<routes>\n\n'
    
    # ──── Vehicle Types ────
    routes_xml += '    <!-- Vehicle Types for realistic traffic mix -->\n'
    routes_xml += '    <vType id="sedan_v2v" length="4.5" width="1.8" maxSpeed="33.33" '
    routes_xml += 'accel="2.6" decel="4.5" sigma="0.5" color="0,200,0"/>\n'
    routes_xml += '    <vType id="suv_v2v" length="4.8" width="2.0" maxSpeed="30.56" '
    routes_xml += 'accel="2.2" decel="4.0" sigma="0.5" color="0,200,0"/>\n'
    routes_xml += '    <vType id="truck_v2v" length="12.0" width="2.5" maxSpeed="25.0" '
    routes_xml += 'accel="1.0" decel="3.0" sigma="0.5" color="0,200,0"/>\n\n'
    
    vid_counter = 0
    vtypes = ['sedan_v2v', 'suv_v2v', 'truck_v2v']
    vtype_weights = [0.65, 0.25, 0.10]  # Realistic distribution
    
    # Phase 1: High-density multi-lane bridge traffic (Blind spot generation)
    # 3-second departures across ALL multi-lane edges over 1 hour
    routes_xml += '    <!-- Phase 1: High-density bridge traffic -->\n'
    
    for ml_edge in multi_lane_edges:
        route = find_route_from_edge(ml_edge, min_length=2, max_length=6)
        if len(route) < 2:
            continue
        
        route_edges = " ".join(e.getID() for e in route)
        route_id = f"ml_route_{vid_counter}"
        routes_xml += f'    <route id="{route_id}" edges="{route_edges}"/>\n'
        
        nlanes = ml_edge.getLaneNumber()
        # High volume: Every 3 seconds
        for t in range(0, 3600, 3):
            vtype = random.choices(vtypes, weights=vtype_weights, k=1)[0]
            # Primary lane vehicle
            routes_xml += (f'    <vehicle id="ml_{vid_counter}" route="{route_id}" '
                          f'type="{vtype}" depart="{t}" departLane="best" '
                          f'departPos="random" departSpeed="max"/>\n')
            vid_counter += 1
            
            # Secondary lane vehicle (creates blind spot pairing)
            if nlanes >= 2:
                vtype2 = random.choices(vtypes, weights=vtype_weights, k=1)[0]
                routes_xml += (f'    <vehicle id="ml_{vid_counter}" route="{route_id}" '
                              f'type="{vtype2}" depart="{t + 0.5}" departLane="best" '
                              f'departPos="random" departSpeed="max"/>\n')
                vid_counter += 1
    
    # Phase 2: Full network coverage (High density)
    routes_xml += '\n    <!-- Phase 2: Comprehensive coverage traffic -->\n'
    for edge in all_edges:
        route = find_route_from_edge(edge, min_length=2, max_length=5)
        if len(route) < 2:
            continue
        
        route_edges = " ".join(e.getID() for e in route)
        route_id = f"cov_route_{vid_counter}"
        routes_xml += f'    <route id="{route_id}" edges="{route_edges}"/>\n'
        
        # 3-5 vehicles per coverage route
        for i in range(random.randint(3, 5)):
            t = random.randint(0, 3550)
            vtype = random.choices(vtypes, weights=vtype_weights, k=1)[0]
            routes_xml += (f'    <vehicle id="cov_{vid_counter}" route="{route_id}" '
                          f'type="{vtype}" depart="{t}" departLane="best" '
                          f'departPos="random" departSpeed="max"/>\n')
            vid_counter += 1
    
    # Phase 3: Platoon bursts (Restored to 30)
    routes_xml += '\n    <!-- Phase 3: Platoon bursts -->\n'
    for burst_idx in range(30):
        if not multi_lane_edges: break
        ml_edge = random.choice(multi_lane_edges)
        route = find_route_from_edge(ml_edge, min_length=3, max_length=7)
        if len(route) < 3: continue
        
        route_edges = " ".join(e.getID() for e in route)
        route_id = f"plt_route_{vid_counter}"
        routes_xml += f'    <route id="{route_id}" edges="{route_edges}"/>\n'
        t_base = 60 + burst_idx * 100
        
        for car_idx in range(6): # 6 cars per platoon
            vtype = random.choices(vtypes, weights=vtype_weights, k=1)[0]
            t = t_base + car_idx * 2
            routes_xml += (f'    <vehicle id="plt_{vid_counter}" route="{route_id}" '
                          f'type="{vtype}" depart="{t}" departLane="best" '
                          f'departPos="random" departSpeed="max"/>\n')
            vid_counter += 1
    
    # Phase 4: Emergency scenarios (Restored to 20)
    routes_xml += '\n    <!-- Phase 4: Emergency scenarios -->\n'
    for scenario_idx in range(20):
        if not long_edges: break
        edge = random.choice(long_edges)
        route = find_route_from_edge(edge, min_length=2, max_length=4)
        if len(route) < 2: continue
        
        route_edges = " ".join(e.getID() for e in route)
        route_id = f"emg_route_{vid_counter}"
        routes_xml += f'    <route id="{route_id}" edges="{route_edges}"/>\n'
        t = 120 + scenario_idx * 150
        
        routes_xml += (f'    <vehicle id="emg_{vid_counter}" route="{route_id}" '
                      f'type="sedan_v2v" depart="{t}" departLane="best" '
                      f'departPos="0" departSpeed="max"/>\n')
        vid_counter += 1
        
        routes_xml += (f'    <vehicle id="emg_{vid_counter}" route="{route_id}" '
                      f'type="truck_v2v" depart="{t+2}" departLane="best" '
                      f'departPos="100" departSpeed="10"/>\n')
        vid_counter += 1
    
    routes_xml += '\n</routes>\n'
    
    out_path = "../Maps/atal_bridge_scenarios.rou.xml"
    with open(out_path, 'w') as f:
        f.write(routes_xml)
    
    print(f"\n✅ Restored: Generated {vid_counter} vehicles (High Volume Scenarios)")
    print(f"   Output: {out_path}")
    return out_path


if __name__ == "__main__":
    random.seed(42)
    np.random.seed(42)
    generate_comprehensive_routes()
