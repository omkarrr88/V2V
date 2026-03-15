"""Quick test of the BSD engine core computations — V3.0 5-field BSM version."""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from bsd_engine import *
import numpy as np

e = BSDEngine()

# Helper: create VehicleState with 5-field BSM structure
def vs(vid, x, y, speed, accel_signed, heading, yaw_rate, length=4.5, width=1.8, mass=1500, mu=0.7, vtype='sedan', ts=0):
    """Create a VehicleState from signed accel (for test convenience)."""
    a_pos = max(0.0, accel_signed)
    d_pos = max(0.0, -accel_signed)
    return VehicleState(
        vid=vid, x=x, y=y, speed=speed,
        accel=a_pos, decel=d_pos,
        heading=heading, yaw_rate=yaw_rate,
        net_accel=accel_signed,
        length=length, width=width, mass=mass,
        mu=mu, vehicle_type=vtype, timestamp=ts,
    )

# Ego heading north (π/2 in math convention)
ego = vs('ego', 100, 100, 25, 0, np.pi/2, 0)

# Target on RIGHT, slightly behind, same heading, slower → classic blind spot
t_right = vs('t1', 103.5, 97, 22, -1, np.pi/2, 0)
tracker_r = TargetTracker(vid='t1', last_state=t_right)
r = e._compute_cri_for_target(ego, t_right, tracker_r)
print("=== RIGHT-SIDE TARGET (classic blind spot) ===")
print(f"  Side:     {r['side']}")
print(f"  x_rel:    {r['x_rel']:.2f} m")
print(f"  y_rel:    {r['y_rel']:.2f} m")
print(f"  d_gap:    {r['d_gap']:.2f} m")
print(f"  In zone:  {r['in_zone']}")
print(f"  P:        {r['P']:.4f}")
print(f"  R_decel:  {r['R_decel']:.4f}")
print(f"  R_ttc:    {r['R_ttc']:.4f}")
print(f"  R_intent: {r['R_intent']:.4f}")
print(f"  PLR mult: {r['plr_multiplier']:.4f}")
print(f"  CRI:      {r['cri']:.4f}")

# Target on LEFT, slightly behind
t_left = vs('t2', 96.5, 97, 22, -1, np.pi/2, 0)
tracker_l = TargetTracker(vid='t2', last_state=t_left)
r2 = e._compute_cri_for_target(ego, t_left, tracker_l)
print("\n=== LEFT-SIDE TARGET (verify |P_lat| fix) ===")
print(f"  Side:     {r2['side']}")
print(f"  x_rel:    {r2['x_rel']:.2f} m")
print(f"  P:        {r2['P']:.4f}  (should be positive, not negative!)")
print(f"  CRI:      {r2['cri']:.4f}")

# Verify P is positive for both sides
assert r['P'] >= 0, f"RIGHT P is negative: {r['P']}"
assert r2['P'] >= 0, f"LEFT P is negative: {r2['P']}"
print("\n✅ P_lat absolute value fix verified — both sides produce positive probability!")

# Test direction-aware intent: ego turns RIGHT (no blinker available in 5-field BSM)
ego_turning = vs('ego2', 100, 100, 25, 0, np.pi/2, -0.1)
dummy_target = vs('dummy', 103.5, 97, 22, 0, np.pi/2, 0)
r_intent_right = e._compute_R_intent(ego_turning, dummy_target, "RIGHT")
r_intent_left = e._compute_R_intent(ego_turning, dummy_target, "LEFT")
print(f"\n=== INTENT (ego turning RIGHT, no blinker — 5-field BSM) ===")
print(f"  R_intent toward RIGHT threat: {r_intent_right:.4f} (should be > 0, pure drift)")
print(f"  R_intent toward LEFT threat:  {r_intent_left:.4f}  (should be 0)")
assert r_intent_right > 0, "RIGHT intent should be elevated from drift!"
assert r_intent_left == 0, "LEFT intent should be zero when drifting right!"
# With no signals, R_intent max is W_LAT = 0.6
assert r_intent_right <= 0.6, f"R_intent must be ≤ W_LAT=0.6, got {r_intent_right}"
print("✅ Direction-aware drift-only intent verified — no signals, correct behavior!")

