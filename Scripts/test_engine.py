"""Quick test of the BSD engine core computations."""
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
r_intent_right = e._compute_R_intent(ego_turning, "RIGHT")
r_intent_left = e._compute_R_intent(ego_turning, "LEFT")
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

print("\n✅ ALL TESTS PASSED! BSD Engine V2.4 is working correctly.")
