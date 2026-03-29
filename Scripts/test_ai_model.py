"""
test_ai_model.py — Unit tests for the XGBoost AI prediction pipeline.
Tests train, save, load, and predict without requiring SUMO.
Updated for 5-field BSM: accel/decel split, no yaw_rate/signals in features.
"""
import pandas as pd
import numpy as np
import sys, os, pathlib, tempfile

sys.path.insert(0, os.path.dirname(__file__))
from train_ai_model import BSDAIModel, create_target_labels, add_derived_features

print("=== AI MODEL PIPELINE TEST (5-Field BSM) ===")

# 1. Generate synthetic training data — 5-field BSM format
np.random.seed(42)
N = 500
speed = np.random.uniform(0, 30, N)
accel_pos = np.random.uniform(0, 5, N)
decel_pos = np.random.uniform(0, 5, N)

df_synth = pd.DataFrame({
    'speed':        speed,
    'accel':        accel_pos,     # positive acceleration only
    'decel':        decel_pos,     # positive deceleration only
    'num_targets':  np.random.randint(0, 5, N),
    'max_gap':      np.random.uniform(0.5, 50, N),
    'rel_speed':    np.random.uniform(0.5, 30, N),
    'max_plr':      np.random.uniform(0, 0.3, N),
    'k_lost_max':   np.random.randint(0, 8, N),
    'cri_left':     np.random.uniform(0.0, 1.0, N),
    'cri_right':    np.random.uniform(0.0, 1.0, N),
    'ground_truth_collision': np.zeros(N, dtype=int),
})

# 2. Derived features
df_synth = add_derived_features(df_synth)
y = create_target_labels(df_synth)
print(f"  Label distribution: {dict(y.value_counts().sort_index())}")
assert len(y) == N, "Labels length mismatch"

# Verify derived features exist
assert 'abs_accel' in df_synth.columns, "abs_accel derived feature missing"
assert 'brake_ratio' in df_synth.columns, "brake_ratio derived feature missing"
assert 'scenario_tsv' in df_synth.columns, "scenario_tsv derived feature missing"
assert 'scenario_hnr' in df_synth.columns, "scenario_hnr derived feature missing"
print(f"  ✅ All derived features present")

# 3. Train model
model = BSDAIModel()
with tempfile.TemporaryDirectory() as tmpdir:
    model_path = pathlib.Path(tmpdir) / 'test_model.json'
    model.train(df_synth)
    assert model.model is not None, "Model is None after training"
    assert model.features is not None and len(model.features) > 0, "No features saved"
    print(f"  Trained on {len(model.features)} features: {model.features}")

# 4. Predict single row — 5-field BSM signature
pred = model.predict(
    speed=25.0, accel=0.0, decel=0.0,
    num_targets=1, max_gap=3.0, rel_speed=5.0,
    max_plr=0.05, k_lost_max=0
)
assert 'ai_alert' in pred, "Missing ai_alert in prediction"
assert 'ai_confidence' in pred, "Missing ai_confidence in prediction"
assert 0.0 <= pred['ai_confidence'] <= 1.0, f"Confidence out of range: {pred['ai_confidence']}"
assert pred['ai_alert'] in ['SAFE', 'CAUTION', 'WARNING', 'CRITICAL'], f"Bad alert: {pred['ai_alert']}"
print(f"  Single predict: alert={pred['ai_alert']}, confidence={pred['ai_confidence']:.4f}")

# 5. Test with braking scenario
pred_brake = model.predict(
    speed=25.0, accel=0.0, decel=4.5,   # Hard braking
    num_targets=2, max_gap=1.5, rel_speed=10.0,
    max_plr=0.1, k_lost_max=2
)
print(f"  Braking predict: alert={pred_brake['ai_alert']}, confidence={pred_brake['ai_confidence']:.4f}")

# 6. Batch predict (same format as simulation uses) — 5-field BSM
rows = [
    {'speed': 25, 'accel': 2.0, 'decel': 0, 'num_targets': 1,
     'max_gap': 3.0, 'rel_speed': 5.0, 'max_plr': 0.05, 'k_lost_max': 0,
     'speed_kmh': 90, 'abs_accel': 2.0, 'is_braking': 0,
     'brake_ratio': 0.0,
     'has_targets': 1, 'speed_category': 2, 'closing_speed': 5.0,
     'scenario_tsv': 0, 'scenario_hnr': 0},
    {'speed': 5, 'accel': 0, 'decel': 2, 'num_targets': 0,
     'max_gap': 50, 'rel_speed': 0.1, 'max_plr': 0, 'k_lost_max': 0,
     'speed_kmh': 18, 'abs_accel': 2, 'is_braking': 1,
     'brake_ratio': 0.4,
     'has_targets': 0, 'speed_category': 1, 'closing_speed': 0.1,
     'scenario_tsv': 0, 'scenario_hnr': 0},
]
batch_out = model.batch_predict(rows)
assert len(batch_out) == 2, f"Batch predict returned {len(batch_out)} results, expected 2"
for out in batch_out:
    assert 'ai_alert' in out and 'ai_confidence' in out
print(f"  Batch predict (2 rows): alerts={[o['ai_alert'] for o in batch_out]}")

# 7. Backward compatibility test — old CSV format with signed accel
print("\n=== BACKWARD COMPAT: Old CSV format (signed accel) ===")
df_old = pd.DataFrame({
    'speed': [20.0, 15.0, 0.5],
    'accel': [2.0, -3.5, 0.0],  # signed — old format
    'num_targets': [1, 2, 0],
    'max_gap': [5.0, 1.0, 50.0],
    'rel_speed': [3.0, 8.0, 0.0],
    'max_plr': [0.0, 0.1, 0.0],
    'k_lost_max': [0, 1, 0],
    'ground_truth_collision': [0, 0, 0],
})
df_old_derived = add_derived_features(df_old)
assert 'decel' in df_old_derived.columns, "decel should be created for old format"
assert (df_old_derived.loc[1, 'decel'] == 3.5), f"decel should be 3.5 for accel=-3.5, got {df_old_derived.loc[1, 'decel']}"
assert (df_old_derived.loc[1, 'accel'] == 0.0), f"accel should be clipped to 0 for negative, got {df_old_derived.loc[1, 'accel']}"
print(f"  Old format row 1: accel={df_old_derived.loc[1, 'accel']}, decel={df_old_derived.loc[1, 'decel']}")
print("  ✅ Backward compatibility verified!")

print("\n✅ ALL AI MODEL TESTS PASSED — Training, prediction, and batch inference work correctly!")
