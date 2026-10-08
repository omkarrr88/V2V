"""
critical_operating_point.py
===========================
Addresses Reviewer 2 (Round 2, point 3): "The SHAP analysis and the
four-classifier comparison all rest on learners with 0% CRITICAL recall."

The 0% CRITICAL recall reported in the four-classifier table is an artefact
of the argmax decision rule on a 4-class output with a ~0.04% positive class,
NOT an absence of CRITICAL-relevant signal: the CRITICAL-binary ranking AUC
is ~0.9 for every learner. This script makes that argument quantitative by
tuning a cost-sensitive decision threshold for the binary task
"CRITICAL vs rest" on a validation split carved out of the TRAINING data
(never the test set), then reporting held-out test recall/precision at that
operating point.

Protocol (leakage-free):
  1. Same 75/25 stratified train/test split as ml_baselines_comparison.py
     (random_state=42), same synthetic-CRITICAL injection, same features.
  2. The training partition is further split 80/20 (stratified) into
     fit / val.  SMOTE is applied to fit only.
  3. Each classifier is trained on fit; the decision threshold t* maximising
     CRITICAL-binary F1 is chosen on val.
  4. Test-set recall / precision / F1 at t* are reported, together with the
     default argmax recall (for contrast) and the CRITICAL-binary PR-AUC.

Outputs:
  - Outputs/critical_operating_point.json
  - Outputs/figures/fig16_critical_pr_curve.png  (PR curves, CRITICAL vs rest)
"""
import os
import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.metrics import (precision_recall_curve, average_precision_score,
                             precision_score, recall_score, f1_score)
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import SMOTE
import lightgbm as lgb
import xgboost as xgb

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from train_ai_model import (add_derived_features, create_target_labels,
                            generate_critical_scenarios,
                            FEATURE_COLS, DERIVED_FEATURES)

METRICS_FILE = '../Outputs/bsd_metrics.csv'
REPORT_FILE  = '../Outputs/critical_operating_point.json'
FIG_FILE     = '../Outputs/figures/fig16_critical_pr_curve.png'

# High-contrast Okabe-Ito palette (consistent with generate_paper_figures.py)
MODEL_COLORS = {
    'XGBoost':            ('#0072B2', '-'),
    'LightGBM':           ('#D55E00', '--'),
    'RandomForest':       ('#009E73', '-.'),
    'LogisticRegression': ('#000000', ':'),
}


def tune_threshold(y_val_bin, val_prob):
    """Return threshold maximising F1 on the validation split."""
    prec, rec, thr = precision_recall_curve(y_val_bin, val_prob)
    f1 = np.where((prec + rec) > 0, 2 * prec * rec / (prec + rec), 0.0)
    # precision_recall_curve returns len(thr) = len(prec) - 1
    best = int(np.argmax(f1[:-1])) if len(thr) else 0
    return float(thr[best]) if len(thr) else 0.5, float(f1[best])


def recall_priority_threshold(y_val_bin, val_prob, target_recall=0.8):
    """Lowest threshold whose validation recall reaches target_recall.
    Deliberately trades precision for recall (screening operating point)."""
    pos = np.sort(val_prob[y_val_bin == 1])
    if len(pos) == 0:
        return 0.5
    k = int(np.floor((1.0 - target_recall) * len(pos)))
    k = min(k, len(pos) - 1)
    return float(pos[k])


