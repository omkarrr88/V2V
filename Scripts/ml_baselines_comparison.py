"""
ml_baselines_comparison.py
==========================
Trains and evaluates Random Forest, LightGBM, and Logistic Regression on the
same 15-feature table used by XGBoost. All four classifiers face the identical
class-imbalance problem (only 54 CRITICAL events in 146 k rows).

Addresses Reviewer 4 (point 10): "XGBoost performance poor - have you tried
other methods?" Answers by demonstrating all data-driven methods hit the same
rare-event ceiling.

Outputs:
  - Outputs/ml_baselines_report.json
"""
import os
import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import (roc_auc_score, classification_report,
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
REPORT_FILE  = '../Outputs/ml_baselines_report.json'


def evaluate_classifier(name, model, X_test, y_test, multi=True):
    """Return AUC + per-class metrics for one classifier."""
    if multi and hasattr(model, 'predict_proba'):
        probs = model.predict_proba(X_test)
        # If the model didn't see all 4 classes during training, pad with zeros
        if probs.shape[1] < 4:
            padded = np.zeros((probs.shape[0], 4))
            for i, c in enumerate(model.classes_):
                padded[:, int(c)] = probs[:, i]
            probs = padded
        y_pred = probs.argmax(axis=1)
        crit_prob = probs[:, 3]
        # AUC: macro one-vs-rest on multiclass; AUC for binary (CRITICAL vs rest) for safety
        try:
            auc_macro = float(roc_auc_score(y_test, probs, multi_class='ovr', average='macro',
                                             labels=[0, 1, 2, 3]))
        except Exception:
            auc_macro = None
        y_bin_crit = (y_test >= 3).astype(int)
        auc_crit = float(roc_auc_score(y_bin_crit, crit_prob)) if y_bin_crit.sum() > 0 else None
    else:
        y_pred = model.predict(X_test)
        crit_prob = np.zeros(len(y_test))
        auc_macro = None
        auc_crit  = None

    class_names = ['SAFE', 'CAUTION', 'WARNING', 'CRITICAL']
    report = classification_report(y_test, y_pred, target_names=class_names[:len(np.unique(y_test))],
                                    output_dict=True, zero_division=0, labels=[0, 1, 2, 3])
    out = {
        'model': name,
        'auc_macro_ovr': auc_macro,
        'auc_critical_binary': auc_crit,
        'per_class': {
            cls: {
                'precision': float(report.get(cls, {}).get('precision', 0.0)),
                'recall':    float(report.get(cls, {}).get('recall', 0.0)),
                'f1':        float(report.get(cls, {}).get('f1-score', 0.0)),
                'support':   int(  report.get(cls, {}).get('support', 0)),
            } for cls in class_names
        },
        'overall_accuracy': float(report.get('accuracy', 0.0)),
        'macro_f1':         float(report.get('macro avg', {}).get('f1-score', 0.0)),
        'weighted_f1':      float(report.get('weighted avg', {}).get('f1-score', 0.0)),
    }
    return out


def main():
    print('=' * 72)
    print('ML Baselines Comparison: XGBoost vs RF vs LightGBM vs Logistic Regression')
    print('=' * 72)

    metrics_path = METRICS_FILE if os.path.exists(METRICS_FILE) else 'bsd_metrics.csv'
    print(f'Loading {metrics_path} ...')
    df = pd.read_csv(metrics_path)
    df = add_derived_features(df)

    features = [f for f in (FEATURE_COLS + DERIVED_FEATURES) if f in df.columns]
    X = df[features].copy()
    y = create_target_labels(df)
    print(f'  Rows: {len(df):,}  Features: {len(features)}')
    print(f'  Class counts: {y.value_counts().to_dict()}')

    # ---- 75/25 stratified split, same protocol as train_ai_model.py ----
    X_train_raw, X_test, y_train_raw, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y)

    # ---- Inject synthetic CRITICAL into TRAINING only (matches XGBoost protocol) ----
    syn = generate_critical_scenarios(n=300)
    syn = add_derived_features(syn)
    syn_y = create_target_labels(syn)
    syn_X = syn[features].copy()
    X_train_raw = pd.concat([X_train_raw, syn_X], ignore_index=True)
    y_train_raw = pd.concat([y_train_raw, syn_y], ignore_index=True)

    # ---- SMOTE on training only ----
    strat = {1: max(int(y_train_raw.value_counts().get(1, 0)), 3000),
             2: max(int(y_train_raw.value_counts().get(2, 0)), 2000),
             3: max(int(y_train_raw.value_counts().get(3, 0)),  500)}
    smote = SMOTE(sampling_strategy=strat, random_state=42)
    X_train, y_train = smote.fit_resample(X_train_raw, y_train_raw)
    print(f'  After SMOTE + synthetic: train={len(X_train):,}, test={len(X_test):,}')
    print(f'  Train class counts: {pd.Series(y_train).value_counts().to_dict()}')

    classifiers = {}

    # ---- 1. XGBoost (re-trained for fair comparison) ----
    print('\n[1/4] Training XGBoost ...')
    xgb_clf = xgb.XGBClassifier(
        n_estimators=200, max_depth=6, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
        gamma=0.1, reg_alpha=0.1, reg_lambda=1.0,
        objective='multi:softprob', num_class=4, eval_metric='mlogloss',
        random_state=42, n_jobs=-1)
    xgb_clf.fit(X_train, y_train, verbose=False)
    classifiers['XGBoost'] = xgb_clf

    # ---- 2. Random Forest ----
    print('[2/4] Training Random Forest ...')
    rf_clf = RandomForestClassifier(n_estimators=200, max_depth=20, min_samples_split=5,
                                     n_jobs=-1, random_state=42, class_weight='balanced')
    rf_clf.fit(X_train, y_train)
    classifiers['RandomForest'] = rf_clf

    # ---- 3. LightGBM ----
    print('[3/4] Training LightGBM ...')
    lgb_clf = lgb.LGBMClassifier(n_estimators=200, max_depth=6, learning_rate=0.1,
                                  subsample=0.8, colsample_bytree=0.8,
                                  class_weight='balanced', objective='multiclass',
                                  num_class=4, random_state=42, n_jobs=-1, verbosity=-1)
    lgb_clf.fit(X_train, y_train)
    classifiers['LightGBM'] = lgb_clf

    # ---- 4. Logistic Regression (with standardisation) ----
    print('[4/4] Training Logistic Regression ...')
    scaler = StandardScaler()
    X_train_std = scaler.fit_transform(X_train)
    X_test_std  = scaler.transform(X_test)
    lr_clf = LogisticRegression(max_iter=1000, class_weight='balanced',
                                 multi_class='multinomial', random_state=42, n_jobs=-1)
    lr_clf.fit(X_train_std, y_train)

    # ---- Evaluate all on same TEST set ----
    print('\nEvaluating on held-out test set ...')
    results = []
    for name, clf in classifiers.items():
        res = evaluate_classifier(name, clf, X_test, y_test)
        results.append(res)
    lr_res = evaluate_classifier('LogisticRegression', lr_clf, X_test_std, y_test)
    results.append(lr_res)

    # ---- Print summary ----
    print('\n' + '=' * 90)
    print(f'{"Model":20s} {"AUC (macro)":>13s} {"AUC (CRIT bin)":>16s} '
          f'{"Macro F1":>10s} {"CRIT recall":>13s} {"Accuracy":>10s}')
    print('-' * 90)
    for r in results:
        crit_recall = r['per_class']['CRITICAL']['recall']
        print(f'{r["model"]:20s} {r["auc_macro_ovr"] or 0:>13.4f} '
              f'{r["auc_critical_binary"] or 0:>16.4f} '
              f'{r["macro_f1"]:>10.4f} {crit_recall:>13.4f} {r["overall_accuracy"]:>10.4f}')
    print('=' * 90)

    Path(os.path.dirname(REPORT_FILE)).mkdir(parents=True, exist_ok=True)
    out = {
        'protocol': {
            'split': '75/25 stratified',
            'random_state': 42,
            'synthetic_critical_in_train': 300,
            'smote_targets': strat,
            'features': features,
        },
        'dataset': {
            'rows_total': int(len(df)),
            'rows_train': int(len(X_train)),
            'rows_test':  int(len(X_test)),
            'class_counts_test': {int(k): int(v) for k, v in pd.Series(y_test).value_counts().items()},
        },
        'results': results,
    }
    with open(REPORT_FILE, 'w') as f:
        json.dump(out, f, indent=2)
    print(f'\nReport written: {REPORT_FILE}')


if __name__ == '__main__':
    main()
