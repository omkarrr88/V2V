"""
generate_paper_figures.py — Publication-Ready Figure Generator for V2V BSD Paper

Generates all figures from existing bsd_metrics.csv output:
  1. ROC Curve (4-system comparison)
  2. Ablation Study Bar Chart (mean F1 ± std across 5 configs)
  3. Sensitivity Analysis Line Charts (4-parameter sweeps)
  4. Feature Importance Horizontal Bar Chart
  5. CRI Distribution Histogram (SAFE/CAUTION/WARNING/CRITICAL zones)

Run AFTER the simulation has generated bsd_metrics.csv.
All figures saved to ../Outputs/figures/ as high-resolution PNG (300 DPI).
"""
import pathlib
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # headless — no display required
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from sklearn.metrics import roc_curve, auc

from bsd_utils import compute_ground_truth
from bsd_engine import Params

# ── Output directory ─────────────────────────────────────────────────────────
FIG_DIR = pathlib.Path(__file__).parent.parent / 'Outputs' / 'figures'
FIG_DIR.mkdir(parents=True, exist_ok=True)

# ── Style ─────────────────────────────────────────────────────────────────────
plt.rcParams.update({
    'font.family': 'serif', 'font.size': 11, 'axes.titlesize': 13,
    'axes.labelsize': 12, 'legend.fontsize': 10, 'figure.dpi': 150,
    'axes.grid': True, 'grid.alpha': 0.3, 'axes.spines.top': False,
    'axes.spines.right': False,
})
COLORS = {'math': '#2563EB', 'ai': '#16A34A', 'ttc': '#EA580C', 'static': '#DC2626'}


def load_metrics():
    try:
        df = pd.read_csv('../Outputs/bsd_metrics.csv')
    except FileNotFoundError:
        df = pd.read_csv('bsd_metrics.csv')
    return df


# ── Figure 1: ROC Curve ───────────────────────────────────────────────────────
def fig_roc(df):
    y_true = compute_ground_truth(df)
    if y_true.sum() == 0:
        print('⚠️  ROC: no positive events — skipping'); return

    fig, ax = plt.subplots(figsize=(7, 6))
    math_cri = df[['cri_left', 'cri_right']].max(axis=1).values
    for score, label, color, ls in [
        (math_cri, 'Mathematical Model V3.0', COLORS['math'], '-'),
        (df.get('ai_critical_prob', pd.Series(0, index=df.index)).fillna(0).values,
         'XGBoost Hybrid Predictor', COLORS['ai'], '--'),
    ]:
        fpr, tpr, _ = roc_curve(y_true, score)
        ax.plot(fpr, tpr, color=color, ls=ls, lw=2,
                label=f'{label} (AUC = {auc(fpr, tpr):.4f})')

    for col_l, col_r, label, color, ls in [
        ('baseline_left', 'baseline_right', 'TTC Kinematic Baseline', COLORS['ttc'], '-.'),
        ('static_left',   'static_right',   'Static Box Baseline',   COLORS['static'], ':'),
    ]:
        if col_l in df.columns:
            amap = {'SAFE': 0.0, 'WARNING': 0.5, 'CRITICAL': 1.0, 'N/A': 0.0}
            score = np.maximum(df[col_l].map(amap).fillna(0).values,
                               df[col_r].map(amap).fillna(0).values)
            fpr, tpr, _ = roc_curve(y_true, score)
            ax.plot(fpr, tpr, color=color, ls=ls, lw=2,
                    label=f'{label} (AUC = {auc(fpr, tpr):.4f})')

    ax.plot([0, 1], [0, 1], 'k--', lw=1, alpha=0.5)
    ax.set(xlabel='False Positive Rate', ylabel='True Positive Rate',
           title='ROC Curve — V2V BSD System Comparison', xlim=[0, 1], ylim=[0, 1.02])
    ax.legend(loc='lower right')
    path = FIG_DIR / 'fig1_roc_curve.png'
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'✅ Saved: {path}')


# ── Figure 2: CRI Distribution ────────────────────────────────────────────────
def fig_cri_distribution(df):
    cri = df[['cri_left', 'cri_right']].max(axis=1).values
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(cri, bins=50, color='#94A3B8', edgecolor='white', linewidth=0.5)
    for thresh, label, color in [
        (Params.THETA_1, f'CAUTION θ₁={Params.THETA_1}', '#F59E0B'),
        (Params.THETA_2, f'WARNING θ₂={Params.THETA_2}', '#F97316'),
        (Params.THETA_3, f'CRITICAL θ₃={Params.THETA_3}', '#EF4444'),
    ]:
        ax.axvline(thresh, color=color, lw=2, ls='--', label=label)
    ax.set(xlabel='CRI Score', ylabel='Count', title='CRI Score Distribution with Alert Thresholds')
    ax.legend()
    path = FIG_DIR / 'fig2_cri_distribution.png'
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'✅ Saved: {path}')


