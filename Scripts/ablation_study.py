import subprocess
import os
import time
import argparse
import pandas as pd
import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score
from bsd_engine import Params
from bsd_utils import compute_ground_truth

def run_sim(alpha, beta, gamma, use_lat_ttc, seed, steps):
    cmd = [
        'python', 'v2v_bsd_simulation.py', '--no-gui', '--steps', str(steps),
        '--alpha', str(alpha),
        '--beta', str(beta),
        '--gamma', str(gamma)
    ]
    if not use_lat_ttc:
        cmd.append('--no-lat-ttc')
    
    cmd.extend(['--seed', str(seed)])
        
    subprocess.run(cmd, stdout=subprocess.DEVNULL)
    
    try:
        df = pd.read_csv('../Outputs/bsd_metrics.csv')
    except Exception:
        df = pd.read_csv('bsd_metrics.csv')
        
    return df

def get_y_preds(df):
    max_cri = df[['cri_left', 'cri_right']].max(axis=1)
    y_pred_80 = (max_cri >= Params.THETA_3).astype(int).values
    y_pred_60 = (max_cri >= Params.THETA_2).astype(int).values
    return y_pred_60, y_pred_80

def evaluate_pred(y_true, y_pred):
    return (
        precision_score(y_true, y_pred, zero_division=0),
        recall_score(y_true, y_pred, zero_division=0),
        f1_score(y_true, y_pred, zero_division=0)
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Run quick test mode")
    args = parser.parse_args()

    steps = 300 if args.quick else 3600
    seeds = [42] if args.quick else [42, 43, 44, 45, 46]
    
    if args.quick:
        print("⚠️  WARNING: Quick mode (300 steps, 1 seed) produces statistically unreliable F1 scores.")
        print("   For paper submission, run without --quick flag (3600 steps, 5 seeds, ~30 min).\n")
    
    print(f"Running Ablation Study (N={len(seeds)} seeds, steps={steps})...")
    
    configs = [
        ('A1', 1.0, 0.0, 0.0, False),
        ('A2', 0.5, 0.5, 0.0, False),
        ('A3', 0.35, 0.45, 0.20, False),
        ('A4', 0.35, 0.45, 0.20, True),
        ('A5', Params.ALPHA, Params.BETA, Params.GAMMA, True)
    ]

    results_60 = {name: [] for name, _, _, _, _ in configs}
    results_80 = {name: [] for name, _, _, _, _ in configs}

    total_runs = len(seeds) * len(configs)
    completed_runs = 0
    start_time = time.time()

    for seed in seeds:
        print(f"\n--- Seed {seed} ---")
        
        # Ground truth is consistent for a given seed / steps combo because simulation physics is autonomous
        # Thus, we compute it from the first configuration run
        y_true_seed = None 
        
        for name, a, b, g, lat in configs:
            run_start = time.time()
            df = run_sim(a, b, g, lat, seed, steps)
            
            if y_true_seed is None:
                y_true_seed = compute_ground_truth(df)
            
            y_pred_60, y_pred_80 = get_y_preds(df)
            
            p60, r60, f60 = evaluate_pred(y_true_seed, y_pred_60)
            p80, r80, f80 = evaluate_pred(y_true_seed, y_pred_80)
            
            results_60[name].append((p60, r60, f60))
            results_80[name].append((p80, r80, f80))
            
            completed_runs += 1
            elapsed = time.time() - start_time
            avg_time = elapsed / completed_runs
            rem_runs = total_runs - completed_runs
            eta = avg_time * rem_runs
            
            print(f"Seed {seed} | Config {name} (α={a}, β={b}, γ={g}, Lat TTC={lat})")
            print(f"  θ=0.60 -> P:{p60:.3f} R:{r60:.3f} F1:{f60:.3f} | θ=0.80 -> P:{p80:.3f} R:{r80:.3f} F1:{f80:.3f}")
            print(f"  [Progress: {completed_runs}/{total_runs} | ETA: {eta:.1f}s]")

    print("\n=== Ablation Results (Mean ± Std) ===")
    summary = []
    for name in configs:
        n = name[0]
        f60s = [res[2] for res in results_60[n]]
        f80s = [res[2] for res in results_80[n]]
        summary.append({
            'Config': n,
            'F1 (θ=0.60)': f"{np.mean(f60s):.3f} ± {np.std(f60s):.3f}",
            'F1 (θ=0.80)': f"{np.mean(f80s):.3f} ± {np.std(f80s):.3f}"
        })
    print(pd.DataFrame(summary))

    metrics_path = "../Outputs/bsd_metrics.csv"
    if os.path.exists(metrics_path):
        df_sc = pd.read_csv(metrics_path)
        if 'scenario_type' in df_sc.columns:
            print("\n=== Scenario-Specific CRI Component Contributions ===")
            for side in ['left', 'right']:
                r_decel_col = f'R_decel_{side}'
                r_ttc_col = f'R_ttc_{side}'
                r_intent_col = f'R_intent_{side}'
                if all(c in df_sc.columns for c in [r_decel_col, r_ttc_col, r_intent_col]):
                    print(f"\n  {side.upper()} side:")
                    for sc in df_sc['scenario_type'].dropna().unique():
                        sc_df = df_sc[df_sc['scenario_type'] == sc]
                        print(f"    {sc} (n={len(sc_df)}):")
                        print(f"      R_decel:  {sc_df[r_decel_col].mean():.4f}")
                        print(f"      R_ttc:    {sc_df[r_ttc_col].mean():.4f}")
                        print(f"      R_intent: {sc_df[r_intent_col].mean():.4f}")

if __name__ == '__main__':
    main()
