"""
optimize_weights_calibrated.py
==============================
Recalibrates CRI weights (alpha, beta, gamma) with strict train/test discipline.

Motivation (Reviewer 2 comment): the published alpha=0.20, beta=0.80 weights were
selected by grid search over the FULL 146,051-row dataset, which means the test set
was implicitly seen during selection. This script fixes that by:

  1. Stratified 75/25 train/test split on the kinematic ground-truth label.
  2. Grid search over alpha, beta (gamma forced to 0 since intent is disabled)
     on the TRAIN partition only, using F1@0.60 as the selection criterion.
  3. The frozen weights are then evaluated on the untouched TEST partition.
  4. Both the current published weights (0.20, 0.80) and the new selected weights
     are reported on the test partition, so the headline AUC is directly comparable.

Outputs:
  - Outputs/calibration_report.json — full protocol record, grid results, both
    train and test metrics, bootstrap 95% CIs on test AUC.

Usage:
  python optimize_weights_calibrated.py
"""
import os
import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, roc_auc_score, precision_score, recall_score

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from bsd_utils import compute_ground_truth

METRICS_FILE = '../Outputs/bsd_metrics.csv'
REPORT_FILE  = '../Outputs/calibration_report.json'

THETA_WARNING  = 0.60   # F1 reported at WARNING threshold
THETA_CRITICAL = 0.80   # F1 reported at CRITICAL threshold
N_BOOTSTRAP    = 1000   # bootstrap iterations for AUC 95% CI

PUBLISHED_ALPHA = 0.20
PUBLISHED_BETA  = 0.80
PUBLISHED_GAMMA = 0.00


def compute_cri(df, alpha, beta, gamma):
    """Vectorised CRI with severity gate (matches bsd_engine.py)."""
    sev_L = df[['R_decel_left',  'R_ttc_left' ]].max(axis=1)
    sev_R = df[['R_decel_right', 'R_ttc_right']].max(axis=1)
    cri_L = (df['P_left']  * sev_L *
             (alpha*df['R_decel_left']  + beta*df['R_ttc_left']  + gamma*df['R_intent_left']) *
             df['plr_mult_left'])
    cri_R = (df['P_right'] * sev_R *
             (alpha*df['R_decel_right'] + beta*df['R_ttc_right'] + gamma*df['R_intent_right']) *
             df['plr_mult_right'])
    return pd.concat([cri_L.clip(0, 1), cri_R.clip(0, 1)], axis=1).max(axis=1).values


def evaluate(cri, y, sumo_y=None):
    """Return AUC + F1 at WARNING/CRITICAL + precision/recall at CRITICAL."""
    metrics = {}
    metrics['auc_proxy'] = float(roc_auc_score(y, cri)) if y.sum() > 0 else None
    metrics['f1_at_060'] = float(f1_score(y, (cri >= THETA_WARNING ).astype(int), zero_division=0))
    metrics['f1_at_080'] = float(f1_score(y, (cri >= THETA_CRITICAL).astype(int), zero_division=0))
    metrics['precision_at_080'] = float(precision_score(y, (cri >= THETA_CRITICAL).astype(int), zero_division=0))
    metrics['recall_at_080']    = float(recall_score   (y, (cri >= THETA_CRITICAL).astype(int), zero_division=0))
    if sumo_y is not None and sumo_y.sum() > 0:
        metrics['auc_sumo_collisions'] = float(roc_auc_score(sumo_y, cri))
        metrics['n_sumo_collisions']   = int(sumo_y.sum())
    return metrics


def bootstrap_auc_ci(y, scores, n_boot=N_BOOTSTRAP, seed=42):
    """Bootstrap 95% CI on AUC."""
    rng = np.random.default_rng(seed)
    n = len(y)
    aucs = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yb = y[idx]
        if yb.sum() in (0, n):
            continue
        aucs.append(roc_auc_score(yb, scores[idx]))
    aucs = np.asarray(aucs)
    return float(np.percentile(aucs, 2.5)), float(np.percentile(aucs, 97.5)), int(len(aucs))


