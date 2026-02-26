import subprocess
import pandas as pd
from sklearn.metrics import f1_score
from bsd_engine import Params

def run_sim(param, val):
    cmd = ['python', 'v2v_bsd_simulation.py', '--no-gui', '--steps', '600']
    
    if param == 'SIGMA_GPS':
        cmd.extend(['--sigma-gps', str(val)])
    elif param == 'PLR':
        cmd.extend(['--plr-g2b', str(val)])
    elif param == 'TTC_CRIT':
        cmd.extend(['--ttc-crit', str(val)])
    elif param == 'THETA_3':
        cmd.extend(['--theta-3', str(val)])

    subprocess.run(cmd, stdout=subprocess.DEVNULL)
    
    try:
        df = pd.read_csv('../Outputs/bsd_metrics.csv')
    except Exception:
        df = pd.read_csv('bsd_metrics.csv')
        
    from bsd_utils import compute_ground_truth, check_coverage
    y_true = compute_ground_truth(df)
    check_coverage(y_true, 'sensitivity_analysis.py')

    eval_threshold = val if param == 'THETA_3' else Params.THETA_3
    y_pred = (df[['cri_left', 'cri_right']].max(axis=1) >= eval_threshold).astype(int)
    return f1_score(y_true, y_pred, zero_division=0)

def main():
    print("Running Sensitivity Analysis...")

    sweeps = {
        'SIGMA_GPS': [0.5, 1.0, 1.5, 2.0, 3.0],
        'PLR': [0.01, 0.05, 0.10, 0.20],
        'TTC_CRIT': [2.0, 4.0, 6.0, 8.0],
        'THETA_3': [0.70, 0.75, 0.80, 0.85]
    }

    results = []
    
    for param, vals in sweeps.items():
        print(f"\n--- Sweeping {param} ---")
        for val in vals:
            f = run_sim(param, val)
            results.append({'Parameter': param, 'Value': val, 'F1': f})
            print(f"  {param}={val} -> F1: {f:.3f}")

    print("\n=== Sensitivity Results ===")
    import pprint
    pprint.pprint(results)

if __name__ == '__main__':
    main()
