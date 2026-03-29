"""
run_multi_seed.py — Multi-Seed Evaluation for V2V BSD System
=============================================================
Runs the simulation with multiple random seeds and reports aggregate
performance metrics (AUC, F1, CRITICAL recall) with mean ± std.

Uses centralized ground truth from bsd_utils.compute_ground_truth()
to ensure consistency with all other evaluation scripts.

Output files (saved after all seeds complete):
  - Outputs/multi_seed_results.csv  — per-seed raw results
  - Outputs/multi_seed_summary.json — mean ± std summary
"""
import subprocess
import os
import sys
import json
import pandas as pd
import numpy as np
import argparse
from sklearn.metrics import f1_score, roc_auc_score, recall_score, average_precision_score

# Ensure centralized ground truth is used
sys.path.insert(0, os.path.dirname(__file__))
from bsd_utils import compute_ground_truth, check_coverage, GT_GAP_CRITICAL, GT_TTC_CRITICAL


def main():
    parser = argparse.ArgumentParser(description="Multi-seed V2V BSD evaluation")
    parser.add_argument('--seeds', type=int, default=5, help="Number of seeds")
    # Must match main simulation duration (3600) for comparable results
    parser.add_argument('--steps', type=int, default=3600, help="Steps per run (default 3600 to match main simulation)")
    args = parser.parse_args()

    seeds = list(range(10, 10 + args.seeds * 10, 10))
    results = []

    print(f"Using centralized thresholds: gap < {GT_GAP_CRITICAL}m, TTC < {GT_TTC_CRITICAL}s")
    print(f"Seeds: {seeds}, Steps: {args.steps}\n")

    for seed in seeds:
        print(f"\n{'=' * 50}")
        print(f"Running Seed {seed}")
        print(f"{'=' * 50}")
        cmd = [
            sys.executable, "v2v_bsd_simulation.py",
            "--no-gui",
            "--steps", str(args.steps),
            "--seed", str(seed)
        ]
        subprocess.run(cmd, timeout=600)

        try:
            df = pd.read_csv('../Outputs/bsd_metrics.csv')
        except FileNotFoundError:
            df = pd.read_csv('bsd_metrics.csv')

        # Use centralized ground truth — same thresholds as all other scripts
        y_true = compute_ground_truth(df)
        check_coverage(y_true, f'seed={seed}')
        gt_positive_rate = y_true.sum() / len(y_true) if len(y_true) > 0 else 0

        math_cri = df[['cri_left', 'cri_right']].max(axis=1).values
        y_pred_critical = (math_cri >= 0.8).astype(int)

        f1 = f1_score(y_true, y_pred_critical, zero_division=0)

        try:
            auc_math = roc_auc_score(y_true, math_cri)
        except ValueError:
            auc_math = float('nan')

        # AI AUC if available
        auc_ai = float('nan')
        if 'ai_critical_prob' in df.columns:
            try:
                auc_ai = roc_auc_score(y_true, df['ai_critical_prob'].fillna(0).values)
            except ValueError:
                pass

        # CRITICAL recall for the math model at θ=0.80
        crit_recall = recall_score(y_true, y_pred_critical, zero_division=0)

        # AUPRC
        try:
            auprc_math = average_precision_score(y_true, math_cri)
        except ValueError:
            auprc_math = float('nan')

        auprc_ai = float('nan')
        if 'ai_critical_prob' in df.columns:
            try:
                auprc_ai = average_precision_score(y_true, df['ai_critical_prob'].fillna(0).values)
            except ValueError:
                pass

        # Accuracy (4-class from AI model)
        accuracy = float('nan')
        if 'ai_alert' in df.columns:
            from sklearn.metrics import accuracy_score
            # Map alert labels to numeric
            alert_map = {'SAFE': 0, 'CAUTION': 1, 'WARNING': 2, 'CRITICAL': 3}
            y_class = pd.Series(np.where(math_cri >= 0.8, 3, np.where(math_cri >= 0.6, 2, np.where(math_cri >= 0.3, 1, 0))))
            ai_preds = df['ai_alert'].map(alert_map).fillna(0).astype(int)
            accuracy = accuracy_score(y_class, ai_preds)

        results.append({
            'seed': seed,
            'f1': f1,
            'auc_math': auc_math,
            'auc_ai': auc_ai,
            'auprc_math': auprc_math,
            'auprc_ai': auprc_ai,
            'accuracy': accuracy,
            'crit_recall': crit_recall,
            'n_rows': len(df),
            'n_positive': int(y_true.sum()),
            'gt_positive_pct': gt_positive_rate * 100,
        })

    print(f"\n{'=' * 60}")
    print("Aggregate Results (Centralized Ground Truth)")
    print(f"{'=' * 60}")
    df_res = pd.DataFrame(results)

    print(f"\n{'Seed':<8} {'Math AUC':<12} {'AI AUC':<12} {'F1 (θ=0.80)':<14} {'CRIT Recall':<14} {'GT+ %':<8}")
    print("-" * 68)
    for _, row in df_res.iterrows():
        print(f"{int(row['seed']):<8} {row['auc_math']:<12.4f} {row['auc_ai']:<12.4f} "
              f"{row['f1']:<14.4f} {row['crit_recall']:<14.4f} {row['gt_positive_pct']:<8.2f}")

    print("-" * 68)
    summary = {}
    for col, label in [('auc_math', 'Math AUC'), ('auc_ai', 'AI AUC'),
                        ('auprc_math', 'Math AUPRC'), ('auprc_ai', 'AI AUPRC'),
                        ('f1', 'F1 (θ=0.80)'), ('crit_recall', 'CRIT Recall'),
                        ('gt_positive_pct', 'GT+ %')]:
        vals = df_res[col].dropna()
        if len(vals) > 0:
            print(f"  {label:<16}: {vals.mean():.4f} ± {vals.std():.4f}")
            summary[col] = {
                'mean': round(float(vals.mean()), 6),
                'std': round(float(vals.std()), 6),
                'min': round(float(vals.min()), 6),
                'max': round(float(vals.max()), 6),
            }
    print(f"{'=' * 60}")

    # Save per-seed results to CSV
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'Outputs')
    csv_path = os.path.join(out_dir, 'multi_seed_results.csv')
    df_res.to_csv(csv_path, index=False)
    print(f"\nPer-seed results saved to {csv_path}")

    # Save summary to JSON
    json_path = os.path.join(out_dir, 'multi_seed_summary.json')
    with open(json_path, 'w') as f:
        json.dump({'n_seeds': len(seeds), 'steps_per_seed': args.steps, 'summary': summary}, f, indent=2)
    print(f"Summary saved to {json_path}")


if __name__ == "__main__":
    main()
