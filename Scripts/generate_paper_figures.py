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


# ── Figure 6: Scenario Comparison Timeseries ───────────────────────────────
def fig_scenario_comparison(df):
    if 'scenario_type' not in df.columns or 'step' not in df.columns:
        print('⚠️  No scenario_type column — skipping scenario comparison'); return
    
    cri = df[['cri_left', 'cri_right']].max(axis=1)
    df_plot = df.copy()
    df_plot['cri_max'] = cri
    
    fig, ax = plt.subplots(figsize=(12, 5))
    
    scenario_colors = {'normal': '#3B82F6', 'TSV': '#EF4444', 'HNR': '#F59E0B'}
    
    for sc_type in df_plot['scenario_type'].unique():
        sc_df = df_plot[df_plot['scenario_type'] == sc_type]
        if sc_df.empty:
            continue
        step_mean = sc_df.groupby('step')['cri_max'].mean()
        color = scenario_colors.get(sc_type, '#64748B')
        ax.plot(step_mean.index, step_mean.values, color=color, lw=1.2, alpha=0.8, label=sc_type)
        ax.fill_between(step_mean.index, step_mean.values, alpha=0.1, color=color)
    
    # Mark scenario boundaries
    ax.axhline(Params.THETA_1, color='#F59E0B', ls=':', lw=1, alpha=0.5)
    ax.axhline(Params.THETA_2, color='#F97316', ls=':', lw=1, alpha=0.5)
    ax.axhline(Params.THETA_3, color='#EF4444', ls=':', lw=1, alpha=0.5)
    
    ax.set(xlabel='Simulation Step', ylabel='Mean CRI (max side)',
           title='CRI Evolution by Scenario Type')
    ax.legend(loc='upper right')
    path = FIG_DIR / 'fig6_scenario_comparison.png'
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'✅ Saved: {path}')


# ── Figure 7: Confusion Matrix (XGBoost 4-Class) ────────────────────────────
def fig_confusion_matrix(df):
    from sklearn.metrics import confusion_matrix
    import seaborn as sns

    if 'ai_alert' not in df.columns:
        print('⚠️  ai_alert column missing from bsd_metrics.csv — skipping confusion matrix'); return

    # True labels from physics model CRI thresholds (what the AI is trained to replicate)
    cri_max = df[['cri_left', 'cri_right']].max(axis=1)
    y_true = pd.Series(0, index=df.index)
    y_true[cri_max >= Params.THETA_1] = 1  # CAUTION
    y_true[cri_max >= Params.THETA_2] = 2  # WARNING
    y_true[cri_max >= Params.THETA_3] = 3  # CRITICAL

    # Predicted labels from XGBoost ai_alert column
    alert_map = {'SAFE': 0, 'CAUTION': 1, 'WARNING': 2, 'CRITICAL': 3}
    valid_mask = df['ai_alert'].isin(alert_map.keys())
    if valid_mask.sum() == 0:
        print('⚠️  No valid AI predictions in ai_alert column — skipping confusion matrix'); return

    y_pred = df.loc[valid_mask, 'ai_alert'].map(alert_map)
    y_true = y_true[valid_mask]

    labels = [0, 1, 2, 3]
    label_names = ['SAFE', 'CAUTION', 'WARNING', 'CRITICAL']
    cm = confusion_matrix(y_true, y_pred, labels=labels)

    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', cbar=False, ax=ax,
                xticklabels=label_names, yticklabels=label_names)
    ax.set(xlabel='Predicted (XGBoost)', ylabel='True (Physics CRI)',
           title='XGBoost 4-Class Confusion Matrix')
    path = FIG_DIR / 'fig7_confusion_matrix.png'
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'✅ Saved: {path}')

