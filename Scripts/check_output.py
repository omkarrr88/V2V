"""Check output with full details."""
import json, pandas as pd

with open("../Outputs/bsd_live.json") as f:
    data = json.load(f)

print(f"Step: {data['step']}, Active: {data['active_count']}, AI: {data.get('has_ai')}")
print(f"Alert counts: {data.get('alert_counts', {})}")

print("\n=== ALL VEHICLES WITH CRI > 0 ===")
for vid, v in data.get('vehicles', {}).items():
    max_cri = max(v.get('cri_left', 0), v.get('cri_right', 0))
    if max_cri > 0:
        print(f"  {vid}:")
        print(f"    Speed: {v['speed']:.1f} m/s | Targets: {v['num_targets']}")
        print(f"    CRI_L: {v['cri_left']:.4f} ({v['alert_left']}) | CRI_R: {v['cri_right']:.4f} ({v['alert_right']})")
        print(f"    AI: {v.get('ai_alert','N/A')} (conf: {v.get('ai_confidence',0):.1%})")
        if v.get('top_threats'):
            for t in v['top_threats']:
                print(f"    └ {t['side']} {t['vid']}: CRI={t['cri']:.4f} P={t['P']:.3f} "
                      f"R_dec={t['R_decel']:.3f} R_ttc={t['R_ttc']:.3f} R_int={t['R_intent']:.3f}")

# Check metrics CSV
df = pd.read_csv("../Outputs/bsd_metrics.csv")
print(f"\n=== METRICS CSV ({len(df)} rows) ===")
print(f"Max CRI_L: {df.cri_left.max():.4f}")
print(f"Max CRI_R: {df.cri_right.max():.4f}")
print(f"Alert L distribution: {dict(df.alert_left.value_counts())}")
print(f"Alert R distribution: {dict(df.alert_right.value_counts())}")
if 'ai_alert' in df.columns:
    print(f"AI Alert distribution: {dict(df.ai_alert.value_counts())}")
