"""
shap_analysis.py
================
Computes SHAP values on the existing trained XGBoost model and exports two
figures: a beeswarm summary plot and a dependence plot for the top feature.

Addresses Reviewer 1 (point 3): SHAP for feature interpretation.

Outputs:
  - Outputs/figures/fig14_shap_summary.png
  - Outputs/figures/fig15_shap_dependence_decel.png
  - Outputs/shap_report.json (mean |SHAP| per feature)
"""
import os
import sys
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import shap
import xgboost as xgb
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from train_ai_model import add_derived_features, create_target_labels, FEATURE_COLS, DERIVED_FEATURES

METRICS_FILE = '../Outputs/bsd_metrics.csv'
MODEL_FILE   = '../Outputs/bsd_xgboost_model.json'
FIG_DIR      = '../Outputs/figures'
REPORT_FILE  = '../Outputs/shap_report.json'

SAMPLE_SIZE  = 5000     # SHAP computation is O(N*M*depth), keep tractable
TOP_FEATURE_OVERRIDE = 'decel'   # dependence plot focal feature


def main():
    print('=' * 72)
    print('SHAP Analysis on Trained XGBoost Model')
    print('=' * 72)

    metrics_path = METRICS_FILE if os.path.exists(METRICS_FILE) else 'bsd_metrics.csv'
    print(f'Loading {metrics_path} ...')
    df = pd.read_csv(metrics_path)
    df = add_derived_features(df)

    available_features = [f for f in (FEATURE_COLS + DERIVED_FEATURES) if f in df.columns]
    print(f'  Features: {len(available_features)}')

    X = df[available_features].copy()
    y = create_target_labels(df)

    print(f'  Loading model {MODEL_FILE} ...')
    model = xgb.XGBClassifier()
    model.load_model(MODEL_FILE)

    # ---- Stratified sample for SHAP (full set is too large) ----
    rng = np.random.default_rng(42)
    classes = y.unique()
    sample_idx = []
    per_class = max(SAMPLE_SIZE // len(classes), 50)
    for c in classes:
        cls_idx = np.where(y == c)[0]
        if len(cls_idx) == 0:
            continue
        take = min(per_class, len(cls_idx))
        sample_idx.extend(rng.choice(cls_idx, size=take, replace=False).tolist())
    sample_idx = np.array(sample_idx)
    X_sample = X.iloc[sample_idx].reset_index(drop=True)
    y_sample = y.iloc[sample_idx].reset_index(drop=True)
    print(f'  SHAP sample size: {len(X_sample)} ({len(classes)} classes, ~{per_class}/class)')

    # ---- Compute SHAP values ----
    print('  Computing SHAP values (tree explainer)...')
    explainer = shap.TreeExplainer(model)
    sv = explainer.shap_values(X_sample)
    # XGBoost multi-class returns shape (n_samples, n_features, n_classes)
    # or list of n_classes arrays. Normalise to per-class list.
    if isinstance(sv, list):
        shap_per_class = sv
    elif sv.ndim == 3:
        shap_per_class = [sv[:, :, k] for k in range(sv.shape[2])]
    else:
        shap_per_class = [sv]

    label_names = {0: 'SAFE', 1: 'CAUTION', 2: 'WARNING', 3: 'CRITICAL'}
    n_classes_model = len(shap_per_class)

    # ---- Mean |SHAP| per feature, aggregated across classes ----
    abs_means_per_class = {}
    for k, sv_k in enumerate(shap_per_class):
        abs_means_per_class[label_names.get(k, f'class_{k}')] = {
            f: float(np.abs(sv_k[:, i]).mean()) for i, f in enumerate(available_features)
        }

    # Overall importance = sum of class-wise mean |SHAP|
    overall_importance = {f: 0.0 for f in available_features}
    for cls, d in abs_means_per_class.items():
        for f, v in d.items():
            overall_importance[f] += v

    sorted_overall = sorted(overall_importance.items(), key=lambda kv: kv[1], reverse=True)
    print('\n  Mean |SHAP| (summed across classes):')
    for f, v in sorted_overall:
        bar = '#' * max(1, int(50 * v / max(sorted_overall[0][1], 1e-9)))
        print(f'    {f:18s} {v:.4f}  {bar}')

    # ---- Figure 1: beeswarm summary for CRITICAL class ----
    Path(FIG_DIR).mkdir(parents=True, exist_ok=True)

    crit_idx = min(3, n_classes_model - 1)
    print(f'\n  Generating beeswarm summary for class {label_names.get(crit_idx, crit_idx)}...')
    plt.figure(figsize=(9, 6))
    shap.summary_plot(shap_per_class[crit_idx], X_sample, feature_names=available_features,
                      show=False, max_display=15)
    fig = plt.gcf()
    fig.suptitle(f'SHAP feature impact on {label_names.get(crit_idx, crit_idx)} class',
                 fontsize=12, y=1.02)
    fig.savefig(f'{FIG_DIR}/fig14_shap_summary.png', dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'  Saved {FIG_DIR}/fig14_shap_summary.png')

    # ---- Figure 2: dependence plot for top feature ----
    top_feature = TOP_FEATURE_OVERRIDE if TOP_FEATURE_OVERRIDE in available_features else sorted_overall[0][0]
    print(f'  Generating dependence plot for "{top_feature}"...')
    plt.figure(figsize=(8, 5))
    shap.dependence_plot(top_feature, shap_per_class[crit_idx], X_sample,
                         feature_names=available_features, show=False)
    fig = plt.gcf()
    fig.suptitle(f'SHAP dependence: {top_feature} on {label_names.get(crit_idx, crit_idx)}',
                 fontsize=12, y=1.02)
    fig.savefig(f'{FIG_DIR}/fig15_shap_dependence_decel.png', dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'  Saved {FIG_DIR}/fig15_shap_dependence_decel.png')

    # ---- Save numeric report ----
    report = {
        'protocol': {
            'model_file': MODEL_FILE,
            'sample_size': int(len(X_sample)),
            'features': available_features,
            'classes_in_model': int(n_classes_model),
            'explainer': 'shap.TreeExplainer',
        },
        'mean_abs_shap_per_class': abs_means_per_class,
        'overall_importance_sum': dict(sorted_overall),
        'top_5_features': [f for f, _ in sorted_overall[:5]],
    }
    with open(REPORT_FILE, 'w') as f:
        json.dump(report, f, indent=2)
    print(f'\nReport written: {REPORT_FILE}')


if __name__ == '__main__':
    main()
