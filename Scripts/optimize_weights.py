import pandas as pd
import numpy as np
from sklearn.metrics import f1_score

def compute_cri(row, alpha, beta, gamma):
    # Left
    r_w_left = alpha * row['R_decel_left'] + beta * row['R_ttc_left'] + gamma * row['R_intent_left']
    cri_left = row['P_left'] * r_w_left * row['plr_mult_left']
    
    # Right
    r_w_right = alpha * row['R_decel_right'] + beta * row['R_ttc_right'] + gamma * row['R_intent_right']
    cri_right = row['P_right'] * r_w_right * row['plr_mult_right']
    
    return max(cri_left, cri_right)

def main():
    print("Loading bsd_metrics.csv...")
    try:
        df = pd.read_csv('../Outputs/bsd_metrics.csv')
    except Exception as e:
        df = pd.read_csv('bsd_metrics.csv')
        
    y_true = df['ground_truth_collision'].values
    y_true = df['ground_truth_collision'].values

    if y_true.sum() == 0:
        print("No SUMO collisions found. Building composite near-miss proxy...")
        # Composite proxy captures BOTH longitudinal AND lateral risk events:
        #   - Longitudinal rear-end near-miss: small gap closing fast
        #   - Lateral sideswipe near-miss: high R_ttc_lat risk on either side
        # Using R_ttc columns (model internals, not raw features) ensures
        # the proxy captures lateral scenarios that gap alone misses.
        longitudinal_nm = (df['max_gap'] < 2.0)
        lateral_nm_left  = (df.get('R_ttc_left',  pd.Series(0.0, index=df.index)) > 0.7) & \
                           (df.get('P_left',       pd.Series(0.0, index=df.index)) > 0.3)
        lateral_nm_right = (df.get('R_ttc_right', pd.Series(0.0, index=df.index)) > 0.7) & \
                           (df.get('P_right',      pd.Series(0.0, index=df.index)) > 0.3)
        y_true = (longitudinal_nm | lateral_nm_left | lateral_nm_right).astype(int)
        print(f"   Composite near-miss events: {y_true.sum()} / {len(y_true)} rows ({100*y_true.mean():.2f}%)")

    if y_true.sum() == 0:
        print("No near-miss events found. Run a longer simulation (--steps 3600) first.")
        return

    best_f1, best_weights = 0, None

    print(f"Total rows: {len(df)}, Collisions: {y_true.sum()}")
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
            y_pred = (cri_vals >= 0.50).astype(int)
            
            f1 = f1_score(y_true, y_pred, zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_weights = (alpha, beta, gamma)
                print(f"New Best: α={alpha:.2f}, β={beta:.2f}, γ={gamma:.2f}, F1={best_f1:.3f}")

    if best_weights:
        a_opt, b_opt, g_opt = best_weights
        print(f"\n✅ Optimal weights: α={a_opt:.2f}, β={b_opt:.2f}, γ={g_opt:.2f}, F1={best_f1:.4f}")

        # Auto-write weights back to bsd_engine.py Params class
        import re, pathlib
        engine_path = pathlib.Path(__file__).parent / 'bsd_engine.py'
        src = engine_path.read_text()
        src = re.sub(r'(ALPHA\s*=\s*)[\d.]+', f'ALPHA       = {a_opt:.2f}', src)
        src = re.sub(r'(BETA\s*=\s*)[\d.]+',  f'BETA        = {b_opt:.2f}', src)
        src = re.sub(r'(GAMMA\s*=\s*)[\d.]+', f'GAMMA       = {g_opt:.2f}', src)
        engine_path.write_text(src)
        print(f"   ✅ Weights written back to bsd_engine.py automatically.")
        print(f"   Re-run the simulation to regenerate CSV with updated weights.")

if __name__ == '__main__':
    main()