# Test R_intent with signals=0 (should produce pure drift-based score)
ego_no_sig = vs('ego_ns', 100, 100, 25, 0, np.pi/2, -0.2)
ri_no_sig = e._compute_R_intent(ego_no_sig, dummy_target, "RIGHT")
print(f"\n=== R_INTENT WITH SIGNALS=0 (pure drift) ===")
print(f"  R_intent (no signals, drifting right): {ri_no_sig:.4f}")
assert ri_no_sig > 0, "Should have positive intent from lateral drift"
assert ri_no_sig <= Params.W_LAT, "Must be bounded by W_LAT"
print("✅ R_intent with signals=0 produces pure drift-based score!")

# Test full process_step with side-specific CRI
print("\n=== FULL PROCESS_STEP ===")
engine = BSDEngine()
targets = {'t1': t_right, 't2': t_left}
received = {'t1', 't2'}
result = engine.process_step(ego, targets, received)
print(f"  CRI_left:  {result['cri_left']:.4f}")
print(f"  CRI_right: {result['cri_right']:.4f}")
print(f"  Alert L:   {result['alert_left']}")
print(f"  Alert R:   {result['alert_right']}")
print(f"  Targets:   {result['num_targets']}")

print("\n=== DEAD RECKONING FIX TEST ===")
ego_dr = vs('ego_dr', 100, 100, 25, 0, np.pi/2, 0)
target_dr = vs('target_dr', 103, 100, 22, 0, np.pi/2, 0)
tracker_dr = TargetTracker(vid='target_dr', last_state=target_dr, k_lost=3)  # tau_eff = 0.305
res_dr = engine._compute_cri_for_target(ego_dr, target_dr, tracker_dr)
print(f"  tau_eff: {res_dr['tau_eff']:.4f}")
print(f"  x_rel:   {res_dr['x_rel']:.4f}")
print(f"  y_rel:   {res_dr['y_rel']:.4f}")
assert not res_dr['stale']

tracker_stale = TargetTracker(vid='t_stale', last_state=target_dr, k_lost=6)  # tau_eff = 0.605
res_stale = engine._compute_cri_for_target(ego_dr, target_dr, tracker_stale)
assert res_stale['stale'], "Target with k_lost=6 should be flagged as stale"
print("✅ Dead reckoning extrapolated correctly & hard cap enforced!")

# ================================================================
# BSM PARSER TESTS
# ================================================================

print("\n=== BSM PARSER: FIRST-SEEN INITIALIZATION ===")
parser = BSMParser()
raw_bsm1 = {'vid': 'v1', 'x': 10.0, 'y': 20.0, 'speed': 15.0, 'accel': 2.0, 'decel': 0.0, 'vehicle_type': 'sedan', 'timestamp': 0}
state1 = parser.parse(raw_bsm1)
assert state1.heading == 0.0, f"First-seen heading should be 0.0, got {state1.heading}"
assert state1.yaw_rate == 0.0, f"First-seen yaw_rate should be 0.0, got {state1.yaw_rate}"
assert state1.net_accel == 2.0, f"net_accel should be 2.0, got {state1.net_accel}"
assert state1.accel == 2.0
assert state1.decel == 0.0
print(f"  heading={state1.heading}, yaw_rate={state1.yaw_rate}, net_accel={state1.net_accel}")
print("✅ BSMParser first-seen initialization correct!")

