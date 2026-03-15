"""
optimize_weights.py — CRI Weight Optimization via Grid Search
==============================================================
Finds optimal α, β, γ weights for the CRI formula by grid search
over existing bsd_metrics.csv data.

Outputs the best weights to console. The author must manually update
Params.ALPHA, Params.BETA, Params.GAMMA in bsd_engine.py — this script
does NOT auto-modify source code (unlike the previous regex-based approach).

Usage: python optimize_weights.py
"""
import pandas as pd
import numpy as np
from sklearn.metrics import f1_score
from bsd_engine import Params

def main():
    print("Loading bsd_metrics.csv...")
    try:
        df = pd.read_csv('../Outputs/bsd_metrics.csv')
    except FileNotFoundError:
        df = pd.read_csv('bsd_metrics.csv')
        
    from bsd_utils import compute_ground_truth, check_coverage
    y_true = compute_ground_truth(df)
    check_coverage(y_true, 'optimize_weights.py')

    if y_true.sum() == 0:
        print("No near-miss events found. Run a longer simulation (--steps 3600) first.")
        return

    best_f1, best_weights = 0, None

    print(f"Total rows: {len(df)}, Positive events: {y_true.sum()}")
    print("Starting Grid Search...")
    for alpha in np.arange(0.1, 0.81, 0.05):
        for beta in np.arange(0.1, 0.81, 0.05):
            gamma = round(1.0 - alpha - beta, 2)
            if gamma < 0.0 or gamma > 1.0:
                continue
            
            # Vectorized CRI — 100x faster than .apply()
            cri_L = df['P_left']  * (alpha*df['R_decel_left']  + beta*df['R_ttc_left']  + gamma*df['R_intent_left'])  * df['plr_mult_left']
            cri_R = df['P_right'] * (alpha*df['R_decel_right'] + beta*df['R_ttc_right'] + gamma*df['R_intent_right']) * df['plr_mult_right']
            cri_vals = pd.concat([cri_L.clip(0,1), cri_R.clip(0,1)], axis=1).max(axis=1)
            y_pred = (cri_vals >= Params.THETA_3).astype(int)
            
            f1 = f1_score(y_true, y_pred, zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_weights = (alpha, beta, gamma)
                print(f"New Best: α={alpha:.2f}, β={beta:.2f}, γ={gamma:.2f}, F1={best_f1:.3f}")

    if best_weights:
        a_opt, b_opt, g_opt = best_weights
        print(f"\n✅ Optimal weights: α={a_opt:.2f}, β={b_opt:.2f}, γ={g_opt:.2f}, F1={best_f1:.4f}")
        print(f"\n   To apply, update bsd_engine.py Params class manually:")
        print(f"     ALPHA       = {a_opt:.2f}")
        print(f"     BETA        = {b_opt:.2f}")
        print(f"     GAMMA       = {g_opt:.2f}")
        print(f"\n   Then re-run the simulation to regenerate CSV with updated weights.")
    else:
        print("No improvement found over current weights.")

if __name__ == '__main__':
    main()