# ── Figure 8: Sensitivity Analysis ─────────────────────────────────────────
def fig_sensitivity_analysis():
    try:
        df_sens = pd.read_csv('../Outputs/sensitivity_results.csv')
    except Exception:
        try:
            df_sens = pd.read_csv('sensitivity_results.csv')
        except Exception:
            print('⚠️  sensitivity_results.csv not found. Run sensitivity_analysis.py first.'); return

    params_to_plot = ['SIGMA_GPS', 'PLR', 'TTC_CRIT', 'THETA_3', 'MU']
    # Filter to only parameters present in the data
    params_to_plot = [p for p in params_to_plot if p in df_sens['Parameter'].values]
    n = len(params_to_plot)
    if n <= 4:
        fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    else:
        fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    axes = axes.flatten()

    for ax, p in zip(axes, params_to_plot):
        sub_df = df_sens[df_sens['Parameter'] == p]
        if sub_df.empty: continue
        label_map = {'SIGMA_GPS': r'$\sigma_{gps}$ (m)', 'PLR': r'$p_{G \to B}$',
                     'TTC_CRIT': r'$TTC_{crit}$ (s)', 'THETA_3': r'$\theta_3$',
                     'MU': r'$\mu$'}
        ax.plot(sub_df['Value'], sub_df['F1'], marker='o', lw=2, color=COLORS['math'])
        ax.set(title=f'Sensitivity to {label_map.get(p, p)}',
               xlabel=label_map.get(p, p), ylabel='F1 Score (CRITICAL)')
        ax.grid(True, linestyle='--', alpha=0.6)

    # Hide unused subplot axes
    for i in range(len(params_to_plot), len(axes)):
        axes[i].set_visible(False)

    fig.tight_layout()
    path = FIG_DIR / 'fig8_sensitivity_analysis.png'
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
    fig_scenario_comparison(df)
    fig_confusion_matrix(df)
    fig_sensitivity_analysis()

    # New figures (9-14)
    fig_pr_curve(df)
    fig_cri_timeseries(df)
    fig_calibration(df)
    fig_feature_correlation(df)
    fig_speed_cri_scatter(df)
    fig_component_correlation(df)

    print(f'\n✅ All figures saved to {FIG_DIR}')
    print('   fig1_roc_curve.png              — ROC comparison')
    print('   fig2_cri_distribution.png       — CRI distribution')
    print('   fig3_feature_importance.png     — AI feature importance')
    print('   fig4_alert_timeline.png         — Alert level evolution')
    print('   fig5_risk_components.png        — Risk component distributions')
    print('   fig6_scenario_comparison.png    — Scenario CRI timeseries')
    print('   fig7_confusion_matrix.png       — Confusion Matrix')
    print('   fig8_sensitivity_analysis.png   — Sensitivity Analysis grids')
    print('   fig9_pr_curve.png               — Precision-Recall curve')
    print('   fig10_cri_timeseries.png        — CRI time-series example')
    print('   fig11_calibration.png           — Calibration plot')
    print('   fig12_feature_correlation.png   — Feature correlation heatmap')
    print('   fig13_speed_cri_scatter.png     — Speed vs CRI scatter')
    print('   fig14_component_correlation.png — Risk component correlation')


def fig_pr_curve(df):
    """Fig 9: Precision-Recall curve."""
    from sklearn.metrics import precision_recall_curve, average_precision_score
    y_true = compute_ground_truth(df)
    cri_max = df[['cri_left', 'cri_right']].max(axis=1)
    precision, recall, _ = precision_recall_curve(y_true, cri_max)
    auprc = average_precision_score(y_true, cri_max)
    pos_rate = y_true.mean()

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(recall, precision, 'b-', lw=2, label=f'Physics CRI (AUPRC={auprc:.3f})')
    ax.axhline(y=pos_rate, color='gray', linestyle='--', lw=1, label=f'Random baseline ({pos_rate:.3f})')
    ax.set_xlabel('Recall', fontsize=13)
    ax.set_ylabel('Precision', fontsize=13)
    ax.set_title('Precision-Recall Curve', fontsize=14)
    ax.legend(fontsize=11)
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1])
    fig.tight_layout()
    fig.savefig(FIG_DIR / 'fig9_pr_curve.png', dpi=300, bbox_inches='tight')
    plt.close(fig)
    print('   fig9_pr_curve.png generated')


def fig_cri_timeseries(df):
    """Fig 10: CRI time-series for a single vehicle with alert events."""
    # Find a vehicle with WARNING or CRITICAL alerts
    candidates = df[df['alert_left'].isin(['WARNING', 'CRITICAL']) |
                    df['alert_right'].isin(['WARNING', 'CRITICAL'])]
    if len(candidates) == 0:
        candidates = df[df['alert_left'].isin(['CAUTION', 'WARNING']) |
                        df['alert_right'].isin(['CAUTION', 'WARNING'])]
    if len(candidates) == 0:
        print('   fig10: no interesting vehicle found, skipping')
        return

    vid = candidates['ego_vid'].value_counts().idxmax()
    vdf = df[df['ego_vid'] == vid].sort_values('step')
    cri_max = vdf[['cri_left', 'cri_right']].max(axis=1)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.axhspan(0, 0.30, alpha=0.1, color='green')
    ax.axhspan(0.30, 0.60, alpha=0.1, color='gold')
    ax.axhspan(0.60, 0.80, alpha=0.1, color='orange')
    ax.axhspan(0.80, 1.0, alpha=0.1, color='red')
    ax.plot(vdf['step'], cri_max, 'b-', lw=1.2)
    for thr, lbl in [(0.30, 'CAUTION'), (0.60, 'WARNING'), (0.80, 'CRITICAL')]:
        ax.axhline(y=thr, color='gray', linestyle=':', lw=0.8, alpha=0.7)
    ax.set_xlabel('Simulation Step', fontsize=13)
    ax.set_ylabel('CRI', fontsize=13)
    ax.set_title(f'CRI Time-Series for Vehicle {vid}', fontsize=14)
    ax.set_ylim([0, min(1.0, cri_max.max() * 1.2 + 0.05)])
    fig.tight_layout()
    fig.savefig(FIG_DIR / 'fig10_cri_timeseries.png', dpi=300, bbox_inches='tight')
    plt.close(fig)
    print('   fig10_cri_timeseries.png generated')


