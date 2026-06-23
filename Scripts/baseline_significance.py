"""
baseline_significance.py
========================
Computes bootstrap 95% confidence intervals on AUC for all four detection
methods, plus paired bootstrap tests for pairwise differences.

Addresses Reviewer 2 (point 5): no CIs or significance tests vs. baselines.
Addresses Reviewer 2 (point 1) and Reviewer 3 (point 3): independent metric
(SUMO physical collisions) with CI.

Outputs:
  - Outputs/baseline_significance.json
"""
import os
import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import roc_auc_score, average_precision_score

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from bsd_utils import compute_ground_truth

METRICS_FILE = '../Outputs/bsd_metrics.csv'
REPORT_FILE  = '../Outputs/baseline_significance.json'
N_BOOTSTRAP  = 500    # 500 iterations is sufficient for stable 95% percentile CIs at this n


def bootstrap_auc(y, scores, n_boot=N_BOOTSTRAP, seed=42):
    """Return (point AUC, CI low, CI high, raw bootstrap array)."""
    rng = np.random.default_rng(seed)
    n = len(y)
    if y.sum() in (0, n):
        return None, None, None, None
    aucs = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yb = y[idx]
        if yb.sum() in (0, n):
            continue
        aucs.append(roc_auc_score(yb, scores[idx]))
    aucs = np.asarray(aucs)
    point = float(roc_auc_score(y, scores))
    return point, float(np.percentile(aucs, 2.5)), float(np.percentile(aucs, 97.5)), aucs


def paired_bootstrap_test(y, scores_a, scores_b, n_boot=N_BOOTSTRAP, seed=42):
    """Test whether AUC(a) > AUC(b) via paired bootstrap. Returns observed delta,
    CI on delta, and one-sided p-value."""
    rng = np.random.default_rng(seed)
    n = len(y)
    obs_delta = roc_auc_score(y, scores_a) - roc_auc_score(y, scores_b)
    deltas = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yb = y[idx]
        if yb.sum() in (0, n):
            continue
        deltas.append(roc_auc_score(yb, scores_a[idx]) - roc_auc_score(yb, scores_b[idx]))
    deltas = np.asarray(deltas)
    # One-sided p-value: P(delta <= 0) under bootstrap distribution
    p_one_sided = float((deltas <= 0).mean())
    return {
        'delta_auc':     float(obs_delta),
        'delta_ci95':    [float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))],
        'p_one_sided':   p_one_sided,
        'p_two_sided':   float(2 * min(p_one_sided, 1 - p_one_sided)),
        'n_bootstrap':   int(len(deltas)),
    }


