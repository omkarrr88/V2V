import pandas as pd
import numpy as np
from sklearn.metrics import roc_curve, auc

def main():
    print("Loading bsd_metrics.csv...")
    try:
        df = pd.read_csv('../Outputs/bsd_metrics.csv')
    except Exception as e:
        df = pd.read_csv('bsd_metrics.csv')
        
    y_true = df['ground_truth_collision'].values
    if y_true.sum() == 0:
        print("No SUMO collisions found. Building composite near-miss proxy...")
        longitudinal_nm = (df['max_gap'] < 2.0)
        lateral_nm_left  = (df.get('R_ttc_left',  pd.Series(0.0, index=df.index)) > 0.7) & \
                           (df.get('P_left',       pd.Series(0.0, index=df.index)) > 0.3)
        lateral_nm_right = (df.get('R_ttc_right', pd.Series(0.0, index=df.index)) > 0.7) & \
                           (df.get('P_right',      pd.Series(0.0, index=df.index)) > 0.3)
        y_true = (longitudinal_nm | lateral_nm_left | lateral_nm_right).astype(int).values
        
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
    fpr_math, tpr_math, _ = roc_curve(y_true, math_cri)
    auc_math = auc(fpr_math, tpr_math)
    
    fpr_ai, tpr_ai, _ = roc_curve(y_true, ai_prob)
    auc_ai = auc(fpr_ai, tpr_ai)
    
    print(f"Mathematical Model AUC: {auc_math:.4f}")
    print(f"AI Hybrid Predictor AUC: {auc_ai:.4f}")
    
    print("\n--- ROC Summary ---")
    print("Generating ROC Curve plot...")
    
    import matplotlib.pyplot as plt
    plt.figure(figsize=(8,6))
    plt.plot(fpr_math, tpr_math, label=f'Mathematical Model (AUC = {auc_math:.4f})', color='blue')
    plt.plot(fpr_ai, tpr_ai, label=f'AI Hybrid Predictor (AUC = {auc_ai:.4f})', color='green')
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
