# ============================================================
# V2V Communication & Collision Detection Simulation
# ============================================================
# This script runs SUMO traffic simulation with real-time
# AI-powered collision prediction and V2V communication
# ============================================================

import pandas as pd
import traci
import os
from joblib import load
import sys

# ================= CONFIGURATION =================
SUMO_CFG = "../Maps/atal.sumocfg"
SCENARIO_CSV = "../Scenarios/scenarios.csv"
OUTPUT_METRICS = "../Outputs/live_metrics.csv"
OUTPUT_COLLISIONS = "../Outputs/collisions.csv"
MODEL_PATH = "../Outputs/rf_model.pkl"

MAX_STEPS = 3600              # Simulation duration (steps)
UPDATE_INTERVAL = 10          # Update vehicle states every n steps
LOG_INTERVAL = 10             # Write CSVs every n steps
RISK_THRESHOLD = 0.5          # AI risk threshold for alerts
COLLISION_DISTANCE = 2.0      # Distance threshold for actual collision (meters)
DEFAULT_DECEL = 4.5           # Default deceleration capability (m/s²)
# ==================================================

print("🚗 V2V Accident Prevention Simulation Starting...")
print("=" * 70)

# Create output directory
os.makedirs("../Outputs", exist_ok=True)

# Load AI model
print(f"\n🤖 Loading AI model from: {MODEL_PATH}")
try:
    model = load(MODEL_PATH)
    print("✅ AI model loaded successfully!")
except FileNotFoundError:
    print("❌ ERROR: AI model not found! Please run 'train_ai.py' first.")
    sys.exit(1)

# Load scenarios (if needed for reference)
print(f"📊 Loading scenarios from: {SCENARIO_CSV}")
try:
    df_scenarios = pd.read_csv(SCENARIO_CSV)
    print(f"✅ Loaded {len(df_scenarios)} scenario records")
except FileNotFoundError:
    print("⚠️  Warning: scenarios.csv not found. Continuing without it.")
    df_scenarios = pd.DataFrame()

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def euclidean_distance(a, b):
    """Calculate Euclidean distance between two vehicles"""
    if not a or not b:
        return 9999
    return ((a['x'] - b['x'])**2 + (a['y'] - b['y'])**2)**0.5

def predict_collision(vehicle_a, vehicle_b):
    """
    Predict collision risk using AI model
    Returns: 0 (safe) or 1 (collision risk)
    """
    if not vehicle_b:
        return 0
    
    # Calculate distance
    distance = euclidean_distance(vehicle_a, vehicle_b)
    
    # Prepare features matching training data format
    features = pd.DataFrame([{
        'speed_a': vehicle_a['speed'],
        'speed_b': vehicle_b['speed'],
        'dist': distance,
        'decel_a': vehicle_a.get('decel', DEFAULT_DECEL),
        'decel_b': vehicle_b.get('decel', DEFAULT_DECEL)
    }])
    
    try:
        prediction = model.predict(features)[0]
        return prediction
    except Exception as e:
        print(f"⚠️  Prediction error: {e}")
        return 0

# ============================================================
# START SUMO SIMULATION
# ============================================================

print(f"\n🚀 Starting SUMO-GUI simulation...")
print(f"   Config: {SUMO_CFG}")
print(f"   Max steps: {MAX_STEPS}")
print("   (SUMO GUI window will open - you'll see vehicles moving on the map)")

try:
    # Start SUMO with GUI
    traci.start([
        "sumo-gui",              # Use GUI version
        "-c", SUMO_CFG,          # Configuration file
        "--start",               # Auto-start simulation
        "--quit-on-end",         # Close GUI after completion
        "--step-length", "1",    # 1 second per step
        "--delay", "50"          # Small delay for visualization (50ms)
    ])
    print("✅ SUMO-GUI launched successfully!\n")
except Exception as e:
    print(f"❌ ERROR starting SUMO: {e}")
    print("   Make sure 'sumo-gui' is installed and atal.sumocfg exists in Maps folder")
    sys.exit(1)

# ============================================================
# SIMULATION LOOP
# ============================================================

messages = {}              # Store vehicle states (simulates V2V communication)
collision_log = []        # Log all collision predictions
metrics_log = []          # Log vehicle metrics
alerted_vehicles = set()  # Track vehicles already alerted

print("🔄 Simulation running... (Watch the SUMO GUI window)")
print("=" * 70)