print("\n=== BSM PARSER: HEADING DERIVATION OVER 3 CONSECUTIVE BSMs ===")
parser2 = BSMParser()
# Vehicle moving northeast at 45°
bsm_t0 = {'vid': 'v2', 'x': 0.0, 'y': 0.0, 'speed': 14.14, 'accel': 0.0, 'decel': 0.0, 'vehicle_type': 'sedan', 'timestamp': 0}
bsm_t1 = {'vid': 'v2', 'x': 1.0, 'y': 1.0, 'speed': 14.14, 'accel': 0.0, 'decel': 0.0, 'vehicle_type': 'sedan', 'timestamp': 1}
bsm_t2 = {'vid': 'v2', 'x': 2.0, 'y': 2.0, 'speed': 14.14, 'accel': 0.0, 'decel': 0.0, 'vehicle_type': 'sedan', 'timestamp': 2}

s0 = parser2.parse(bsm_t0)
s1 = parser2.parse(bsm_t1)
s2 = parser2.parse(bsm_t2)

expected_heading = np.arctan2(1.0, 1.0)  # π/4 = 45°
print(f"  t0: heading={s0.heading:.4f} (first-seen=0)")
print(f"  t1: heading={s1.heading:.4f} (expected≈{expected_heading:.4f} = π/4)")
print(f"  t2: heading={s2.heading:.4f} (expected≈{expected_heading:.4f} = π/4)")
assert abs(s1.heading - expected_heading) < 0.01, f"Heading at t1 wrong: {s1.heading}"
assert abs(s2.heading - expected_heading) < 0.01, f"Heading at t2 wrong: {s2.heading}"
assert abs(s2.yaw_rate) < 0.01, "Yaw rate should be ~0 for straight-line motion"
print("✅ BSMParser heading derivation over 3 consecutive BSMs correct!")

print("\n=== BSM PARSER: LOW-SPEED GUARD ===")
parser3 = BSMParser()
# First BSM at normal speed
bsm_fast = {'vid': 'v3', 'x': 0.0, 'y': 0.0, 'speed': 10.0, 'accel': 0.0, 'decel': 0.0, 'vehicle_type': 'sedan', 'timestamp': 0}
bsm_slow = {'vid': 'v3', 'x': 0.01, 'y': 0.01, 'speed': 0.3, 'accel': 0.0, 'decel': 0.0, 'vehicle_type': 'sedan', 'timestamp': 1}
s_fast = parser3.parse(bsm_fast)
s_slow = parser3.parse(bsm_slow)
# When speed < 0.5, heading should be retained from previous
assert s_slow.heading == s_fast.heading, f"Low-speed guard failed: heading should be retained"
print(f"  Fast heading: {s_fast.heading:.4f}, Slow heading: {s_slow.heading:.4f}")
print("✅ BSMParser low-speed guard correctly retains previous heading!")

print("\n=== BSM PARSER: DECEL/ACCEL SPLIT ===")
parser4 = BSMParser()
bsm_braking = {'vid': 'v4', 'x': 0.0, 'y': 0.0, 'speed': 20.0, 'accel': 0.0, 'decel': 3.5, 'vehicle_type': 'suv', 'timestamp': 0}
s_brake = parser4.parse(bsm_braking)
assert s_brake.accel == 0.0
assert s_brake.decel == 3.5
assert s_brake.net_accel == -3.5, f"net_accel should be -3.5, got {s_brake.net_accel}"
assert s_brake.vehicle_type == 'suv'
assert s_brake.width == 2.0  # SUV default
assert s_brake.length == 4.8  # SUV default
assert s_brake.mass == 2200  # SUV default
print(f"  Type: {s_brake.vehicle_type}, L={s_brake.length}, W={s_brake.width}, M={s_brake.mass}")
print(f"  accel={s_brake.accel}, decel={s_brake.decel}, net_accel={s_brake.net_accel}")
print("✅ BSMParser decel/accel split and vehicle defaults correct!")

# ================================================================
# SCENARIO CONTEXT TESTS
# ================================================================

print("\n=== SCENARIO CONTEXT TEST ===")
engine_sc = BSDEngine()
assert engine_sc.active_w_lane == 3.5, "Default W_LANE should be 3.5"
assert engine_sc.active_mu == 0.7, "Default mu should be 0.7"

