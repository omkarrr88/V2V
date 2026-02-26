"""
V2V BSD — Route Generator with GUARANTEED Blind Spot Scenarios
================================================================
Creates routes that FORCE vehicles into adjacent lanes on multi-lane roads,
ensuring the BSD engine will detect blind spot situations naturally.

KEY INSIGHT: departLane="best" puts all vehicles in the same lane.
We must use departLane="0" and departLane="1" with offset times to create
side-by-side driving that triggers blind spot detection.

TIMING: 3600 steps × 0.1s = 360s simulation time.
All departures must be in [0, 355].
"""
import os
import sys
import random
import numpy as np

if 'SUMO_HOME' in os.environ:
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
import sumolib


def generate_comprehensive_routes():
    net = sumolib.net.readNet("../Maps/atal.net.xml")
    all_edges = [e for e in net.getEdges() if not e.getID().startswith(":")]
    
    multi_lane_edges = [e for e in all_edges if e.getLaneNumber() >= 2 and e.getLength() > 50]
    single_lane_edges = [e for e in all_edges if e.getLaneNumber() == 1 and e.getLength() > 20]
    
    print(f"Network: {len(all_edges)} total edges")
    print(f"  Multi-lane: {len(multi_lane_edges)}")
    print(f"  Single-lane: {len(single_lane_edges)}")
    
    MAX_TIME = 350
    
    def find_route(start_edge, min_len=2, max_len=6):
        route = [start_edge]
        current = start_edge
        visited = {start_edge.getID()}
        for _ in range(max_len - 1):
            next_edges = [e for e in current.getOutgoing()
                          if e.getID() not in visited and not e.getID().startswith(":")]
            if not next_edges:
                break
            weights = [3.0 if e.getLaneNumber() >= 2 else 1.0 for e in next_edges]
            total = sum(weights)
            chosen = random.choices(next_edges, weights=[w/total for w in weights], k=1)[0]
            route.append(chosen)
            visited.add(chosen.getID())
            current = chosen
            if len(route) >= min_len and random.random() < 0.3:
                break
        return route
    
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<routes>\n\n'
    
    # Vehicle types
    xml += '    <vType id="sedan" length="4.5" width="1.8" maxSpeed="33.33" accel="2.6" decel="4.5" sigma="0.5" color="0,200,0"/>\n'
    xml += '    <vType id="suv" length="4.8" width="2.0" maxSpeed="30.56" accel="2.2" decel="4.0" sigma="0.5" color="0,200,0"/>\n'
    xml += '    <vType id="truck" length="12.0" width="2.5" maxSpeed="25.0" accel="1.0" decel="3.0" sigma="0.5" color="0,200,0"/>\n\n'
    
    vid = 0
    vtypes = ['sedan', 'suv', 'truck']
    vweights = [0.65, 0.25, 0.10]
    
    # ================================================================
    # PHASE 1: BLIND SPOT PAIRS — Two vehicles in adjacent lanes
    # This is the KEY phase that creates actual blind spot detections!
    # ================================================================
    xml += '    <!-- PHASE 1: Blind Spot Pairs (adjacent lanes, offset timing) -->\n'
    
    # Build routes that ONLY use multi-lane edges (so lane 1 always exists)
    def find_multilane_route(start_edge, min_len=2, max_len=5):
        """Route where ALL edges have 2+ lanes."""
        route = [start_edge]
        current = start_edge
        visited = {start_edge.getID()}
        for _ in range(max_len - 1):
            next_edges = [e for e in current.getOutgoing()
                          if e.getID() not in visited 
                          and not e.getID().startswith(":")
                          and e.getLaneNumber() >= 2]  # ONLY multi-lane successors!
            if not next_edges:
                break
            chosen = random.choice(next_edges)
            route.append(chosen)
            visited.add(chosen.getID())
            current = chosen
            if len(route) >= min_len:
                break
        return route
    
    for ml_edge in multi_lane_edges:
        route = find_multilane_route(ml_edge, min_len=1, max_len=4)
        # Single-edge routes are fine — we just need 2+ lanes
        
        route_str = " ".join(e.getID() for e in route)
        nlanes = ml_edge.getLaneNumber()
        
    # ================================================================
    # PHASE 1: BLIND SPOT PAIRS (THE "CHAOS" ENGINE)
    # ================================================================
    xml += '    <!-- PHASE 1: Extreme Blind Spot Density -->\n'
    
    for ml_edge in multi_lane_edges:
        route = find_multilane_route(ml_edge, min_len=1, max_len=6)
        route_str = " ".join(e.getID() for e in route)
        nlanes = ml_edge.getLaneNumber()
        
        # INCREASE FREQUENCY: Overtaking pairs every 3.0 seconds (Down from 1.5 to prevent crash)
        for t in np.arange(0, MAX_TIME, 3.0):
            rid = f"bsp_r{vid}"
            xml += f'    <route id="{rid}" edges="{route_str}"/>\n'
            
            # Alternate lanes
            l_slow, l_fast = (0, 1) if int(t*10) % 2 == 0 else (1, 0)
            
            # Ego-like Vehicle (Slow, ahead)
            xml += (f'    <vehicle id="bsp_{vid}" route="{rid}" type="{random.choice(vtypes)}" '
                   f'depart="{t:.1f}" departLane="{l_slow}" departPos="30" departSpeed="12" maxSpeed="12"/>\n')
            vid += 1
            
            # Aggressive Target (Fast, behind, catching up)
            xml += (f'    <vehicle id="bsp_{vid}" route="{rid}" type="sedan" '
                   f'depart="{t:.1f}" departLane="{l_fast}" departPos="0" departSpeed="28" maxSpeed="35"/>\n')
            vid += 1
            
            # Add a 3rd "blocking" vehicle if lanes allow
            if nlanes >= 3 and random.random() < 0.4:
                xml += (f'    <vehicle id="bsp_{vid}" route="{rid}" type="truck" '
                       f'depart="{t:.1f}" departLane="2" departPos="15" departSpeed="15"/>\n')
                vid += 1

    # ================================================================
    # PHASE 2: CROSS-MAP SATURATION
    # ================================================================
    xml += '\n    <!-- PHASE 2: Global Map Saturation -->\n'
    # Generate 150 random routes (Down from 500)
    for i in range(150):
        start_edge = random.choice(all_edges)
        route = find_route(start_edge, min_len=3, max_len=10)
        if len(route) < 2: continue
        
        route_str = " ".join(e.getID() for e in route)
        rid = f"sat_r_{vid}"
        xml += f'    <route id="{rid}" edges="{route_str}"/>\n'
        
        t = random.uniform(0, MAX_TIME)
        vt = random.choices(vtypes, weights=vweights, k=1)[0]
        xml += (f'    <vehicle id="sat_{vid}" route="{rid}" type="{vt}" '
               f'depart="{t:.1f}" departLane="best" departPos="random" departSpeed="max"/>\n')
        vid += 1

    # ================================================================
    # PHASE 3: SUDDEN BURSTS (ACCIDENT PRONE PLATOONS)
    # ================================================================
    xml += '\n    <!-- PHASE 3: High-Density Platoons (Accident Situations) -->\n'
    for i in range(40):
        if not multi_lane_edges: break
        ml_edge = random.choice(multi_lane_edges)
        route = find_route(ml_edge, min_len=4, max_len=8)
        if len(route) < 2: continue
        route_str = " ".join(e.getID() for e in route)
        rid = f"plt_r{vid}"
        xml += f'    <route id="{rid}" edges="{route_str}"/>\n'
        
        t_start = random.uniform(5, MAX_TIME - 30)
        # 6 cars in a tight pack
        for j in range(6):
            lane = random.choice([0, 1])
            xml += (f'    <vehicle id="plt_{vid}" route="{rid}" type="sedan" '
                   f'depart="{t_start + j*0.5:.1f}" departLane="{lane}" departPos="base" departSpeed="20"/>\n')
            vid += 1

    # ================================================================
    # PHASE 4: OMNI-DIRECTIONAL CHAOS (360-Degree Inflow)
    # ================================================================
    xml += '\n    <!-- PHASE 4: 360-Degree Inflow -->\n'
    boundary_edges = [e for e in all_edges if not e.getIncoming()]
    if not boundary_edges: boundary_edges = all_edges[:20]
    
    for be in boundary_edges:
        for t in range(0, MAX_TIME, 10):
            # Fast scout vehicles coming from everywhere
            route = find_route(be, min_len=10, max_len=20)
            if len(route) < 3: continue
            route_str = " ".join(e.getID() for e in route)
            rid = f"omn_r{vid}"
            xml += f'    <route id="{rid}" edges="{route_str}"/>\n'
            xml += (f'    <vehicle id="omn_{vid}" route="{rid}" type="sedan" '
                   f'depart="{t}" departLane="best" departPos="base" departSpeed="max"/>\n')
            vid += 1
    
    xml += '\n</routes>\n'
    
    out_path = "../Maps/atal_bridge_scenarios.rou.xml"
    with open(out_path, 'w') as f:
        f.write(xml)
    
    print(f"\n✅ Generated {vid} vehicles")
    print(f"   Blind spot pairs: ~{len(multi_lane_edges) * (MAX_TIME // 10) * 2}")
    print(f"   Closing scenarios: ~{min(15,len(multi_lane_edges)) * (MAX_TIME // 20) * 2}")
    print(f"   Coverage: ~{len(all_edges) * 2}")
    print(f"   All departures within 0-{MAX_TIME}s")
    print(f"   Output: {out_path}")
    return out_path


if __name__ == "__main__":
    random.seed(42)
    np.random.seed(42)
    generate_comprehensive_routes()
