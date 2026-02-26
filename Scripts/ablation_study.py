import subprocess
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score

import numpy as np
from bsd_engine import Params

def run_sim(alpha, beta, gamma, use_lat_ttc, seed):
    cmd = [
        'python', 'v2v_bsd_simulation.py', '--no-gui', '--steps', '600',
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
        
    y_pred = (df[['cri_left', 'cri_right']].max(axis=1) >= 0.8).astype(int).values
    return df, y_pred

def get_y_true_for_seed(seed):
    """Get kinematic near-miss ground truth for this seed (matches evaluate_system.py)."""
    df, _ = run_sim(Params.ALPHA, Params.BETA, Params.GAMMA, True, seed)
    from bsd_utils import compute_ground_truth, check_coverage
    y_true = compute_ground_truth(df)
    check_coverage(y_true, 'ablation_study.py')

    positive_events = set()
    for i, row in df.iterrows():
        if y_true[i] == 1:
            positive_events.add((row['step'], row['ego_vid']))
    return positive_events

def evaluate_pred(df, y_pred, positive_events):
    y_true_mapped = np.array([1 if (row['step'], row['ego_vid']) in positive_events else 0 for _, row in df.iterrows()])
    return (
        precision_score(y_true_mapped, y_pred, zero_division=0),
        recall_score(y_true_mapped, y_pred, zero_division=0),
        f1_score(y_true_mapped, y_pred, zero_division=0)
    )

def main():
    print("Running Ablation Study (N=5 seeds)...")
    
    configs = [
        ('A1', 1.0, 0.0, 0.0, False),
        ('A2', 0.5, 0.5, 0.0, False),
        ('A3', 0.35, 0.45, 0.20, False),
        ('A4', 0.35, 0.45, 0.20, True),
        ('A5', Params.ALPHA, Params.BETA, Params.GAMMA, True)
    ]

    all_results = {name: [] for name, _, _, _, _ in configs}

    for seed in range(42, 47):
        print(f"\n--- Seed {seed} ---")
        positive_events = get_y_true_for_seed(seed)
        for name, a, b, g, lat in configs:
            df, y_pred = run_sim(a, b, g, lat, seed)
            p, r, f = evaluate_pred(df, y_pred, positive_events)
            all_results[name].append((p, r, f))
            print(f"Seed {seed} | Config {name} (α={a}, β={b}, γ={g}, Lat TTC={lat}) -> P:{p:.3f} R:{r:.3f} F1:{f:.3f}")

    print("\n=== Ablation Results (Mean ± Std) ===")
    summary = []
    for name in all_results:
        ps = [res[0] for res in all_results[name]]
        rs = [res[1] for res in all_results[name]]
        fs = [res[2] for res in all_results[name]]
        summary.append({
            'Config': name,
            'Precision': f"{np.mean(ps):.3f} ± {np.std(ps):.3f}",
            'Recall': f"{np.mean(rs):.3f} ± {np.std(rs):.3f}",
            'F1': f"{np.mean(fs):.3f} ± {np.std(fs):.3f}"
        })
    print(pd.DataFrame(summary))

if __name__ == '__main__':
    main()
