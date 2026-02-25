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
        
        # Create PAIRS every 4 seconds — perfect overtaking scenarios
        # One starts 20m ahead but slower. The other starts at 0m but faster.
        # This guarantees they will sweep through each other's blind spots.
        for t in range(0, MAX_TIME, 4):
            rid = f"bsp_r{vid}"
            xml += f'    <route id="{rid}" edges="{route_str}"/>\n'
            
            # 50% chance: Lane 0 is slow, Lane 1 is fast (Left-side overtake)
            # 50% chance: Lane 1 is slow, Lane 0 is fast (Right-side overtake)
            if random.random() < 0.5:
                l_slow, l_fast = 0, 1
            else:
                l_slow, l_fast = 1, 0
            
            # Vehicle A (Slow, ahead)
            vt1 = random.choices(vtypes, weights=vweights, k=1)[0]
            xml += (f'    <vehicle id="bsp_{vid}" route="{rid}" type="{vt1}" '
                   f'depart="{t}" departLane="{l_slow}" departPos="20" departSpeed="15" maxSpeed="15"/>\n')
            vid += 1
            
            # Vehicle B (Fast, behind, catching up)
            vt2 = random.choices(vtypes, weights=vweights, k=1)[0]
            xml += (f'    <vehicle id="bsp_{vid}" route="{rid}" type="{vt2}" '
                   f'depart="{t}" departLane="{l_fast}" departPos="0" departSpeed="20" maxSpeed="20"/>\n')
            vid += 1
            
            # If 3+ lanes, third vehicle in lane 2
            if nlanes >= 3 and random.random() < 0.3:
                vt3 = random.choices(vtypes, weights=vweights, k=1)[0]
                xml += (f'    <vehicle id="bsp_{vid}" route="{rid}" type="{vt3}" '
                       f'depart="{t}" departLane="2" departPos="10" departSpeed="18"/>\n')
                vid += 1
    
    # ================================================================
    # PHASE 2: CLOSING SCENARIOS — Fast car catching slow car
    # Creates high R_ttc values (approaching from behind in adjacent lane)
    # ================================================================
    xml += '\n    <!-- PHASE 2: Closing scenarios (fast behind slow in adjacent lane) -->\n'
    
    for ml_edge in multi_lane_edges[:15]:  # Top 15 multi-lane edges
        route = find_route(ml_edge, min_len=3, max_len=6)
        if len(route) < 2:
            continue
        
        route_str = " ".join(e.getID() for e in route)
        
        for t in range(5, MAX_TIME, 60):
            rid = f"cls_r{vid}"
            xml += f'    <route id="{rid}" edges="{route_str}"/>\n'
            
            # Slow vehicle in lane 0
            xml += (f'    <vehicle id="cls_{vid}" route="{rid}" type="truck" '
                   f'depart="{t}" departLane="0" departPos="100" departSpeed="10"/>\n')
            vid += 1
            
            # Fast vehicle in lane 1 (will catch up and enter blind spot)
            xml += (f'    <vehicle id="cls_{vid}" route="{rid}" type="sedan" '
                   f'depart="{t + 3}" departLane="1" departPos="0" departSpeed="20" maxSpeed="33.33"/>\n')
            vid += 1
    
    # ================================================================
    # PHASE 3: Coverage traffic — all roads get vehicles
    # ================================================================
    xml += '\n    <!-- PHASE 3: Network coverage -->\n'
    for edge in all_edges:
        route = find_route(edge, min_len=2, max_len=4)
        if len(route) < 2:
            continue
        
        route_str = " ".join(e.getID() for e in route)
        rid = f"cov_r{vid}"
        xml += f'    <route id="{rid}" edges="{route_str}"/>\n'
        
        # 1 vehicle at t=0, 1 more later
        vt = random.choices(vtypes, weights=vweights, k=1)[0]
        xml += (f'    <vehicle id="cov_{vid}" route="{rid}" type="{vt}" '
               f'depart="0" departLane="best" departPos="base" departSpeed="15"/>\n')
        vid += 1
        
        t = random.randint(30, MAX_TIME)
        vt = random.choices(vtypes, weights=vweights, k=1)[0]
        xml += (f'    <vehicle id="cov_{vid}" route="{rid}" type="{vt}" '
               f'depart="{t}" departLane="best" departPos="base" departSpeed="15"/>\n')
        vid += 1
    
    # ================================================================
    # PHASE 4: Platoon bursts on bridges
    # ================================================================
    xml += '\n    <!-- PHASE 4: Platoon bursts -->\n'
    for i in range(20):
        if not multi_lane_edges: break
        ml_edge = random.choice(multi_lane_edges)
        route = find_route(ml_edge, min_len=3, max_len=6)
        if len(route) < 3: continue
        
        route_str = " ".join(e.getID() for e in route)
        rid = f"plt_r{vid}"
        xml += f'    <route id="{rid}" edges="{route_str}"/>\n'
        
        t_base = 10 + i * 15
        if t_base > MAX_TIME: break
        
        for j in range(4):
            lane = j % 2  # Alternate between lanes 0 and 1
            vt = random.choices(vtypes, weights=vweights, k=1)[0]
            t = t_base + j * 1.5
            if t > MAX_TIME: break
            xml += (f'    <vehicle id="plt_{vid}" route="{rid}" type="{vt}" '
                   f'depart="{t:.1f}" departLane="{lane}" departPos="base" departSpeed="15"/>\n')
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
