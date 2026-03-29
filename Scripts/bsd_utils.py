"""
bsd_utils.py — Shared evaluation utility for V2V BSD evaluation pipeline.

Centralizes the kinematic near-miss proxy so that evaluate_system.py,
sensitivity_analysis.py, ablation_study.py, and optimize_weights.py
all use identical logic. Change the thresholds here — they update everywhere.

V3.0 Update: Added blind-spot zone filter (in_zone), minimum speed guard,
TTC division-by-zero guard, and positive rate sanity check (max 15%).

IMPORTANT — EVALUATION METHODOLOGY NOTE:
    This function computes a kinematic near-miss PROXY label, NOT an
    independent ground truth. The proxy uses gap and TTC thresholds
    derived from the same BSM telemetry that the CRI model consumes.
    Results must be interpreted as proxy-based evaluation. Where SUMO-
    reported physical collisions are available (ground_truth_collision == 1),
    those are treated as authoritative positive labels independent of
    the proxy.
"""
import numpy as np
import pandas as pd

# Single source of truth for near-miss thresholds (V3.0 recalibrated)
GT_GAP_CRITICAL = 1.0   # m  — longitudinal gap below which event is positive
GT_TTC_CRITICAL = 2.0   # s  — kinematic TTC proxy below which event is positive
GT_MIN_REL_SPEED = 0.5  # m/s — guard against division instability in TTC proxy
GT_MIN_EGO_SPEED = 2.0  # m/s — ignore stationary/near-stopped ego vehicles
GT_MAX_POSITIVE_RATE = 0.15  # 15% — sanity cap; above this, thresholds are too loose


def compute_ground_truth(df: pd.DataFrame,
                         gap_thresh: float = GT_GAP_CRITICAL,
                         ttc_thresh: float = GT_TTC_CRITICAL) -> np.ndarray:
    """
    Compute evaluation labels using a two-tier approach:

    Tier 1 (authoritative): SUMO-reported physical collisions
        (ground_truth_collision == 1). These are independent of the model.

    Tier 2 (proxy): Kinematic near-miss proxy — gap < gap_thresh OR
        TTC < ttc_thresh, with target in blind spot zone AND ego speed > 2 m/s.

    Uses only raw BSM fields and in_zone flag. Never reads R_ttc, R_decel,
    or any model intermediate — ensuring evaluations are methodologically
    independent from the CRI computation.

    NOTE: The proxy shares structural similarity with CRI inputs (position,
    speed, gap). AUC values evaluated against this proxy should be
    interpreted with this caveat. See paper/main.tex Section IX for discussion.
    """
    # Tier 1: SUMO collision flag (true ground truth, model-independent)
    if 'ground_truth_collision' in df.columns:
        y = df['ground_truth_collision'].values.copy().astype(int)
    else:
        y = np.zeros(len(df), dtype=int)

    n_sumo_collisions = int(y.sum())

    # Speed filter: ignore near-stationary ego vehicles
    ego_moving = df['speed'] > GT_MIN_EGO_SPEED if 'speed' in df.columns else True

    # Blind-spot zone filter: only count targets actually in the blind spot
    if 'in_zone_left' in df.columns and 'in_zone_right' in df.columns:
        in_zone = (df['in_zone_left'].fillna(0).astype(int) | 
                   df['in_zone_right'].fillna(0).astype(int)).astype(bool)
    elif 'P_left' in df.columns and 'P_right' in df.columns:
        # Fallback: use probability > 0.1 as zone proxy
        in_zone = (df['P_left'].fillna(0) + df['P_right'].fillna(0)) > 0.1
    else:
        in_zone = True  # No zone data available — skip filter

    # TTC proxy with division guard
    rel_speed_safe = df['rel_speed'].clip(lower=GT_MIN_REL_SPEED)
    ttc_proxy = df['max_gap'] / rel_speed_safe
    # When relative speed is too low, TTC is effectively infinite
    ttc_proxy = ttc_proxy.where(df['rel_speed'] > GT_MIN_REL_SPEED, other=999.0)

    has_target = df['num_targets'] > 0

    # Tier 2 proxy: gap close OR TTC short, filtered by zone and speed
    proxy_mask = (
        has_target & ego_moving & in_zone &
        ((df['max_gap'] < gap_thresh) | (ttc_proxy < ttc_thresh))
    ).values

    y = np.maximum(y, proxy_mask.astype(int))

    # Store collision breakdown for reporting
    compute_ground_truth._last_sumo_collisions = n_sumo_collisions
    compute_ground_truth._last_proxy_positives = int(proxy_mask.sum())
    compute_ground_truth._last_total_positives = int(y.sum())

    return y

# Initialize static attributes
compute_ground_truth._last_sumo_collisions = 0
compute_ground_truth._last_proxy_positives = 0
compute_ground_truth._last_total_positives = 0


def check_coverage(y_true: np.ndarray, tag: str = '') -> None:
    """Warn if evaluation labels have no positive events or unrealistic positive rate."""
    n, p = len(y_true), int(y_true.sum())
    rate = p / n if n > 0 else 0
    label = f'[{tag}] ' if tag else ''

    # Report breakdown between SUMO collisions and proxy events
    n_sumo = getattr(compute_ground_truth, '_last_sumo_collisions', 0)
    n_proxy = getattr(compute_ground_truth, '_last_proxy_positives', 0)

    if p == 0:
        print(f'{label}⚠️  WARNING: 0 positive events in evaluation labels — '
              f'run a longer simulation before using these metrics.')
    elif rate > GT_MAX_POSITIVE_RATE:
        print(f'{label}⚠️  WARNING: Positive rate {rate:.1%} '
              f'exceeds {GT_MAX_POSITIVE_RATE:.0%} sanity cap! '
              f'Thresholds may be too loose. ({p}/{n})')
    else:
        print(f'{label}Evaluation labels: {p}/{n} positive ({rate:.2%})')
        if n_sumo > 0:
            print(f'{label}  ├─ SUMO collisions (authoritative): {n_sumo}')
        print(f'{label}  └─ Kinematic proxy events: {n_proxy}')