for step in range(MAX_STEPS):
    traci.simulationStep()
    
    # -------------------------
    # Update vehicle states every UPDATE_INTERVAL steps
    # -------------------------
    if step % UPDATE_INTERVAL == 0:
        vehicle_ids = traci.vehicle.getIDList()
        
        if len(vehicle_ids) == 0:
            continue
        
        # Collect current vehicle states
        messages.clear()
        for vid in vehicle_ids:
            try:
                position = traci.vehicle.getPosition(vid)
                speed = traci.vehicle.getSpeed(vid)
                accel = traci.vehicle.getAcceleration(vid)
                
                # Get deceleration capability from vehicle type
                # Note: TraCI doesn't have getDeceleration(), we get it from vehicle type
                try:
                    vehicle_type = traci.vehicle.getTypeID(vid)
                    decel = traci.vehicletype.getDecel(vehicle_type)
                except:
                    decel = DEFAULT_DECEL  # Use default if unavailable
                
                messages[vid] = {
                    'x': position[0],
                    'y': position[1],
                    'speed': speed,
                    'accel': accel,
                    'decel': decel
                }
                
                # Log metrics
                metrics_log.append({
                    'id': vid,
                    'speed': speed,
                    'x': position[0],
                    'y': position[1],
                    'accel': accel,
                    'ts': step
                })
                
            except traci.exceptions.TraCIException:
                continue
        
        # -------------------------
        # Collision Detection & AI Prediction
        # -------------------------
        for vid_a in vehicle_ids:
            if vid_a not in messages:
                continue
            
            vehicle_a = messages[vid_a]
            nearest_vehicle = None
            min_distance = float('inf')
            
            # Find nearest vehicle
            for vid_b in vehicle_ids:
                if vid_a == vid_b or vid_b not in messages:
                    continue
                
                vehicle_b = messages[vid_b]
                dist = euclidean_distance(vehicle_a, vehicle_b)
                
                if dist < min_distance:
                    min_distance = dist
                    nearest_vehicle = vehicle_b
            
            # Predict collision with nearest vehicle
            if nearest_vehicle:
                ai_risk = predict_collision(vehicle_a, nearest_vehicle)
                actual_collision = 1 if min_distance < COLLISION_DISTANCE else 0
                
                # Log prediction
                collision_log.append({
                    'step': step,
                    'vehicle_id': vid_a,
                    'nearest_dist': min_distance,
                    'ai_prediction': ai_risk,
                    'actual_collision': actual_collision,
                    'speed': vehicle_a['speed']
                })
                
                # -------------------------
                # VISUAL ALERT: Change vehicle color to RED if high risk
                # -------------------------
                if ai_risk >= RISK_THRESHOLD:
                    try:
                        traci.vehicle.setColor(vid_a, (255, 0, 0, 255))  # Bright RED
                        
                        # Console alert (only once per vehicle)
                        if vid_a not in alerted_vehicles:
                            print(f"⚠️  AI ALERT [Step {step}]: High collision risk for vehicle '{vid_a}' "
                                  f"(distance: {min_distance:.1f}m, speed: {vehicle_a['speed']:.1f}m/s)")
                            alerted_vehicles.add(vid_a)
                    except:
                        pass
                else:
                    # Reset to default color (green) if safe
                    try:
                        traci.vehicle.setColor(vid_a, (0, 255, 0, 255))  # Green
                    except:
                        pass
    
    # -------------------------
    # Save data to CSV every LOG_INTERVAL steps
    # -------------------------
    if step % LOG_INTERVAL == 0 and step > 0:
        if metrics_log:
            pd.DataFrame(metrics_log).to_csv(OUTPUT_METRICS, index=False)
        
        if collision_log:
            pd.DataFrame(collision_log).to_csv(OUTPUT_COLLISIONS, index=False)
        
        if step % 100 == 0:  # Print progress every 100 steps
            print(f"📊 Step {step}/{MAX_STEPS} - Active vehicles: {len(vehicle_ids)}, "
                  f"Alerts: {len(alerted_vehicles)}")

# ============================================================
# CLEANUP & FINAL REPORT
# ============================================================

print("\n" + "=" * 70)
print("🏁 Simulation completed!")

# Save final data
if metrics_log:
    pd.DataFrame(metrics_log).to_csv(OUTPUT_METRICS, index=False)
    print(f"✅ Live metrics saved: {OUTPUT_METRICS} ({len(metrics_log)} records)")

if collision_log:
    pd.DataFrame(collision_log).to_csv(OUTPUT_COLLISIONS, index=False)
    print(f"✅ Collision log saved: {OUTPUT_COLLISIONS} ({len(collision_log)} predictions)")

traci.close()

# Calculate statistics
if collision_log:
    collision_df = pd.DataFrame(collision_log)
    total_predictions = len(collision_df)
    high_risk_count = (collision_df['ai_prediction'] >= RISK_THRESHOLD).sum()
    actual_collisions = collision_df['actual_collision'].sum()
    
    print("\n📈 Simulation Statistics:")
    print(f"   Total predictions: {total_predictions}")
    print(f"   High-risk alerts: {high_risk_count} ({high_risk_count/total_predictions*100:.1f}%)")
    print(f"   Actual collisions detected: {actual_collisions}")
    print(f"   Unique vehicles alerted: {len(alerted_vehicles)}")

print("\n" + "=" * 70)
print("✅ V2V Simulation Complete!")
print("\n📌 Next Step: Run 'streamlit run dashboard.py' to view live dashboard")
print("=" * 70)