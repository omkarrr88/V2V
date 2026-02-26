"""
bsd_utils.py — Shared ground truth utility for V2V BSD evaluation pipeline.

Centralizes the kinematic near-miss proxy so that evaluate_system.py,
sensitivity_analysis.py, ablation_study.py, and optimize_weights.py
all use identical logic. Change the thresholds here — they update everywhere.
"""
import numpy as np
import pandas as pd

# Single source of truth for near-miss thresholds
GT_GAP_CRITICAL = 2.0   # m  — longitudinal gap below which event is positive
GT_TTC_CRITICAL = 1.5   # s  — TTC proxy below which event is positive


def compute_ground_truth(df: pd.DataFrame,
                         gap_thresh: float = GT_GAP_CRITICAL,
                         ttc_thresh: float = GT_TTC_CRITICAL) -> np.ndarray:
    """
    Binary ground truth using pure kinematic near-miss proxy.

    Priority 1: actual SUMO collision flag (ground_truth_collision == 1)
    Priority 2: kinematic proxy — gap < gap_thresh OR ttc_proxy < ttc_thresh

    Uses only raw BSM fields. Never reads R_ttc, R_decel, P_left, or any
    model intermediate — ensuring evaluations are methodologically independent.
    """
    if 'ground_truth_collision' in df.columns:
        y = df['ground_truth_collision'].values.copy().astype(int)
    else:
        y = np.zeros(len(df), dtype=int)

    rel_speed = df['rel_speed'].clip(lower=0.001)
    ttc_proxy = (df['max_gap'] / rel_speed).where(df['rel_speed'] > 0, other=999.0)
    has_target = df['num_targets'] > 0
    proxy_mask = (has_target & ((df['max_gap'] < gap_thresh) | (ttc_proxy < ttc_thresh))).values
    
    y = np.maximum(y, proxy_mask.astype(int))
    return y


def check_coverage(y_true: np.ndarray, tag: str = '') -> None:
    """Warn if ground truth has no positive events (degenerate dataset)."""
    n, p = len(y_true), int(y_true.sum())
    label = f'[{tag}] ' if tag else ''
    if p == 0:
        print(f'{label}⚠️  WARNING: 0 positive events in ground truth — '
              f'run a longer simulation before using these metrics.')
    else:
        print(f'{label}Ground truth: {p}/{n} positive ({p/n:.2%})')