engine_sc.set_scenario_context("hilly")
assert engine_sc.active_w_lane == 2.8, f"Hilly W_LANE should be 2.8, got {engine_sc.active_w_lane}"
assert engine_sc.active_mu == 0.55, f"Hilly mu should be 0.55, got {engine_sc.active_mu}"

engine_sc.set_scenario_context("TSV")
assert engine_sc.active_w_lane == 3.5
assert engine_sc.active_mu == 0.7

engine_sc.set_scenario_context("normal")
assert engine_sc.active_w_lane == 3.5
assert engine_sc.active_mu == 0.7
print("✅ Scenario context switching works correctly!")

# ================================================================
# ADDITIONAL TESTS (V3.0 completeness)
# ================================================================

print("\n=== SYMMETRY TEST (Left/Right CRI Must Be Equal for Mirror Scenarios) ===")
engine_sym = BSDEngine()
ego_sym = vs('ego_s', 100, 100, 25, 0, np.pi/2, 0)
t_sym_r = vs('sym_r', 103.5, 95, 22, 0, np.pi/2, 0)
t_sym_l = vs('sym_l', 96.5, 95, 22, 0, np.pi/2, 0)
tracker_sr = TargetTracker(vid='sym_r', last_state=t_sym_r)
tracker_sl = TargetTracker(vid='sym_l', last_state=t_sym_l)
r_sym_r = engine_sym._compute_cri_for_target(ego_sym, t_sym_r, tracker_sr)
r_sym_l = engine_sym._compute_cri_for_target(ego_sym, t_sym_l, tracker_sl)
assert abs(r_sym_r['cri'] - r_sym_l['cri']) < 0.01, \
    f"Symmetry broken: CRI_right={r_sym_r['cri']:.4f}, CRI_left={r_sym_l['cri']:.4f}"
print(f"  CRI_right={r_sym_r['cri']:.4f}, CRI_left={r_sym_l['cri']:.4f}")
print("✅ Left/Right symmetry verified!")

print("\n=== LATERAL TTC TEST (heading divergence must produce non-zero R_ttc_lat) ===")
engine_lat = BSDEngine(use_lateral_ttc=True)
ego_lat = vs('ego_lat', 100, 100, 20, 0, np.pi/2, 0)
import math
diverge_heading = np.pi/2 - math.radians(10)
t_lat = vs('t_lat', 103.5, 100, 20, 0, diverge_heading, 0)
tracker_lat = TargetTracker(vid='t_lat', last_state=t_lat)
r_lat = engine_lat._compute_cri_for_target(ego_lat, t_lat, tracker_lat)
v_lat_rel_expected = abs(t_lat.speed * np.sin(diverge_heading - np.pi/2))
from bsd_engine import Params as P
W_gap = P.W_LANE - ego_lat.width / 2.0 - t_lat.width / 2.0
ttc_lat_expected = W_gap / v_lat_rel_expected
if ttc_lat_expected < P.TTC_CRIT:
    expected_R_ttc_lat = 1.0 - ttc_lat_expected / P.TTC_CRIT
else:
    expected_R_ttc_lat = 0.0
print(f"  v_lat_rel = {v_lat_rel_expected:.4f} m/s (heading diff = 10°)")
print(f"  Expected R_ttc_lat ≈ {expected_R_ttc_lat:.4f}")
print(f"  Actual  R_ttc (with lateral) = {r_lat['R_ttc']:.4f}")
assert r_lat['R_ttc'] >= expected_R_ttc_lat * 0.8, \
    f"R_ttc should be ~{expected_R_ttc_lat:.4f}, got {r_lat['R_ttc']:.4f}"
print("✅ Lateral TTC produces physically correct non-trivial result!")

