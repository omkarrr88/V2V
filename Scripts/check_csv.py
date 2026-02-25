import pandas as pd
df = pd.read_csv('../Outputs/bsd_metrics.csv')
required = ['step','ego_vid','speed','accel','yaw_rate','max_gap','rel_speed',
            'cri_left','cri_right','alert_left','alert_right',
            'baseline_left','baseline_right','ground_truth_collision',
            'P_left','R_decel_left','R_ttc_left','R_intent_left','plr_mult_left',
            'P_right','R_decel_right','R_ttc_right','R_intent_right','plr_mult_right',
            'num_targets','signals','ai_alert','ai_confidence','ai_critical_prob']
missing = [c for c in required if c not in df.columns]
print(f'Rows: {len(df)}, Columns: {len(df.columns)}')
print(f'Missing: {missing if missing else "NONE ✅"}')
print(f'ai_critical_prob sample: {df["ai_critical_prob"].describe()}')
print(f'Near-miss events (composite proxy): {((df["max_gap"]<2.0) | (df["R_ttc_left"]>0.7)).sum()}')
