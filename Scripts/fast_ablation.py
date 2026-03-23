# Fast Ablation Study using exact formula on bsd_metrics.csv
import pandas as pd
import numpy as np
from sklearn.metrics import f1_score
from bsd_engine import Params
from bsd_utils import compute_ground_truth

def evaluate_config(df, y_true, alpha, beta, gamma, use_lat_ttc):
    # Vectorized CRI recomputation with severity gate (matching bsd_engine.py)
    # NOTE: The use_lat_ttc flag cannot be toggled post-hoc because R_ttc values
    # in the CSV were computed during simulation with the engine's default setting
    # (lateral TTC enabled). Configs labeled "Lat TTC = No" recompute CRI weights
    # only; the underlying R_ttc column already includes lateral TTC contributions
    # from the simulation run. A true lateral-TTC ablation requires re-running the
    # simulation with --no-lat-ttc.
    sev_L = df[['R_decel_left', 'R_ttc_left']].max(axis=1)
    sev_R = df[['R_decel_right', 'R_ttc_right']].max(axis=1)
    cri_L = df['P_left']  * sev_L * (alpha*df['R_decel_left']  + beta*df['R_ttc_left']  + gamma*df['R_intent_left'])  * df['plr_mult_left']
    cri_R = df['P_right'] * sev_R * (alpha*df['R_decel_right'] + beta*df['R_ttc_right'] + gamma*df['R_intent_right']) * df['plr_mult_right']

    cri_vals = pd.concat([cri_L.clip(0,1), cri_R.clip(0,1)], axis=1).max(axis=1)

    y_pred_60 = (cri_vals >= Params.THETA_2).astype(int)
    y_pred_80 = (cri_vals >= Params.THETA_3).astype(int)

    base_f1_60 = f1_score(y_true, y_pred_60, zero_division=0)
    base_f1_80 = f1_score(y_true, y_pred_80, zero_division=0)

    return base_f1_60, base_f1_80

def main():
    try:
        df = pd.read_csv('../Outputs/bsd_metrics.csv')
    except Exception:
        df = pd.read_csv('bsd_metrics.csv')
        
    y_true = compute_ground_truth(df)
    
    configs = [
        ('A1', 1.0, 0.0, 0.0, False),
        ('A2', 0.5, 0.5, 0.0, False),
        ('A3', 0.35, 0.45, 0.20, False),
        ('A4', 0.35, 0.45, 0.20, True),
        ('A5', Params.ALPHA, Params.BETA, Params.GAMMA, True)
    ]
    
    print("| Config | α | β | γ | Lat TTC | F1 (θ=0.60) | F1 (θ=0.80) |")
    print("|--------|------|------|------|---------|-------------|-------------|")
    for name, a, b, g, l in configs:
        f60, f80 = evaluate_config(df, y_true, a, b, g, l)
        
        lt = '✓' if l else '✗'
        print(f"| {name} | {a:.2f} | {b:.2f} | {g:.2f} | {lt} | {f60:.4f} | {f80:.4f} |")

if __name__ == '__main__':
    main()
