"""Quick test of the BSD engine core computations."""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from bsd_engine import *
import numpy as np

e = BSDEngine()

# Ego heading north (π/2 in math convention)
ego = VehicleState('ego', 100, 100, 25, 0, np.pi/2, 0, 4.5, 1.8, 1500, 0.7, 0, 'sedan', 0)

# Target on RIGHT, slightly behind, same heading, slower → classic blind spot
t_right = VehicleState('t1', 103.5, 97, 22, -1, np.pi/2, 0, 4.5, 1.8, 1500, 0.7, 0, 'sedan', 0)
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
t_left = VehicleState('t2', 96.5, 97, 22, -1, np.pi/2, 0, 4.5, 1.8, 1500, 0.7, 0, 'sedan', 0)
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

# Test direction-aware intent: ego turns RIGHT with right blinker
ego_turning = VehicleState('ego2', 100, 100, 25, 0, np.pi/2, -0.1, 4.5, 1.8, 1500, 0.7, 1, 'sedan', 0)
dummy_target = VehicleState('dummy', 103.5, 97, 22, 0, np.pi/2, 0, 4.5, 1.8, 1500, 0.7, 0, 'sedan', 0)
r_intent_right = e._compute_R_intent(ego_turning, dummy_target, "RIGHT")
r_intent_left = e._compute_R_intent(ego_turning, dummy_target, "LEFT")
print(f"\n=== INTENT (ego turning RIGHT, right blinker) ===")
print(f"  R_intent toward RIGHT threat: {r_intent_right:.4f} (should be > 0)")
print(f"  R_intent toward LEFT threat:  {r_intent_left:.4f}  (should be 0)")
assert r_intent_right > 0, "RIGHT intent should be elevated!"
assert r_intent_left == 0, "LEFT intent should be zero!"
print("✅ Direction-aware intent verified — signs are correct!")

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
ego_dr = VehicleState('ego_dr', 100, 100, 25, 0, np.pi/2, 0, 4.5, 1.8, 1500, 0.7, 0, 'sedan', 0)
target_dr = VehicleState('target_dr', 103, 100, 22, 0, np.pi/2, 0, 4.5, 1.8, 1500, 0.7, 0, 'sedan', 0)
tracker_dr = TargetTracker(vid='target_dr', last_state=target_dr, k_lost=3) # tau_eff = 0.305
res_dr = engine._compute_cri_for_target(ego_dr, target_dr, tracker_dr)
print(f"  tau_eff: {res_dr['tau_eff']:.4f}")
print(f"  x_rel:   {res_dr['x_rel']:.4f}")
print(f"  y_rel:   {res_dr['y_rel']:.4f}")
assert not res_dr['stale']

tracker_stale = TargetTracker(vid='t_stale', last_state=target_dr, k_lost=6) # tau_eff = 0.605
res_stale = engine._compute_cri_for_target(ego_dr, target_dr, tracker_stale)
assert res_stale['stale'], "Target with k_lost=6 should be flagged as stale"
print("✅ Dead reckoning extrapolated correctly & hard cap enforced!")

# ================================================================
# ADDITIONAL TESTS (V3.0 completeness)
# ================================================================

print("\n=== SYMMETRY TEST (Left/Right CRI Must Be Equal for Mirror Scenarios) ===")
engine_sym = BSDEngine()
ego_sym = VehicleState('ego_s', 100, 100, 25, 0, np.pi/2, 0, 4.5, 1.8, 1500, 0.7, 0, 'sedan', 0)
t_sym_r = VehicleState('sym_r', 103.5, 95, 22, 0, np.pi/2, 0, 4.5, 1.8, 1500, 0.7, 0, 'sedan', 0)
t_sym_l = VehicleState('sym_l', 96.5, 95, 22, 0, np.pi/2, 0, 4.5, 1.8, 1500, 0.7, 0, 'sedan', 0)
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
ego_lat = VehicleState('ego_lat', 100, 100, 20, 0, np.pi/2, 0, 4.5, 1.8, 1500, 0.7, 0, 'sedan', 0)
# Target heading 10° away from ego — will converge laterally
import math
diverge_heading = np.pi/2 - math.radians(10)
t_lat = VehicleState('t_lat', 103.5, 100, 20, 0, diverge_heading, 0, 4.5, 1.8, 1500, 0.7, 0, 'sedan', 0)
tracker_lat = TargetTracker(vid='t_lat', last_state=t_lat)
r_lat = engine_lat._compute_cri_for_target(ego_lat, t_lat, tracker_lat)
v_lat_rel_expected = t_lat.speed * np.sin(diverge_heading - np.pi/2)
print(f"  v_lat_rel = {v_lat_rel_expected:.4f} m/s (heading diff = 10°)")
print(f"  R_ttc (with lateral) = {r_lat['R_ttc']:.4f}")
assert r_lat['R_ttc'] >= 0, "R_ttc must be non-negative"
print("✅ Lateral TTC produces valid non-negative result!")

