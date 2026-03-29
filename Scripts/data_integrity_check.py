"""
data_integrity_check.py — Pre-submission Data Consistency Verifier
==================================================================
Reads bsd_training_report.json and feature_importance.csv and verifies
that the top features and importance values are consistent between both files.

Run this before any paper submission to catch mismatches.

Usage: python data_integrity_check.py
"""
import json
import os
import sys
import pandas as pd

# Fix Windows console encoding for emoji output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    report_path = os.path.join('..', 'Outputs', 'bsd_training_report.json')
    csv_path = os.path.join('..', 'Outputs', 'feature_importance.csv')
    
    # Fallback paths (if run from project root)
    if not os.path.exists(report_path):
        report_path = os.path.join('Outputs', 'bsd_training_report.json')
        csv_path = os.path.join('Outputs', 'feature_importance.csv')

    errors = []

    # Check files exist
    if not os.path.exists(report_path):
        print(f"❌ FAIL: {report_path} not found")
        sys.exit(1)
    if not os.path.exists(csv_path):
        print(f"❌ FAIL: {csv_path} not found")
        sys.exit(1)

    # Load data
    with open(report_path) as f:
        report = json.load(f)
    
    df_csv = pd.read_csv(csv_path)
    report_fi = report.get('feature_importance', {})

    if not report_fi:
        errors.append("Training report has no 'feature_importance' key")
    if df_csv.empty:
        errors.append("feature_importance.csv is empty")

    if not errors:
        # Check 1: Top feature matches
        csv_top = df_csv.iloc[0]['feature']
        report_top = max(report_fi, key=report_fi.get)
        if csv_top != report_top:
            errors.append(f"Top feature mismatch: CSV='{csv_top}', Report='{report_top}'")
        else:
            print(f"✅ Top feature matches: {csv_top}")

        # Check 2: Top-5 feature order matches
        csv_top5 = list(df_csv.head(5)['feature'])
        report_sorted = sorted(report_fi.items(), key=lambda x: x[1], reverse=True)
        report_top5 = [r[0] for r in report_sorted[:5]]
        if csv_top5 != report_top5:
            errors.append(f"Top-5 order mismatch:\n  CSV:    {csv_top5}\n  Report: {report_top5}")
        else:
            print(f"✅ Top-5 feature order matches: {csv_top5}")

        # Check 3: Values within tolerance (gain normalization may differ slightly)
        TOLERANCE = 0.005
        for _, row in df_csv.head(5).iterrows():
            feat = row['feature']
            csv_val = row['importance']
            report_val = report_fi.get(feat, -1)
            if abs(csv_val - report_val) > TOLERANCE:
                errors.append(
                    f"Value mismatch for '{feat}': CSV={csv_val:.4f}, Report={report_val:.4f} "
                    f"(diff={abs(csv_val - report_val):.4f} > {TOLERANCE})")
            else:
                print(f"✅ {feat}: CSV={csv_val:.4f}, Report={report_val:.4f}")

        # Check 4: CV std is non-zero (cross-validation actually ran)
        cv_std = report.get('cv_accuracy_std', report.get('cv_std', None))
        if cv_std is not None and cv_std == 0.0:
            errors.append("cv_accuracy_std is 0.0 — cross-validation may not have run properly")
        elif cv_std is not None:
            print(f"✅ Cross-validation std is non-zero: {cv_std:.4f}")

    # Summary
    print(f"\n{'=' * 50}")
    if errors:
        print(f"❌ FAIL: {len(errors)} issue(s) found:")
        for e in errors:
            print(f"  • {e}")
        print("\nRun train_ai_model.py to regenerate both files from the same training run.")
        sys.exit(1)
    else:
        print("✅ PASS: All data integrity checks passed.")
        print("Feature importance CSV and training report are consistent.")
        sys.exit(0)


if __name__ == '__main__':
    main()