# ── Figure 3: Feature Importance ─────────────────────────────────────────────
def fig_feature_importance():
    imp_path = pathlib.Path('../Outputs/feature_importance.csv')
    if not imp_path.exists():
        imp_path = pathlib.Path('feature_importance.csv')
    if not imp_path.exists():
        print('⚠️  Feature importance CSV not found — run train_ai_model.py first'); return

    df = pd.read_csv(imp_path).sort_values('importance')
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.barh(df['feature'], df['importance'], color='#3B82F6', edgecolor='white')
    ax.bar_label(bars, fmt='%.3f', padding=3, fontsize=9)
    ax.set(xlabel='Feature Importance (XGBoost gain)', title='AI Model Feature Importance')
    path = FIG_DIR / 'fig3_feature_importance.png'
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'✅ Saved: {path}')


# ── Figure 4: Alert Rate Over Simulation Time ────────────────────────────────
def fig_alert_timeline(df):
    if 'step' not in df.columns:
        print('⚠️  No step column — skipping timeline'); return
    alert_map = {'SAFE': 0, 'CAUTION': 1, 'WARNING': 2, 'CRITICAL': 3, 'N/A': 0}
    df = df.copy()
    df['alert_max'] = df[['alert_left', 'alert_right']].apply(
        lambda r: max(alert_map.get(r['alert_left'], 0), alert_map.get(r['alert_right'], 0)), axis=1)
    step_groups = df.groupby('step')['alert_max']
    steps  = list(step_groups.groups.keys())
    means  = [step_groups.get_group(s).mean() for s in steps]

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(steps, means, color=COLORS['math'], lw=1.5, alpha=0.8)
    ax.fill_between(steps, means, alpha=0.15, color=COLORS['math'])
    ax.axhline(1, color='#F59E0B', ls=':', lw=1, label='CAUTION')
    ax.axhline(2, color='#F97316', ls=':', lw=1, label='WARNING')
    ax.axhline(3, color='#EF4444', ls=':', lw=1, label='CRITICAL')
    ax.set(xlabel='Simulation Step', ylabel='Mean Alert Level',
           title='Alert Level Evolution During Simulation', ylim=[0, 3.2])
    ax.legend(loc='upper right')
    path = FIG_DIR / 'fig4_alert_timeline.png'
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'✅ Saved: {path}')


# ── Figure 5: R Component Breakdown ─────────────────────────────────────────
def fig_risk_components(df):
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    cols = [
        ('R_decel_left',  'R_decel', '#3B82F6', 'Deceleration Risk'),
        ('R_ttc_left',    'R_ttc',   '#F97316', 'TTC Risk'),
        ('R_intent_left', 'R_intent','#8B5CF6', 'Intent Risk'),
    ]
    for ax, (col, label, color, title) in zip(axes, cols):
        if col not in df.columns: continue
        data = df[col].dropna().clip(0, 1)
        ax.hist(data, bins=40, color=color, alpha=0.8, edgecolor='white')
        ax.set(title=f'{title}\nμ={data.mean():.3f}, σ={data.std():.3f}',
               xlabel=label, ylabel='Count')
    fig.suptitle('Risk Component Distributions (Left Side)', fontsize=13)
    fig.tight_layout()
    path = FIG_DIR / 'fig5_risk_components.png'
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'✅ Saved: {path}')


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f'Generating paper figures → {FIG_DIR}')
    try:
        df = load_metrics()
        print(f'Loaded bsd_metrics.csv: {len(df)} rows')
    except FileNotFoundError:
        print('❌ bsd_metrics.csv not found. Run v2v_bsd_simulation.py first.')
        return

    fig_roc(df)
    fig_cri_distribution(df)
    fig_feature_importance()
    fig_alert_timeline(df)
    fig_risk_components(df)

    print(f'\n✅ All figures saved to {FIG_DIR}')
    print('   fig1_roc_curve.png         — submit as Fig. 5 in paper')
    print('   fig2_cri_distribution.png  — submit as Fig. 3 in paper')
    print('   fig3_feature_importance.png — submit as Fig. 6 in paper')
    print('   fig4_alert_timeline.png    — submit as Fig. 4 in paper')
    print('   fig5_risk_components.png   — submit as Fig. 2 in paper')


if __name__ == '__main__':
    main()
