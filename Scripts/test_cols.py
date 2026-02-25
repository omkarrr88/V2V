import pandas as pd
df = pd.read_csv('../Outputs/bsd_metrics.csv')
required = ['step','ego_vid','speed','max_gap','rel_speed','cri_left','cri_right',
            'alert_left','alert_right','baseline_left','baseline_right',
            'ground_truth_collision','ai_alert','ai_confidence',
            'P_left','R_decel_left','R_ttc_left','R_intent_left',
            'P_right','R_decel_right','R_ttc_right','R_intent_right']
missing = [c for c in required if c not in df.columns]
print('Rows:', len(df))
print('Missing columns:', missing if missing else 'NONE \u2705')
print(df[['speed','max_gap','cri_left','alert_left','baseline_left']].head(3))