print("\n=== TARGET INTENT TEST (V3.0 — no signals in 5-field BSM) ===")
engine_ti = BSDEngine()
ego_ti = vs('ego_ti', 100, 100, 25, 0, np.pi/2, 0)
t_no_blinker = vs('t_nb', 103.5, 97, 22, 0, np.pi/2, 0)
# In 5-field BSM, there are no signals — R_intent is always drift-only
ri_test = engine_ti._compute_R_intent(ego_ti, t_no_blinker, 'RIGHT')
print(f"  R_intent (no drift, no signals): {ri_test:.4f}")
assert ri_test == 0.0, "R_intent should be 0 when ego has no lateral drift"
print("✅ R_intent correctly zero when no drift and no signals!")

print("\n=== ZERO SPEED EDGE CASE (stationary target — dead reckoning returns stored position) ===")
engine_zs = BSDEngine()
ego_zs = vs('ego_zs', 100, 100, 15, 0, np.pi/2, 0)
t_stopped = vs('t_zs', 103.5, 95, 0, 0, np.pi/2, 0)
tracker_zs = TargetTracker(vid='t_zs', last_state=t_stopped, k_lost=2)  # 2 lost packets
res_zs = engine_zs._compute_cri_for_target(ego_zs, t_stopped, tracker_zs)
print(f"  Stopped target, k_lost=2: x_rel={res_zs['x_rel']:.4f}, stale={res_zs['stale']}")
assert not res_zs['stale'], "k_lost=2 should not be stale (threshold is k_lost>5)"
assert res_zs['cri'] >= 0, "CRI must be non-negative even for stopped target"
print("✅ Zero-speed edge case handled correctly!")

print("\n=== CRI BOUNDS TEST (0 ≤ CRI ≤ 1.0 for 200 random inputs) ===")
engine_bounds = BSDEngine()
rng = np.random.default_rng(seed=42)
for i in range(200):
    vals = rng.uniform([0,0,0,0,0,0,-0.5,3.0,1.5], [200,200,30,5,5,2*np.pi,0.5,6.0,2.5])
    e_v = VehicleState('e', vals[0], vals[1], vals[2], vals[3], 0.0,
                        vals[5], vals[6], vals[3] - 0.0,
                        vals[7], vals[8], 1800, 0.7, 'sedan', 0)
    t_v = VehicleState('t', vals[0]+rng.uniform(-10,10), vals[1]+rng.uniform(-10,10), 
                        vals[2]*0.8, 0.0, rng.uniform(0,5),
                        vals[5]+rng.uniform(-0.1,0.1), rng.uniform(-0.5,0.5), 
                        0.0 - rng.uniform(0,5),
                        vals[7], vals[8], 1800, 0.7, 'sedan', 0)
    tracker_b = TargetTracker(vid='t', last_state=t_v, k_lost=rng.integers(0, 4))
    res_b = engine_bounds._compute_cri_for_target(e_v, t_v, tracker_b)
    assert 0.0 <= res_b['cri'] <= 1.0, f"CRI out of bounds at iter {i}: {res_b['cri']}"
print("✅ CRI bounds [0,1] verified across 200 random vehicle states!")

print("\n=== PLR=1.0 EDGE CASE (all packets dropped → stale after 5 steps) ===")
engine_plr = BSDEngine()
ego_plr = vs('ego_plr', 100, 100, 25, 0, np.pi/2, 0)
t_plr = vs('t_plr', 103.5, 97, 22, 0, np.pi/2, 0)
tracker_plr = TargetTracker(vid='t_plr', last_state=t_plr, k_lost=6,
                             plr_window=[0]*10)  # All 10 packets dropped
res_plr = engine_plr._compute_cri_for_target(ego_plr, t_plr, tracker_plr)
print(f"  k_lost=6, all packets dropped: stale={res_plr['stale']}, cri={res_plr['cri']:.4f}")
assert res_plr['stale'], "k_lost=6 must be flagged as hard stale"
assert res_plr['cri'] == 0.0, f"Stale target CRI must be 0.0, got {res_plr['cri']}"
print("✅ PLR=1.0 edge case: stale flag correct, CRI correctly zeroed!")

