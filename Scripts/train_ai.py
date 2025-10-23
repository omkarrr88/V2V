# ============================================================
# V2V Accident Prevention System - AI Model Training Script
# ============================================================
# This script trains a Random Forest Classifier to predict
# collision risk based on vehicle dynamics
# ============================================================

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import pandas as pd
import numpy as np
import joblib
import os

print("🤖 V2V AI Model Training Started...")
print("=" * 60)

# Create output directory
os.makedirs("../Outputs", exist_ok=True)

# ============================================================
# STEP 1: Generate Synthetic Training Data
# ============================================================
print("\n📊 Step 1: Generating training data...")

np.random.seed(42)
n_samples = 10000

# Generate features
data = pd.DataFrame({
    'speed_a': np.random.uniform(50, 120, n_samples),      # Speed of vehicle A (km/h)
    'speed_b': np.random.uniform(50, 120, n_samples),      # Speed of vehicle B (km/h)
    'dist': np.random.uniform(5, 300, n_samples),          # Distance between vehicles (m)
    'decel_a': np.random.uniform(3, 10, n_samples),        # Deceleration capability A (m/s²)
    'decel_b': np.random.uniform(3, 10, n_samples)         # Deceleration capability B (m/s²)
})

# Create collision labels based on physics-inspired formula
# High risk when: high speeds, low distance, low deceleration
data['collision'] = (
    (120 - data['speed_a']) / 70 + 
    data['decel_a'] / 5 + 
    (300 - data['dist']) / 100 > 1.5
).astype(int)

print(f"✅ Generated {n_samples} training samples")
print(f"   - Collision cases: {data['collision'].sum()} ({data['collision'].sum()/n_samples*100:.1f}%)")
print(f"   - Safe cases: {(~data['collision'].astype(bool)).sum()} ({(~data['collision'].astype(bool)).sum()/n_samples*100:.1f}%)")

# ============================================================
# STEP 2: Split Data into Train/Test Sets
# ============================================================
print("\n🔀 Step 2: Splitting data into train/test sets...")

X = data.drop('collision', axis=1)
y = data['collision']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, 
    test_size=0.2, 
    random_state=42,
    stratify=y  # Maintain class balance
)

print(f"✅ Training set: {len(X_train)} samples")
print(f"✅ Test set: {len(X_test)} samples")

# ============================================================
# STEP 3: Train Random Forest Model
# ============================================================
print("\n🌲 Step 3: Training Random Forest Classifier...")

model = RandomForestClassifier(
    n_estimators=100,      # 100 decision trees
    max_depth=15,          # Prevent overfitting
    min_samples_split=10,
    random_state=42,
    n_jobs=-1              # Use all CPU cores
)

model.fit(X_train, y_train)
print("✅ Model training completed!")

# ============================================================
# STEP 4: Evaluate Model Performance
# ============================================================
print("\n📈 Step 4: Evaluating model performance...")

# Make predictions
y_pred = model.predict(X_test)

# Calculate metrics
accuracy = accuracy_score(y_test, y_pred)
print(f"\n✅ Model Accuracy: {accuracy:.2%}")

print("\n📊 Detailed Classification Report:")
print(classification_report(y_test, y_pred, target_names=['Safe', 'Collision Risk']))

# Feature importance
feature_importance = pd.DataFrame({
    'feature': X.columns,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

print("\n🔍 Feature Importance:")
for idx, row in feature_importance.iterrows():
    print(f"   {row['feature']:12s}: {row['importance']:.4f}")

# ============================================================
# STEP 5: Save Model
# ============================================================
print("\n💾 Step 5: Saving model...")

model_path = "../Outputs/rf_model.pkl"
joblib.dump(model, model_path)

print(f"✅ Model saved to: {model_path}")
print("\n" + "=" * 60)
print("🎉 AI Model Training Completed Successfully!")
print("=" * 60)
print("\n📌 Next Steps:")
print("   1. Run 'python v2v_sim.py' to start the simulation")
print("   2. Run 'streamlit run dashboard.py' to view live dashboard")