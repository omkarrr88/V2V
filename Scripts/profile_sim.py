"""Quick profiler to identify BSD simulation bottlenecks."""
import os, sys, time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_SUMO_BIN = ""
if 'SUMO_HOME' in os.environ:
    _SUMO_BIN = os.path.join(os.environ['SUMO_HOME'], 'bin')
else:
    import importlib.util as _util
    _sumo_spec = _util.find_spec("sumo")
    if _sumo_spec and _sumo_spec.origin:
        _SUMO_BIN = os.path.join(os.path.dirname(_sumo_spec.origin), "bin")

if _SUMO_BIN and os.path.isdir(_SUMO_BIN):
    os.environ["PATH"] = _SUMO_BIN + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        try: os.add_dll_directory(_SUMO_BIN)
        except: pass

try:
    import libsumo as traci
    import libsumo.constants as tc
    print("libsumo OK")
except Exception as e:
    import traci
    import traci.constants as tc
    print(f"TraCI: {e}")

import random, numpy as np

SUMO_CFG = "../Maps/atal_v2v.sumocfg"
cmd = ["sumo", "-c", SUMO_CFG, "--start",
       "--step-length", "1.0",
       "--no-step-log", "true", "--no-duration-log", "true", "--no-warnings", "true"]
traci.start(cmd)

timers = {"simulationStep": 0, "getAllSubs": 0, "getDeparted": 0,
          "getCollisions": 0, "setColor": 0, "BSD_engine": 0, "total": 0}
counts = {k: 0 for k in timers}

t_total = time.perf_counter()
V_STATE_CACHE = {}

for step in range(60):
    t0 = time.perf_counter()
    traci.simulationStep()
    timers["simulationStep"] += time.perf_counter() - t0
    counts["simulationStep"] += 1

    t0 = time.perf_counter()
    departed = traci.simulation.getDepartedIDList()
    timers["getDeparted"] += time.perf_counter() - t0
    counts["getDeparted"] += 1

    for vid in departed:
        traci.vehicle.subscribe(vid, [tc.VAR_POSITION, tc.VAR_SPEED, tc.VAR_ACCELERATION,
                                       tc.VAR_ANGLE, tc.VAR_LENGTH, tc.VAR_WIDTH,
                                       tc.VAR_SIGNALS, tc.VAR_TYPE])

    t0 = time.perf_counter()
    sub_results = traci.vehicle.getAllSubscriptionResults()
    timers["getAllSubs"] += time.perf_counter() - t0
    counts["getAllSubs"] += 1

    t0 = time.perf_counter()
    if step % 10 == 0:
        traci.simulation.getCollisions()
    timers["getCollisions"] += time.perf_counter() - t0
    counts["getCollisions"] += 1

    # Simulate setColor cost
    t0 = time.perf_counter()
    for vid in list(sub_results.keys())[:10]:
        try: traci.vehicle.setColor(vid, (0, 200, 0, 255))
        except: pass
    timers["setColor"] += time.perf_counter() - t0
    counts["setColor"] += 1

timers["total"] = time.perf_counter() - t_total
traci.close()

print("\n=== BOTTLENECK PROFILE (60 steps) ===")
for k, v in timers.items():
    pct = (v / timers["total"]) * 100
    ms_per_step = (v / max(counts.get(k, 1), 1)) * 1000
    print(f"  {k:<20}: {v:6.2f}s total  ({pct:5.1f}%)  {ms_per_step:7.1f}ms/call")
print(f"\nTotal: {timers['total']:.2f}s for 60 steps = {timers['total']/60:.2f}s/step")