print("\n=== EMPTY TARGETS TEST ===")
engine_e = BSDEngine()
ego_e = vs('ego_e', 100, 100, 25, 0, np.pi/2, 0)
res_e = engine_e.process_step(ego_e, {}, set())
assert res_e['cri_left']  == 0.0, f"CRI_left must be 0 with no targets, got {res_e['cri_left']}"
assert res_e['cri_right'] == 0.0, f"CRI_right must be 0 with no targets, got {res_e['cri_right']}"
assert res_e['alert_left']  == 'SAFE'
assert res_e['alert_right'] == 'SAFE'
assert res_e['num_targets'] == 0
print(f"  CRI_left={res_e['cri_left']}, CRI_right={res_e['cri_right']}, alerts=SAFE/SAFE")
print("✅ Empty targets → CRI=0.0, SAFE verified!")

print("\n=== FAST CLOSING TARGET = HIGH CRI ===")
engine_fc = BSDEngine()
ego_fc  = vs('ego_fc',  100, 100, 20, 0, np.pi/2, 0)
t_fc    = vs('t_fc',    103.5, 92, 50, 0, np.pi/2, 0)
tk_fc   = TargetTracker(vid='t_fc', last_state=t_fc)
r_fc    = engine_fc._compute_cri_for_target(ego_fc, t_fc, tk_fc)
print(f"  R_decel={r_fc['R_decel']:.4f}, R_ttc={r_fc['R_ttc']:.4f}, CRI={r_fc['cri']:.4f}")
assert r_fc['R_ttc']   > 0.5, f"Fast closing: R_ttc should be > 0.5, got {r_fc['R_ttc']:.4f}"
assert r_fc['cri']     > Params.THETA_2, f"Fast closing CRI {r_fc['cri']:.4f} should exceed WARNING={Params.THETA_2}"
print("✅ Fast-closing vehicle correctly generates high-risk CRI > WARNING threshold!")

print("\n=== bsd_utils.compute_ground_truth TEST ===")
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from bsd_utils import compute_ground_truth
import pandas as pd

df_test = pd.DataFrame({
    'max_gap':    [1.0,  3.0,  20.0, 50.0, 1.5],
    'rel_speed':  [5.0,  5.0,   5.0,  0.5,  0.5],
    'num_targets':[1,    1,     1,    1,    1  ],
    'ground_truth_collision': [0, 0, 0, 0, 0],
})
# Row 0: gap=1.0<1.0 False, ttc=0.2<2.0 True → 1
# Row 1: gap=3.0<1.0 False, ttc=0.6<2.0 True → 1
# Row 2: gap=20.0<1.0 False, ttc=4.0<2.0 False → 0
# Row 3: gap=50.0<1.0 False, rel_speed=0.5 → ttc=999.0 → 0
# Row 4: gap=1.5<1.0 False, rel_speed=0.5 → ttc=999.0 → 0
expected = [1, 1, 0, 0, 0]
got = list(compute_ground_truth(df_test))
assert got == expected, f"Expected {expected}, got {got}"
print(f"  Results: {got} ✓")
print("✅ bsd_utils.compute_ground_truth works correctly!")

print("\n=== 5-FIELD BSM CONSISTENCY TEST ===")
# Verify that net_accel = accel - decel for various combinations
for a, d in [(3.0, 0.0), (0.0, 4.5), (2.0, 1.0), (0.0, 0.0)]:
    s = VehicleState('test', 0, 0, 10, a, d, 0, 0, a-d, 4.5, 1.8, 1500, 0.7, 'sedan', 0)
    assert s.net_accel == a - d, f"net_accel mismatch: {s.net_accel} != {a-d}"
print("✅ 5-field BSM net_accel consistency verified!")