def main():
    print('=' * 72)
    print('Cost-sensitive CRITICAL operating-point analysis')
    print('=' * 72)

    metrics_path = METRICS_FILE if os.path.exists(METRICS_FILE) else 'bsd_metrics.csv'
    df = pd.read_csv(metrics_path)
    df = add_derived_features(df)
    features = [f for f in (FEATURE_COLS + DERIVED_FEATURES) if f in df.columns]
    X = df[features].copy()
    y = create_target_labels(df)
    print(f'  Rows: {len(df):,}  Features: {len(features)}')

    # ---- Identical outer split to ml_baselines_comparison.py ----
    X_train_raw, X_test, y_train_raw, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y)

    syn = generate_critical_scenarios(n=300)
    syn = add_derived_features(syn)
    syn_y = create_target_labels(syn)
    is_synth = pd.Series([False] * len(X_train_raw) + [True] * len(syn))
    X_train_raw = pd.concat([X_train_raw, syn[features].copy()], ignore_index=True)
    y_train_raw = pd.concat([y_train_raw, syn_y], ignore_index=True)

    # ---- Inner fit/val split (threshold tuned on val, never on test).
    #      Synthetic rows may train the model but are EXCLUDED from threshold
    #      tuning: thresholds must be chosen on the real data distribution.
    X_fit, X_val, y_fit, y_val, synth_fit, synth_val = train_test_split(
        X_train_raw, y_train_raw, is_synth, test_size=0.20, random_state=42,
        stratify=y_train_raw)
    real_val = ~synth_val.values
    X_val, y_val = X_val[real_val], y_val[real_val]
    strat = {1: max(int(y_fit.value_counts().get(1, 0)), 3000),
             2: max(int(y_fit.value_counts().get(2, 0)), 2000),
             3: max(int(y_fit.value_counts().get(3, 0)),  500)}
    X_fit_sm, y_fit_sm = SMOTE(sampling_strategy=strat, random_state=42
                               ).fit_resample(X_fit, y_fit)
    print(f'  fit={len(X_fit_sm):,} (after SMOTE)  val={len(X_val):,}  test={len(X_test):,}')
    print(f'  CRITICAL rows: fit(raw)={int((y_fit==3).sum())}  '
          f'val={int((y_val==3).sum())}  test={int((y_test==3).sum())}')

    scaler = StandardScaler().fit(X_fit_sm)

    def make_models():
        return {
            'XGBoost': xgb.XGBClassifier(
                n_estimators=200, max_depth=6, learning_rate=0.1,
                subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
                gamma=0.1, reg_alpha=0.1, reg_lambda=1.0,
                objective='multi:softprob', num_class=4, eval_metric='mlogloss',
                random_state=42, n_jobs=-1),
            'LightGBM': lgb.LGBMClassifier(
                n_estimators=200, max_depth=6, learning_rate=0.1,
                subsample=0.8, colsample_bytree=0.8, class_weight='balanced',
                objective='multiclass', num_class=4, random_state=42,
                n_jobs=-1, verbosity=-1),
            'RandomForest': RandomForestClassifier(
                n_estimators=200, max_depth=20, min_samples_split=5,
                n_jobs=-1, random_state=42, class_weight='balanced'),
            'LogisticRegression': LogisticRegression(
                max_iter=1000, class_weight='balanced', random_state=42,
                n_jobs=-1),
        }

    y_val_bin  = (y_val  >= 3).astype(int).values
    y_test_bin = (y_test >= 3).astype(int).values

    results = []
    fig, ax = plt.subplots(figsize=(6.5, 5.2))
    for name, model in make_models().items():
        print(f'\n[{name}] training ...')
        if name == 'LogisticRegression':
            model.fit(scaler.transform(X_fit_sm), y_fit_sm)
            val_prob  = model.predict_proba(scaler.transform(X_val))[:, 3]
            test_prob = model.predict_proba(scaler.transform(X_test))[:, 3]
            test_argmax = model.predict_proba(scaler.transform(X_test)).argmax(axis=1)
        else:
            model.fit(X_fit_sm, y_fit_sm)
            val_prob  = model.predict_proba(X_val)[:, 3]
            test_prob = model.predict_proba(X_test)[:, 3]
            test_argmax = model.predict_proba(X_test).argmax(axis=1)

        t_star, val_f1 = tune_threshold(y_val_bin, val_prob)
        y_hat = (test_prob >= t_star).astype(int)
        rec  = recall_score(y_test_bin, y_hat, zero_division=0)
        prec = precision_score(y_test_bin, y_hat, zero_division=0)
        f1   = f1_score(y_test_bin, y_hat, zero_division=0)
        argmax_rec = recall_score(y_test_bin, (test_argmax == 3).astype(int),
                                  zero_division=0)
        pr_auc = average_precision_score(y_test_bin, test_prob)

        # Recall-priority (screening) operating point: threshold set so that
        # validation recall reaches 80%, then frozen and applied to test.
        t_screen = recall_priority_threshold(y_val_bin, val_prob, 0.8)
        y_scr = (test_prob >= t_screen).astype(int)
        scr_rec  = recall_score(y_test_bin, y_scr, zero_division=0)
        scr_prec = precision_score(y_test_bin, y_scr, zero_division=0)
        scr_rate = float(y_scr.mean())

        print(f'  t*={t_star:.4f} (val F1={val_f1:.3f})  '
              f'test recall={rec:.3f} precision={prec:.3f} F1={f1:.3f}  '
              f'argmax recall={argmax_rec:.3f}  PR-AUC={pr_auc:.3f}')
        print(f'  screening t={t_screen:.4f}: test recall={scr_rec:.3f} '
              f'precision={scr_prec:.4f} alarm-rate={scr_rate:.4f}')
        results.append({
            'model': name,
            'threshold': t_star,
            'val_f1': val_f1,
            'test_recall_at_tstar': float(rec),
            'test_precision_at_tstar': float(prec),
            'test_f1_at_tstar': float(f1),
            'test_recall_argmax': float(argmax_rec),
            'test_pr_auc_critical': float(pr_auc),
            'screening_threshold': t_screen,
            'screening_test_recall': float(scr_rec),
            'screening_test_precision': float(scr_prec),
            'screening_alarm_rate': scr_rate,
            'n_test_critical': int(y_test_bin.sum()),
        })

        p_curve, r_curve, _ = precision_recall_curve(y_test_bin, test_prob)
        color, ls = MODEL_COLORS[name]
        ax.plot(r_curve, p_curve, color=color, ls=ls, lw=2.2,
                label=f'{name} (PR-AUC={pr_auc:.3f})')

    ax.set_xlabel('Recall (CRITICAL vs rest)', fontsize=12)
    ax.set_ylabel('Precision (CRITICAL vs rest)', fontsize=12)
    ax.set_title('CRITICAL-Class Precision-Recall (Held-Out Test)', fontsize=13)
    ax.legend(fontsize=9.5, loc='upper right')
    ax.set_xlim([0, 1]); ax.set_ylim([0, 1.02])
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    Path(os.path.dirname(FIG_FILE)).mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_FILE, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'\nFigure written: {FIG_FILE}')

    out = {
        'protocol': {
            'outer_split': '75/25 stratified, random_state=42 (same as ml_baselines_comparison)',
            'inner_split': '80/20 stratified fit/val from training partition',
            'smote': 'applied to fit portion only',
            'threshold_rule': 'maximise CRITICAL-binary F1 on val; frozen before test',
        },
        'results': results,
    }
    Path(os.path.dirname(REPORT_FILE)).mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, 'w') as f:
        json.dump(out, f, indent=2)
    print(f'Report written: {REPORT_FILE}')


if __name__ == '__main__':
    main()
