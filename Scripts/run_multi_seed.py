import subprocess
import os
import sys
import pandas as pd
import argparse
from sklearn.metrics import f1_score, roc_auc_score

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seeds', type=int, default=5)
    parser.add_argument('--steps', type=int, default=600)
    args = parser.parse_args()
    seeds = list(range(10, 10 + args.seeds * 10, 10))
    results = []

    for seed in seeds:
        print(f"\n======================================")
        print(f"Running Seed {seed}")
        print(f"======================================")
        cmd = [
            "python", "v2v_bsd_simulation.py",
            "--no-gui",
            "--steps", str(args.steps),
            "--seed", str(seed)
        ]
        subprocess.run(cmd, timeout=300)

        try:
            df = pd.read_csv('../Outputs/bsd_metrics.csv')
        except FileNotFoundError:
            df = pd.read_csv('bsd_metrics.csv')

        y_true_col = df['ground_truth_collision'].values
        if y_true_col.sum() == 0:
            rel_speed = df['rel_speed'].clip(lower=0.001)
            ttc_proxy = df['max_gap'] / rel_speed
            ttc_proxy[df['rel_speed'] <= 0] = 999.0
            has_target = df['num_targets'] > 0
            y_true = (has_target & ((df['max_gap'] < 2.0) | (ttc_proxy < 1.5))).astype(int).values
        else:
            y_true = y_true_col

        math_cri = df[['cri_left', 'cri_right']].max(axis=1).values
        y_pred = (math_cri >= 0.8).astype(int)

        f1 = f1_score(y_true, y_pred, zero_division=0)
        
        try:
            auc_math = roc_auc_score(y_true, math_cri)
        except ValueError:
            auc_math = float('nan') # Handle edge cases with zero positive samples

        results.append({'seed': seed, 'f1': f1, 'auc': auc_math})

    print("\n======================================")
    print("Aggregate Results (Math Model)")
    print("======================================")
    df_res = pd.DataFrame(results)
    for idx, row in df_res.iterrows():
        print(f"Seed {int(row['seed'])}: F1={row['f1']:.4f}, AUC={row['auc']:.4f}")
    
    print("--------------------------------------")
    print(f"Average F1:  {df_res['f1'].mean():.4f}")
    print(f"Average AUC: {df_res['auc'].mean():.4f}")
    print("======================================")

if __name__ == "__main__":
    main()