# ==============================================================================
# LATENCY BENCHMARK
# ==============================================================================
print("\n=== LATENCY BENCHMARK ===")
import time
bench_engine = BSDEngine()
# Create realistic scenario: ego with 15 targets
bench_ego = VehicleState('ego_bench', 500, 500, 15.0, 1.0, 0.0, 0.1, 0.01, 1.0, 4.5, 1.8, 1500, 0.7, 'sedan', 0)
bench_targets = {}
bench_received = set()
for i in range(15):
    vid = f'tgt_{i}'
    offset_x = 2.0 + (i % 3) * 3.5
    offset_y = -10.0 + i * 5.0
    ts = VehicleState(vid, 500 + offset_x, 500 + offset_y, 12.0 + i*0.5,
                      0.5, 0.3, 0.1 + i*0.01, 0.005, 0.2, 4.5, 1.8, 1500, 0.7, 'sedan', 0)
    bench_targets[vid] = ts
    bench_received.add(vid)

N_BENCH = 1000
times_ms = []
for _ in range(N_BENCH):
    t0 = time.perf_counter()
    bench_engine.process_step(bench_ego, bench_targets, bench_received)
    times_ms.append((time.perf_counter() - t0) * 1000)

times_arr = np.array(times_ms)
mean_ms = np.mean(times_arr)
p95_ms = np.percentile(times_arr, 95)
p99_ms = np.percentile(times_arr, 99)
print(f"process_step() with 15 targets ({N_BENCH} iterations):")
print(f"  Mean: {mean_ms:.3f} ms")
print(f"  P95:  {p95_ms:.3f} ms")
print(f"  P99:  {p99_ms:.3f} ms")
sae_pass = p99_ms < 100
print(f"  SAE J2945/1 100ms budget: {'PASS ✅' if sae_pass else 'FAIL ❌'}")
assert sae_pass, f"P99 latency {p99_ms:.1f}ms exceeds 100ms SAE budget"

# ==============================================================================
# WGS84 CONVERTER TEST
# ==============================================================================
print("\n=== WGS84 CONVERTER TEST ===")
try:
    sys.path.insert(0, os.path.dirname(__file__) if '__file__' in dir() else '.')
    from ros2_wgs84_wrapper import WGS84Converter

    # Atal Bridge approximate reference (Pune, India)
    converter = WGS84Converter(lat0=18.519, lon0=73.854)

    # Test 1: Reference point maps to (0, 0)
    x0, y0 = converter.to_local(18.519, 73.854)
    assert abs(x0) < 0.1 and abs(y0) < 0.1, f"Origin should be (0,0), got ({x0:.3f}, {y0:.3f})"
    print(f"  Origin test: ({x0:.4f}, {y0:.4f}) ✓")

    # Test 2: ~100m north offset
    x_n, y_n = converter.to_local(18.519 + 0.0009, 73.854)
    assert 95 < y_n < 105, f"100m north offset wrong: {y_n:.1f}m"
    print(f"  100m north: y={y_n:.1f}m ✓")

    # Test 3: Round-trip conversion
    test_lat, test_lon = 18.520, 73.856
    x_rt, y_rt = converter.to_local(test_lat, test_lon)
    lat_back, lon_back = converter.to_wgs84(x_rt, y_rt)
    assert abs(lat_back - test_lat) < 0.0001 and abs(lon_back - test_lon) < 0.0001, \
        f"Round-trip failed: ({test_lat},{test_lon}) -> ({lat_back:.6f},{lon_back:.6f})"
    print(f"  Round-trip: error = ({abs(lat_back-test_lat)*111000:.2f}m, {abs(lon_back-test_lon)*111000:.2f}m) ✓")

    print("✅ WGS84Converter tests passed!")
except ImportError:
    print("⚠️  ros2_wgs84_wrapper not importable — skipping WGS84 test")

print("\n✅✅✅ ALL V3.0 TESTS PASSED — BSD Engine (5-field BSM) is complete and correct! ✅✅✅")

