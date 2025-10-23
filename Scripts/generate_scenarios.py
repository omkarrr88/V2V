import pandas as pd
import numpy as np
import random

np.random.seed(42)  # Reproducibility
data = []
for i in range(200):
    sid = i + 1
    vid = f"veh_{sid}"
    accel = np.random.uniform(0.5, 3.0)
    decel = np.random.uniform(3, 8) if random.random() > 0.3 else np.random.uniform(6, 10)  # 70% normal, 30% harsh
    speed = np.random.uniform(50, 120)
    x = np.random.uniform(72.84648 * 100000, 72.86214 * 100000)  # Scaled UTM-like
    y = np.random.uniform(18.99201 * 100000, 19.00201 * 100000)
    risk = min(1.0, (120 - speed)/70 + decel/10 + random.uniform(0, 0.2))  # Simple heuristic
    ts = random.uniform(0, 3600)
    data.append([sid, vid, accel, decel, speed, x, y, risk, ts])

df = pd.DataFrame(data, columns=['scenario_id', 'vehicle_id', 'acceleration', 'deceleration', 'speed', 'x', 'y', 'collision_risk', 'timestamp'])
df.to_csv('../Scenarios/scenarios.csv', index=False)
print("Generated 200 scenarios in Scenarios/scenarios.csv")