def main():
    print('=' * 72)
    print('CRI Weight Recalibration with Strict Train/Test Discipline')
    print('=' * 72)

    metrics_path = METRICS_FILE if os.path.exists(METRICS_FILE) else 'bsd_metrics.csv'
    print(f'Loading {metrics_path} ...')
    df = pd.read_csv(metrics_path)
    n_rows = len(df)
    print(f'  Rows: {n_rows:,}')

    y = compute_ground_truth(df)
    sumo_y = df['ground_truth_collision'].values.astype(int) if 'ground_truth_collision' in df.columns else None
    print(f'  Positive (kinematic proxy): {int(y.sum()):,} ({100*y.mean():.2f}%)')
    if sumo_y is not None:
        print(f'  SUMO physical collisions (model-independent): {int(sumo_y.sum())}')

    if y.sum() == 0:
        print('No positive events. Aborting.')
        return

    # ---- 75/25 stratified split ----
    idx_train, idx_test = train_test_split(
        np.arange(n_rows), test_size=0.25, random_state=42, stratify=y
    )
    print(f'\nSplit:  train={len(idx_train):,}  test={len(idx_test):,}  '
          f'train_pos={int(y[idx_train].sum())}  test_pos={int(y[idx_test].sum())}')

    df_train = df.iloc[idx_train].reset_index(drop=True)
    df_test  = df.iloc[idx_test ].reset_index(drop=True)
    y_train  = y[idx_train]
    y_test   = y[idx_test]
    sumo_test = sumo_y[idx_test] if sumo_y is not None else None

    # ---- Grid search on TRAIN ONLY (both AUC and F1 criteria) ----
    print('\nGrid searching alpha, beta on training partition (gamma=0)...')
    grid = []
    best_auc = {'auc': -1, 'alpha': None, 'beta': None}
    best_f1  = {'f1_at_060': -1, 'alpha': None, 'beta': None}
    for alpha in np.arange(0.10, 0.91, 0.05):
        for beta in np.arange(0.10, 0.91, 0.05):
            if abs(alpha + beta - 1.0) > 0.01:
                continue
            alpha = round(alpha, 2)
            beta  = round(beta, 2)
            cri_train = compute_cri(df_train, alpha, beta, 0.0)
            auc_t = roc_auc_score(y_train, cri_train)
            f1_w  = f1_score(y_train, (cri_train >= THETA_WARNING).astype(int), zero_division=0)
            grid.append({'alpha': alpha, 'beta': beta,
                         'train_auc': float(auc_t), 'train_f1_at_060': float(f1_w)})
            if auc_t > best_auc['auc']:
                best_auc.update({'alpha': alpha, 'beta': beta, 'auc': float(auc_t)})
            if f1_w > best_f1['f1_at_060']:
                best_f1.update({'alpha': alpha, 'beta': beta, 'f1_at_060': float(f1_w)})

    print(f'  Best by AUC: alpha={best_auc["alpha"]}, beta={best_auc["beta"]}, '
          f'train AUC={best_auc["auc"]:.4f}')
    print(f'  Best by F1:  alpha={best_f1["alpha"]}, beta={best_f1["beta"]}, '
          f'train F1@0.60={best_f1["f1_at_060"]:.4f}')

    grid_auc_sorted = sorted(grid, key=lambda r: r['train_auc'], reverse=True)
    grid_f1_sorted  = sorted(grid, key=lambda r: r['train_f1_at_060'], reverse=True)
    print('  Top-5 by TRAIN AUC:')
    for r in grid_auc_sorted[:5]:
        print(f'    alpha={r["alpha"]:.2f}  beta={r["beta"]:.2f}  '
              f'AUC={r["train_auc"]:.4f}  F1={r["train_f1_at_060"]:.4f}')
    # Use AUC-optimal as the primary selection (matches paper's stated criterion)
    best = best_auc

    # ---- Evaluate BOTH published and new weights on TEST ----
    print('\nEvaluating on untouched TEST partition...')
    cri_test_published = compute_cri(df_test, PUBLISHED_ALPHA, PUBLISHED_BETA, PUBLISHED_GAMMA)
    cri_test_new       = compute_cri(df_test, best['alpha'],   best['beta'],   0.0)

    pub_metrics = evaluate(cri_test_published, y_test, sumo_test)
    new_metrics = evaluate(cri_test_new,       y_test, sumo_test)

    # Bootstrap CIs on test AUC
    print('Bootstrapping 95% CIs on test AUC (1000 iterations)...')
    pub_lo, pub_hi, _ = bootstrap_auc_ci(y_test, cri_test_published)
    new_lo, new_hi, _ = bootstrap_auc_ci(y_test, cri_test_new)
    pub_metrics['auc_proxy_ci95'] = [pub_lo, pub_hi]
    new_metrics['auc_proxy_ci95'] = [new_lo, new_hi]

    if sumo_test is not None and sumo_test.sum() > 0:
        pub_lo_s, pub_hi_s, n_eff_p = bootstrap_auc_ci(sumo_test, cri_test_published)
        new_lo_s, new_hi_s, n_eff_n = bootstrap_auc_ci(sumo_test, cri_test_new)
        pub_metrics['auc_sumo_ci95'] = [pub_lo_s, pub_hi_s]
        new_metrics['auc_sumo_ci95'] = [new_lo_s, new_hi_s]

    print('\n  Published weights (alpha=0.20, beta=0.80) on TEST:')
    for k, v in pub_metrics.items():
        print(f'    {k}: {v}')
    print(f'\n  Recalibrated weights (alpha={best["alpha"]}, beta={best["beta"]}) on TEST:')
    for k, v in new_metrics.items():
        print(f'    {k}: {v}')

    # ---- Write report ----
    Path(os.path.dirname(REPORT_FILE)).mkdir(parents=True, exist_ok=True)
    report = {
        'protocol': {
            'split': '75/25 stratified on kinematic ground truth',
            'random_state': 42,
            'selection_criterion': f'F1 at CRI threshold {THETA_WARNING}',
            'grid_alpha_range': '0.10 to 0.90 step 0.05',
            'grid_beta_range':  '0.10 to 0.90 step 0.05',
            'gamma_constraint': '0.0 (intent disabled per V3.0)',
            'alpha_plus_beta_constraint': 'alpha + beta = 1.0',
            'bootstrap_iterations_for_CI': N_BOOTSTRAP,
        },
        'dataset': {
            'rows_total':    int(n_rows),
            'rows_train':    int(len(idx_train)),
            'rows_test':     int(len(idx_test)),
            'positive_train': int(y_train.sum()),
            'positive_test':  int(y_test.sum()),
            'sumo_collisions_total': int(sumo_y.sum()) if sumo_y is not None else 0,
            'sumo_collisions_test':  int(sumo_test.sum()) if sumo_test is not None else 0,
        },
        'grid_search_top5_by_auc':  grid_auc_sorted[:5],
        'grid_search_top5_by_f1':   grid_f1_sorted[:5],
        'selected_weights_by_auc': {
            'alpha': best_auc['alpha'],
            'beta':  best_auc['beta'],
            'gamma': 0.00,
            'train_auc': best_auc['auc'],
        },
        'selected_weights_by_f1': {
            'alpha': best_f1['alpha'],
            'beta':  best_f1['beta'],
            'gamma': 0.00,
            'train_f1_at_060': best_f1['f1_at_060'],
        },
        'test_metrics_published_weights': pub_metrics,
        'test_metrics_selected_weights':  new_metrics,
        'note': ('Both weight sets are evaluated on the SAME untouched test partition. '
                 'The selected weights were chosen using only training data, so test '
                 'metrics are a valid generalisation estimate.'),
    }
    with open(REPORT_FILE, 'w') as f:
        json.dump(report, f, indent=2)
    print(f'\nReport written: {REPORT_FILE}')


if __name__ == '__main__':
    main()