def fig_calibration(df):
    """Fig 11: Calibration plot (reliability diagram)."""
    from sklearn.calibration import calibration_curve
    y_true = compute_ground_truth(df)
    cri_max = df[['cri_left', 'cri_right']].max(axis=1)
    prob_true, prob_pred = calibration_curve(y_true, cri_max, n_bins=10, strategy='uniform')

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], 'k--', lw=1, label='Perfect calibration')
    ax.plot(prob_pred, prob_true, 'bo-', lw=2, markersize=6, label='Physics CRI')
    ax.set_xlabel('Mean Predicted CRI', fontsize=13)
    ax.set_ylabel('Fraction of Positives', fontsize=13)
    ax.set_title('Calibration Plot', fontsize=14)
    ax.legend(fontsize=11)
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1])
    fig.tight_layout()
    fig.savefig(FIG_DIR / 'fig11_calibration.png', dpi=300, bbox_inches='tight')
    plt.close(fig)
    print('   fig11_calibration.png generated')


def fig_feature_correlation(df):
    """Fig 12: Feature correlation heatmap."""
    feat_cols = ['speed', 'accel', 'decel', 'num_targets', 'max_gap', 'rel_speed',
                 'max_plr', 'k_lost_max']
    available = [c for c in feat_cols if c in df.columns]
    dff = df[available].copy()
    dff['speed_kmh'] = dff['speed'] * 3.6
    dff['abs_accel'] = (dff['accel'] - dff['decel']).abs()
    dff['is_braking'] = (dff['decel'] > 1.0).astype(int)
    dff['brake_ratio'] = dff['decel'] / dff['speed'].clip(lower=0.1)
    dff['has_targets'] = (dff['num_targets'] > 0).astype(int)
    dff['closing_speed'] = dff['rel_speed']

    corr = dff.corr()
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(corr, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
    ax.set_xticks(range(len(corr.columns)))
    ax.set_yticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha='right', fontsize=9)
    ax.set_yticklabels(corr.columns, fontsize=9)
    for i in range(len(corr)):
        for j in range(len(corr)):
            val = corr.iloc[i, j]
            color = 'white' if abs(val) > 0.6 else 'black'
            ax.text(j, i, f'{val:.2f}', ha='center', va='center', fontsize=7, color=color)
    fig.colorbar(im, ax=ax, shrink=0.8)
    ax.set_title('Feature Correlation Matrix', fontsize=14)
    fig.tight_layout()
    fig.savefig(FIG_DIR / 'fig12_feature_correlation.png', dpi=300, bbox_inches='tight')
    plt.close(fig)
    print('   fig12_feature_correlation.png generated')


def fig_speed_cri_scatter(df):
    """Fig 13: Speed vs CRI scatter by scenario."""
    sample = df.sample(n=min(5000, len(df)), random_state=42)
    cri_max = sample[['cri_left', 'cri_right']].max(axis=1)
    colors = {'normal': '#4285F4', 'HNR': '#EA4335', 'TSV': '#34A853'}

    fig, ax = plt.subplots(figsize=(8, 5))
    for scenario, color in colors.items():
        mask = sample['scenario_type'] == scenario
        ax.scatter(sample.loc[mask, 'speed'], cri_max[mask],
                   c=color, alpha=0.3, s=8, label=scenario)
    ax.set_xlabel('Ego Speed (m/s)', fontsize=13)
    ax.set_ylabel('max(CRI_left, CRI_right)', fontsize=13)
    ax.set_title('Speed vs CRI by Scenario', fontsize=14)
    ax.legend(fontsize=11, markerscale=3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / 'fig13_speed_cri_scatter.png', dpi=300, bbox_inches='tight')
    plt.close(fig)
    print('   fig13_speed_cri_scatter.png generated')


def fig_component_correlation(df):
    """Fig 14: CRI risk component correlation matrix."""
    comp_df = pd.DataFrame()
    for comp in ['R_decel', 'R_ttc', 'R_intent']:
        left = f'{comp}_left'
        right = f'{comp}_right'
        if left in df.columns and right in df.columns:
            comp_df[comp] = df[[left, right]].max(axis=1)

    if len(comp_df.columns) < 2:
        print('   fig14: insufficient component columns, skipping')
        return

    # Filter to rows with any risk > 0
    has_risk = (comp_df > 0).any(axis=1)
    comp_df = comp_df[has_risk]

    corr = comp_df.corr()
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(corr, cmap='RdBu_r', vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr.columns)))
    ax.set_yticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, fontsize=11)
    ax.set_yticklabels(corr.columns, fontsize=11)
    for i in range(len(corr)):
        for j in range(len(corr)):
            val = corr.iloc[i, j]
            color = 'white' if abs(val) > 0.6 else 'black'
            ax.text(j, i, f'{val:.3f}', ha='center', va='center', fontsize=12, color=color)
    fig.colorbar(im, ax=ax, shrink=0.8)
    ax.set_title('Risk Component Correlation', fontsize=14)
    fig.tight_layout()
    fig.savefig(FIG_DIR / 'fig14_component_correlation.png', dpi=300, bbox_inches='tight')
    plt.close(fig)
    print('   fig14_component_correlation.png generated')


if __name__ == '__main__':
    main()

