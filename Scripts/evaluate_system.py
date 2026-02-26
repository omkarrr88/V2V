import pandas as pd
import numpy as np
from sklearn.metrics import roc_curve, auc

def main():
    print("Loading bsd_metrics.csv...")
    try:
        df = pd.read_csv('../Outputs/bsd_metrics.csv')
    except Exception as e:
        df = pd.read_csv('bsd_metrics.csv')
        
    from bsd_utils import compute_ground_truth, check_coverage
    y_true = compute_ground_truth(df)
    check_coverage(y_true, 'evaluate_system.py')
        
    if y_true.sum() == 0:
        print("No near-misses found either. Cannot generate ROC curve.")
        return

    math_cri = df[['cri_left', 'cri_right']].max(axis=1).values
    
    if 'ai_critical_prob' in df.columns:
        ai_prob = df['ai_critical_prob'].fillna(0.0).values
    else:
        # Fallback for older CSVs if they exist
        ai_alert_map = {'SAFE': 0, 'CAUTION': 1, 'WARNING': 2, 'CRITICAL': 3, 'N/A': 0}
        ai_alerts = df['ai_alert'].map(ai_alert_map).fillna(0).values
        ai_prob = np.where(ai_alerts == 3, df['ai_confidence'], np.where(ai_alerts == 2, 0.7 * df['ai_confidence'], 0.1 * df['ai_confidence']))
    
    print("Computing ROC...")
    import matplotlib.pyplot as plt
    plt.figure(figsize=(8,6))

    fpr_math, tpr_math, _ = roc_curve(y_true, math_cri)
    auc_math = auc(fpr_math, tpr_math)
    plt.plot(fpr_math, tpr_math, label=f'Mathematical Model (AUC = {auc_math:.4f})', color='blue')
    print(f"Mathematical Model AUC: {auc_math:.4f}")
    
    fpr_ai, tpr_ai, _ = roc_curve(y_true, ai_prob)
    auc_ai = auc(fpr_ai, tpr_ai)
    plt.plot(fpr_ai, tpr_ai, label=f'AI Hybrid Predictor (AUC = {auc_ai:.4f})', color='green')
    print(f"AI Hybrid Predictor AUC: {auc_ai:.4f}")

    alert_map = {'SAFE': 0.0, 'WARNING': 0.5, 'CRITICAL': 1.0, 'N/A': 0.0}
    if 'baseline_left' in df.columns:
        ttc_base = np.maximum(df['baseline_left'].map(alert_map).fillna(0.0), df['baseline_right'].map(alert_map).fillna(0.0))
        fpr_ttc, tpr_ttc, _ = roc_curve(y_true, ttc_base)
        auc_ttc = auc(fpr_ttc, tpr_ttc)
        plt.plot(fpr_ttc, tpr_ttc, label=f'TTC Kinematic Baseline (AUC = {auc_ttc:.4f})', color='orange')
        print(f"TTC Kinematic Baseline AUC: {auc_ttc:.4f}")

    if 'static_left' in df.columns:
        stat_base = np.maximum(df['static_left'].map(alert_map).fillna(0.0), df['static_right'].map(alert_map).fillna(0.0))
        fpr_stat, tpr_stat, _ = roc_curve(y_true, stat_base)
        auc_stat = auc(fpr_stat, tpr_stat)
        plt.plot(fpr_stat, tpr_stat, label=f'Static Box Baseline (AUC = {auc_stat:.4f})', color='red')
        print(f"Static Box Baseline AUC: {auc_stat:.4f}")
    
    print("\n--- ROC Summary ---")
    print("Generating ROC Curve plot...")
    
    plt.plot([0, 1], [0, 1], 'k--')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('Receiver Operating Characteristic (ROC)')
    plt.legend(loc="lower right")
    plt.grid(True)
    plt.savefig('../Outputs/roc_curve.png')
    print("Saved ROC curve to ../Outputs/roc_curve.png")

if __name__ == '__main__':
    main()
