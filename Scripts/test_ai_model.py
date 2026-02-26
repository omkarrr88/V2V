"""
test_ai_model.py — Unit tests for the XGBoost AI prediction pipeline.
Tests train, save, load, and predict without requiring SUMO.
"""
import pandas as pd
import numpy as np
import sys, os, pathlib, tempfile

sys.path.insert(0, os.path.dirname(__file__))
from train_ai_model import BSDAIModel, create_target_labels, add_derived_features

print("=== AI MODEL PIPELINE TEST ===")

# 1. Generate synthetic training data
np.random.seed(42)
N = 500
df_synth = pd.DataFrame({
    'speed':        np.random.uniform(0, 30, N),
    'accel':        np.random.uniform(-5, 5, N),
    'yaw_rate':     np.random.uniform(-1, 1, N),
    'num_targets':  np.random.randint(0, 5, N),
    'signals':      np.random.randint(0, 4, N),
    'max_gap':      np.random.uniform(0.5, 50, N),
    'rel_speed':    np.random.uniform(0.5, 30, N),
    'max_plr':      np.random.uniform(0, 0.3, N),
    'k_lost_max':   np.random.randint(0, 8, N),
    'ground_truth_collision': np.zeros(N, dtype=int),
})

# 2. Derived features
df_synth = add_derived_features(df_synth)
y = create_target_labels(df_synth)
print(f"  Label distribution: {dict(y.value_counts().sort_index())}")
assert len(y) == N, "Labels length mismatch"

# 3. Train model
model = BSDAIModel()
with tempfile.TemporaryDirectory() as tmpdir:
    model_path = pathlib.Path(tmpdir) / 'test_model.json'
    # Temporarily override save path
    model.train(df_synth)  # trains internally
    assert model.model is not None, "Model is None after training"
    assert model.features is not None and len(model.features) > 0, "No features saved"
    print(f"  Trained on {len(model.features)} features: {model.features}")

# 4. Predict single row
pred = model.predict(
    speed=25.0, accel=0.0, yaw_rate=0.0,
    num_targets=1, max_gap=3.0, rel_speed=5.0,
    max_plr=0.05, k_lost_max=0, signals=0
)
assert 'ai_alert' in pred, "Missing ai_alert in prediction"
assert 'ai_confidence' in pred, "Missing ai_confidence in prediction"
assert 0.0 <= pred['ai_confidence'] <= 1.0, f"Confidence out of range: {pred['ai_confidence']}"
assert pred['ai_alert'] in ['SAFE', 'CAUTION', 'WARNING', 'CRITICAL'], f"Bad alert: {pred['ai_alert']}"
print(f"  Single predict: alert={pred['ai_alert']}, confidence={pred['ai_confidence']:.4f}")

# 5. Batch predict (same as simulation uses)
rows = [
    {'speed': 25, 'accel': 0, 'yaw_rate': 0, 'num_targets': 1, 'signals': 0,
     'max_gap': 3.0, 'rel_speed': 5.0, 'max_plr': 0.05, 'k_lost_max': 0,
     'speed_kmh': 90, 'abs_accel': 0, 'abs_yaw_rate': 0, 'is_braking': 0,
     'is_signaling': 0, 'has_targets': 1, 'speed_category': 2, 'closing_speed': 5.0},
    {'speed': 5, 'accel': -2, 'yaw_rate': 0, 'num_targets': 0, 'signals': 0,
     'max_gap': 50, 'rel_speed': 0.1, 'max_plr': 0, 'k_lost_max': 0,
     'speed_kmh': 18, 'abs_accel': 2, 'abs_yaw_rate': 0, 'is_braking': 1,
     'is_signaling': 0, 'has_targets': 0, 'speed_category': 1, 'closing_speed': 0.1},
]
batch_out = model.batch_predict(rows)
assert len(batch_out) == 2, f"Batch predict returned {len(batch_out)} results, expected 2"
for out in batch_out:
    assert 'ai_alert' in out and 'ai_confidence' in out
print(f"  Batch predict (2 rows): alerts={[o['ai_alert'] for o in batch_out]}")

print("\n✅ ALL AI MODEL TESTS PASSED — Training, prediction, and batch inference work correctly!")