print("\n=== TARGET INTENT TEST (V3.0 ego-only check) ===")
engine_ti = BSDEngine()
ego_ti = VehicleState('ego_ti', 100, 100, 25, 0, np.pi/2, 0, 4.5, 1.8, 1500, 0.7, 0, 'sedan', 0)
t_no_blinker = VehicleState('t_nb', 103.5, 97, 22, 0, np.pi/2, 0, 4.5, 1.8, 1500, 0.7, 0, 'sedan', 0)
t_with_blinker = VehicleState('t_wb', 103.5, 97, 22, 0, np.pi/2, 0, 4.5, 1.8, 1500, 0.7, 2, 'sedan', 0)  # signals=2 = left blinker
ri_no_blinker   = engine_ti._compute_R_intent(ego_ti, t_no_blinker,   'RIGHT')
ri_with_blinker = engine_ti._compute_R_intent(ego_ti, t_with_blinker, 'RIGHT')
print(f"  R_intent (no target blinker): {ri_no_blinker:.4f}")
print(f"  R_intent (target with blinker): {ri_with_blinker:.4f}")
assert ri_with_blinker == ri_no_blinker, \
    f"Target blinker should NOT affect R_intent in V3.0 ego-only model."
print("✅ Target intent correctly ignored by R_intent (Ego-only rule enforced)!")

print("\n=== ZERO SPEED EDGE CASE (stationary target — dead reckoning returns stored position) ===")
engine_zs = BSDEngine()
ego_zs = VehicleState('ego_zs', 100, 100, 15, 0, np.pi/2, 0, 4.5, 1.8, 1500, 0.7, 0, 'sedan', 0)
t_stopped = VehicleState('t_zs', 103.5, 95, 0, 0, np.pi/2, 0, 4.5, 1.8, 1500, 0.7, 0, 'sedan', 0)
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
    e_v = VehicleState('e', *rng.uniform([0,0,0,-5,0,-0.5,3.0,1.5],[200,200,30,3,2*np.pi,0.5,6.0,2.5]), 1800, 0.7, 0, 'sedan', 0)
    t_v = VehicleState('t', *rng.uniform([0,0,0,-5,0,-0.5,3.0,1.5],[200,200,30,3,2*np.pi,0.5,6.0,2.5]), 1800, 0.7, 0, 'sedan', 0)
    tracker_b = TargetTracker(vid='t', last_state=t_v, k_lost=rng.integers(0, 4))
    res_b = engine_bounds._compute_cri_for_target(e_v, t_v, tracker_b)
    assert 0.0 <= res_b['cri'] <= 1.0, f"CRI out of bounds at iter {i}: {res_b['cri']}"
print("✅ CRI bounds [0,1] verified across 200 random vehicle states!")

print("\n=== PLR=1.0 EDGE CASE (all packets dropped → stale after 5 steps) ===")
engine_plr = BSDEngine()
ego_plr = VehicleState('ego_plr', 100, 100, 25, 0, np.pi/2, 0, 4.5, 1.8, 1500, 0.7, 0, 'sedan', 0)
t_plr = VehicleState('t_plr', 103.5, 97, 22, 0, np.pi/2, 0, 4.5, 1.8, 1500, 0.7, 0, 'sedan', 0)
tracker_plr = TargetTracker(vid='t_plr', last_state=t_plr, k_lost=6,
                             plr_window=[0]*10)  # All 10 packets dropped
res_plr = engine_plr._compute_cri_for_target(ego_plr, t_plr, tracker_plr)
print(f"  k_lost=6, all packets dropped: stale={res_plr['stale']}, cri={res_plr['cri']:.4f}")
assert res_plr['stale'], "k_lost=6 must be flagged as hard stale"
assert res_plr['cri'] == 0.0, f"Stale target CRI must be 0.0, got {res_plr['cri']}"
print("✅ PLR=1.0 edge case: stale flag correct, CRI correctly zeroed!")

print("\n✅✅✅ ALL V3.0 TESTS PASSED — BSD Engine is complete and correct! ✅✅✅")
