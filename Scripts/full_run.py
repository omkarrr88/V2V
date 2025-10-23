import os
import pandas as pd
import subprocess
import time

SCENARIO_DIR = "../Scenarios/"
SCENARIO_FILES = [f for f in os.listdir(SCENARIO_DIR) if f.endswith(".csv")]
MAX_BATCH = 10  # run 10 scenarios at a time

for i in range(0, len(SCENARIO_FILES), MAX_BATCH):
    batch = SCENARIO_FILES[i:i+MAX_BATCH]
    for scenario in batch:
        try:
            print(f"🔹 Running scenario: {scenario}")
            subprocess.run(["python", "v2v_sim.py"], check=True)
        except subprocess.CalledProcessError:
            print(f"⚠️ Error in scenario {scenario}, skipping...")
        time.sleep(1)  # small pause between runs