def main():
    print('=' * 72)
    print('Baseline Significance Analysis')
    print('=' * 72)

    metrics_path = METRICS_FILE if os.path.exists(METRICS_FILE) else 'bsd_metrics.csv'
    print(f'Loading {metrics_path} ...')
    df = pd.read_csv(metrics_path)
    print(f'  Rows: {len(df):,}')

    y_proxy = compute_ground_truth(df)
    y_sumo  = df['ground_truth_collision'].values.astype(int)
    print(f'  Proxy positives: {int(y_proxy.sum()):,}')
    print(f'  SUMO physical collisions (independent ground truth): {int(y_sumo.sum())}')

    # ---- Score columns ----
    physics  = df[['cri_left', 'cri_right']].max(axis=1).values
    # Re-compute physics with recalibrated weights for comparison
    sev_L = df[['R_decel_left',  'R_ttc_left' ]].max(axis=1)
    sev_R = df[['R_decel_right', 'R_ttc_right']].max(axis=1)
    a, b = 0.90, 0.10   # recalibrated optimum from Phase 1.1
    cri_L = (df['P_left']  * sev_L *
             (a*df['R_decel_left']  + b*df['R_ttc_left'])  * df['plr_mult_left']).clip(0, 1)
    cri_R = (df['P_right'] * sev_R *
             (a*df['R_decel_right'] + b*df['R_ttc_right']) * df['plr_mult_right']).clip(0, 1)
    physics_recal = pd.concat([cri_L, cri_R], axis=1).max(axis=1).values

    alert_map = {'SAFE': 0.0, 'CAUTION': 0.33, 'WARNING': 0.66, 'CRITICAL': 1.0, 'N/A': 0.0}
    ttc      = np.maximum(df['baseline_left'].map(alert_map).fillna(0.0),
                          df['baseline_right'].map(alert_map).fillna(0.0)).values
    static   = np.maximum(df['static_left'  ].map(alert_map).fillna(0.0),
                          df['static_right' ].map(alert_map).fillna(0.0)).values
    xgb      = df['ai_critical_prob'].fillna(0.0).values

    methods = {
        'Physics (published a=0.20, b=0.80)':  physics,
        'Physics (recalibrated a=0.90, b=0.10)': physics_recal,
        'TTC kinematic baseline':              ttc,
        'Static box baseline':                 static,
        'XGBoost classifier':                  xgb,
    }

    report = {
        'protocol': {
            'n_bootstrap': N_BOOTSTRAP,
            'random_state': 42,
            'paired_test': 'percentile bootstrap on delta AUC',
        },
        'dataset': {
            'rows': int(len(df)),
            'proxy_positives': int(y_proxy.sum()),
            'sumo_collisions': int(y_sumo.sum()),
        },
        'auc_with_ci': {'proxy': {}, 'sumo_collisions': {}},
        'auprc': {'proxy': {}},
        'pairwise_vs_physics_published': {'proxy': {}, 'sumo_collisions': {}},
    }

    # ---- Per-method AUC + CI ----
    print('\nPer-method AUC with 95% bootstrap CI (proxy ground truth):')
    for name, scores in methods.items():
        pt, lo, hi, _ = bootstrap_auc(y_proxy, scores)
        report['auc_with_ci']['proxy'][name] = {'auc': pt, 'ci95': [lo, hi]}
        ap = float(average_precision_score(y_proxy, scores))
        report['auprc']['proxy'][name] = ap
        print(f'  {name:50s} AUC={pt:.4f} [{lo:.4f}, {hi:.4f}]  AUPRC={ap:.4f}')

    print('\nPer-method AUC with 95% bootstrap CI (SUMO physical collisions, independent):')
    for name, scores in methods.items():
        pt, lo, hi, _ = bootstrap_auc(y_sumo, scores)
        if pt is None:
            print(f'  {name:50s} (no positive events)')
            report['auc_with_ci']['sumo_collisions'][name] = None
        else:
            report['auc_with_ci']['sumo_collisions'][name] = {'auc': pt, 'ci95': [lo, hi]}
            print(f'  {name:50s} AUC={pt:.4f} [{lo:.4f}, {hi:.4f}]')

    # ---- Pairwise tests vs. published physics ----
    print('\nPaired bootstrap test (Physics published) vs others on proxy:')
    base = methods['Physics (published a=0.20, b=0.80)']
    for name, scores in methods.items():
        if name.startswith('Physics (published'):
            continue
        res = paired_bootstrap_test(y_proxy, base, scores)
        report['pairwise_vs_physics_published']['proxy'][name] = res
        sig = '***' if res['p_two_sided'] < 0.001 else ('**' if res['p_two_sided'] < 0.01 else ('*' if res['p_two_sided'] < 0.05 else 'n.s.'))
        print(f'  Physics vs {name:45s} delta={res["delta_auc"]:+.4f}  p={res["p_two_sided"]:.4f}  {sig}')

    print('\nPaired bootstrap test (Physics published) vs others on SUMO collisions:')
    for name, scores in methods.items():
        if name.startswith('Physics (published'):
            continue
        if y_sumo.sum() < 2:
            continue
        res = paired_bootstrap_test(y_sumo, base, scores)
        report['pairwise_vs_physics_published']['sumo_collisions'][name] = res
        sig = '***' if res['p_two_sided'] < 0.001 else ('**' if res['p_two_sided'] < 0.01 else ('*' if res['p_two_sided'] < 0.05 else 'n.s.'))
        print(f'  Physics vs {name:45s} delta={res["delta_auc"]:+.4f}  p={res["p_two_sided"]:.4f}  {sig}')

    Path(os.path.dirname(REPORT_FILE)).mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, 'w') as f:
        json.dump(report, f, indent=2)
    print(f'\nReport written: {REPORT_FILE}')


if __name__ == '__main__':
    main()
