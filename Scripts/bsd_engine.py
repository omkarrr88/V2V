"""
V2V Blind Spot Detection Engine — V3.0 Mathematical Model Implementation
=========================================================================
Direct implementation of the Comprehensive Mathematical Model for V2V BSD.
Every formula, parameter, and edge case from the V3.0 spec is implemented here.

Author: V2V BSD Research Project
"""

import numpy as np
from scipy.stats import norm
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from enum import Enum


# ============================================================
# SECTION 8: Complete Parameter Reference (from V3.0 model)
# ============================================================

class Params:
    """All model parameters from Section 8 of V3.0 spec."""
    # BSM & Communication
    F_BSM       = 10        # Hz — BSM broadcast frequency (SAE J2735 §1)
    DT          = 0.1       # s  — timestep (1/F_BSM)
    R_COMM      = 300.0     # m  — V2V communication range
    TAU_BASE    = 0.005     # s  — base DSRC latency (0.015 for C-V2X)
    N_PLR       = 10        # packets — PLR sliding window size

    # Blind Spot Zone Geometry
    L_BASE      = 4.5       # m  — minimum blind spot length
    V_MIN       = 2.0       # m/s — speed below which L_bs = L_base
    V_MAX       = 40.0      # m/s — speed above which L_bs = L_base + lambda
    LAMBDA_SCALE = 12.0     # m  — additional length at max speed
    W_LANE      = 3.5       # m  — lane width (configurable)

    # Curvature Correction Guards
    EPS_YAW     = 1e-3      # rad/s — straight-line yaw rate threshold
    EPS_V       = 0.1       # m/s — minimum velocity for curvature

    # GPS Uncertainty
    SIGMA_GPS   = 1.5       # m  — default GPS uncertainty (1σ)

    # Physics — Deceleration Risk
    T_REACT     = 1.2       # s  — human reaction time (P85 AASHTO)
    K_BRAKE     = 1.50      # —  — decay constant: ln(20)/2
    G           = 9.81      # m/s² — gravitational acceleration
    RHO_AIR     = 1.225     # kg/m³ — air density at sea level

    # TTC
    EPS_A       = 1e-3      # m/s² — near-zero acceleration threshold (§5.2)
    TTC_CRIT    = 4.0       # s  — imminent collision threshold
    TTC_MAX     = 8.0       # s  — maximum TTC horizon

    # Intent
    W_SIG       = 0.4       # — turn signal weight
    W_LAT       = 0.6       # — lateral drift weight
    V_LAT_MAX   = 1.0       # m/s — max lane-change lateral speed

    # CRI Weights (α + β + γ = 1.0)
    ALPHA       = 0.15      # — R_decel weight (tuned via optimize_weights.py)
    BETA        = 0.80      # — R_ttc weight
    GAMMA       = 0.05      # — R_intent weight
    EPSILON     = 0.30      # — PLR penalty coefficient

    # Alert Thresholds
    THETA_1     = 0.30      # — CAUTION threshold
    THETA_2     = 0.60      # — WARNING threshold
    THETA_3     = 0.80      # — CRITICAL threshold
    DELTA_H     = 0.05      # — hysteresis band width
    N_H         = 3         # — consecutive timesteps for upgrade

    # Vehicle Defaults
    M_DEFAULT   = 1800.0    # kg — default target mass (BSM Part II absent)
    MU_DEFAULT  = 0.7       # — default dry asphalt friction

    # Typical Vehicle Aerodynamics
    AERO = {
        'sedan': {'Cd': 0.30, 'Af': 2.2, 'M': 1500},
        'suv':   {'Cd': 0.35, 'Af': 3.0, 'M': 2200},
        'truck': {'Cd': 0.60, 'Af': 8.0, 'M': 15000},
    }


class AlertLevel(Enum):
    SAFE     = 0
    CAUTION  = 1
    WARNING  = 2
    CRITICAL = 3


@dataclass
class VehicleState:
    """State vector S_i for a vehicle (Section 1)."""
    vid: str
    x: float            # GPS X position (m)
    y: float            # GPS Y position (m)
    speed: float        # velocity magnitude (m/s)
    accel: float        # longitudinal acceleration (m/s²)
    heading: float      # heading angle θ in radians (math convention: CCW from +X)
    yaw_rate: float     # dθ/dt (rad/s)
    length: float       # vehicle length (m)
    width: float        # vehicle width (m)
    mass: float         # vehicle mass (kg)
    mu: float           # road friction coefficient
    signals: int        # turn signal bitfield (bit 0 = right, bit 1 = left)
    vehicle_type: str   # 'sedan', 'suv', 'truck'
    timestamp: int      # simulation step when BSM was generated


@dataclass
class TargetTracker:
    """Per-target state maintained by the ego vehicle."""
    vid: str
    last_state: Optional[VehicleState] = None
    k_lost: int = 0                     # consecutive dropped packets
    plr_window: list = field(default_factory=lambda: [1]*Params.N_PLR)  # reception flags
    prev_heading: Optional[float] = None


@dataclass
class SideState:
    """Per-side hysteresis and alert state."""
    current_level: AlertLevel = AlertLevel.SAFE
    upgrade_counter: int = 0
    pending_level: Optional[AlertLevel] = None


class BSDEngine:
    """
    V2V Blind Spot Detection Engine — V3.0 Mathematical Model.
    
    Implements every section of the mathematical model:
    - §2: Coordinate transformation (rotation matrix)
    - §3: Dynamic blind spot zone with curvature correction
    - §3.4: Side-specific CRI with empty-set default
    - §4.1: GPS probability with |P_lat| fix
    - §4.2: Dead reckoning (CA-CYR)
    - §4.3: PLR formal definition
    - §5.1: R_decel with friction + aero drag
    - §5.2: R_ttc second-order with all edge cases
    - §5.2.1: Lateral Time-To-Collision (TTC_lat)
     §5.3: R_intent direction-aware with Ego-only intent.
    - §6: CRI composition with PLR penalty
    - §7: Alert levels with per-side hysteresis
    """

    def __init__(self, alpha=None, beta=None, gamma=None, use_lateral_ttc=True, sigma_gps=None, ttc_crit=None, theta_3=None):
        self.target_trackers: Dict[str, TargetTracker] = {}
        self.left_state = SideState()
        self.right_state = SideState()
        # Logging for dashboard
        self.last_computation = {}
        
        # Overrides for Ablation & Sensitivity Analysis
        self.alpha = alpha if alpha is not None else Params.ALPHA
        self.beta = beta if beta is not None else Params.BETA
        self.gamma = gamma if gamma is not None else Params.GAMMA
        self.use_lateral_ttc = use_lateral_ttc
        self.sigma_gps = sigma_gps if sigma_gps is not None else Params.SIGMA_GPS
        self.ttc_crit = ttc_crit if ttc_crit is not None else Params.TTC_CRIT
        self.theta_3 = theta_3 if theta_3 is not None else Params.THETA_3

    # ============================================================
    # §2: COORDINATE TRANSFORMATION
    # ============================================================
    def _to_ego_frame(self, ego: VehicleState, target_x: float, target_y: float) -> Tuple[float, float]:
        """
        Transform global (x, y) to ego-centric frame using rotation matrix R(θ_e).
        R(θ) = [[sin θ, -cos θ], [cos θ, sin θ]]
        Positive X = RIGHT, Positive Y = FORWARD
        """
        dx = target_x - ego.x
        dy = target_y - ego.y
        theta = ego.heading
        x_rel = np.sin(theta) * dx - np.cos(theta) * dy
        y_rel = np.cos(theta) * dx + np.sin(theta) * dy
        return x_rel, y_rel

    # ============================================================
    # §3.1: DYNAMIC BLIND SPOT LENGTH
    # ============================================================
    def _compute_L_bs(self, v_e: float) -> float:
        """
        L_bs(v_e) = L_base + λ_scale · clamp((v_e - v_min)/(v_max - v_min), 0, 1)
        """
        t = np.clip((v_e - Params.V_MIN) / (Params.V_MAX - Params.V_MIN), 0.0, 1.0)
        return Params.L_BASE + Params.LAMBDA_SCALE * t

    # ============================================================
    # §3.2: CURVATURE CORRECTION (Clothoid)
    # ============================================================
    def _curvature_correction(self, ego: VehicleState, x_rel: float, y_rel: float) -> float:
        """
        Corrects x_rel for road curvature when ego is turning.
        x_corrected = x_rel - (y_rel² · θ̇_e) / (2 · v_e)
        Returns x_corrected. Only applied if |θ̇_e| > ε_yaw and v_e > ε_v.
        """
        if abs(ego.yaw_rate) > Params.EPS_YAW and ego.speed > Params.EPS_V:
            correction = (y_rel ** 2 * ego.yaw_rate) / (2.0 * ego.speed)
            return x_rel - correction
        return x_rel

    # ============================================================
    # §3.3: BLIND SPOT ZONE BOOLEAN (for visualization only)
    # ============================================================
    def _in_blind_spot_zone(self, ego: VehicleState, x_corrected: float, y_rel: float) -> bool:
        """
        D_bs: lateral and longitudinal boundary check.
        Lateral: W_e/2 ≤ |x_corrected| ≤ W_e/2 + W_lane
        Longitudinal: -L_bs ≤ y_rel ≤ L_e/2
        """
        half_w = ego.width / 2.0
        L_bs = self._compute_L_bs(ego.speed)
        lat_ok = half_w <= abs(x_corrected) <= half_w + Params.W_LANE
        lon_ok = -L_bs <= y_rel <= ego.length / 2.0
        return lat_ok and lon_ok

    # ============================================================
    # §3.4: SIDE IDENTIFICATION
    # ============================================================
    def _get_side(self, x_corrected: float) -> str:
        """side(V_t) based on sgn(x_corrected)."""
        return "RIGHT" if x_corrected >= 0 else "LEFT"

    # ============================================================
    # §4.1: GPS PROBABILITY (with |P_lat| fix for left-side targets)
    # ============================================================
    def _compute_probability(self, ego: VehicleState, x_hat: float, y_hat: float) -> float:
        """
        P(V_t ∈ Z_bs) ≈ |P_lat| × P_lon
        
        P_lat = |Φ((x_outer - x̂)/σ) - Φ((x_inner - x̂)/σ)|
        P_lon = Φ((y_front - ŷ)/σ) - Φ((y_rear - ŷ)/σ)
        
        x_outer = sgn(x̂) · (W_e/2 + W_lane)
        x_inner = sgn(x̂) · (W_e/2)
        """
        sigma = self.sigma_gps
        half_w = ego.width / 2.0
        L_bs = self._compute_L_bs(ego.speed)
        
        if x_hat >= 0:
            x_inner = half_w
            x_outer = half_w + Params.W_LANE
        else:
            x_inner = -(half_w + Params.W_LANE)
            x_outer = -half_w
        
        y_front = ego.length / 2.0
        y_rear = -L_bs

        lower = min(x_inner, x_outer)
        upper = max(x_inner, x_outer)
        
        P_lat = norm.cdf(upper, loc=x_hat, scale=sigma) - norm.cdf(lower, loc=x_hat, scale=sigma)
        
        # Guard against forward-lane targets throwing side alerts (zero-lateral offset)
        if abs(x_hat) < half_w:
            P_lat *= (abs(x_hat) / half_w) ** 2
        
        P_lon = (
            norm.cdf((y_front - y_hat) / sigma) -
            norm.cdf((y_rear - y_hat) / sigma)
        )
        
        return np.clip(P_lat * P_lon, 0.0, 1.0)

    # ============================================================
    # §4.2: DEAD RECKONING (CA-CYR model)
    # ============================================================
    def _dead_reckon_rel(self, ego: VehicleState, target: VehicleState, tau_eff: float) -> Tuple[float, float, bool]:
        """
        Predict target relative position after delay τ_eff using the Constant Acceleration
        kinematic model in the GLOBAL frame, then converting to EGO frame.
        """
        # Hard stale cap
        if tau_eff > 0.5:
            return 0.0, 0.0, True

        # Extrapolate target position in GLOBAL frame
        x_t_pred = target.x + target.speed * np.cos(target.heading) * tau_eff + 0.5 * target.accel * np.cos(target.heading) * (tau_eff ** 2)
        y_t_pred = target.y + target.speed * np.sin(target.heading) * tau_eff + 0.5 * target.accel * np.sin(target.heading) * (tau_eff ** 2)

        # Transform to EGO frame
        x_pred_rel, y_pred_rel = self._to_ego_frame(ego, x_t_pred, y_t_pred)

        return x_pred_rel, y_pred_rel, False

    def _compute_tau_eff(self, tracker: TargetTracker) -> float:
        """τ_eff = τ_base + k_lost · Δt"""
        return Params.TAU_BASE + tracker.k_lost * Params.DT

    def _is_stale(self, tracker: TargetTracker) -> bool:
        """Target is stale if τ_eff > 0.5s (k_lost > 4)."""
        return tracker.k_lost > 4

    # ============================================================
    # §4.3: PACKET LOSS RATIO
    # ============================================================
    def _compute_plr(self, tracker: TargetTracker) -> float:
        """
        PLR = (missed in last N_plr) / N_plr
        plr_window: list of 0/1 (0 = missed, 1 = received)
        """
        missed = sum(1 for flag in tracker.plr_window if flag == 0)
        return missed / Params.N_PLR

    def _update_tracker(self, tracker: TargetTracker, received: bool, state: Optional[VehicleState] = None):
        """Update k_lost counter and PLR window for a target."""
        # PLR window (sliding)
        tracker.plr_window.pop(0)
        tracker.plr_window.append(1 if received else 0)

        # k_lost counter
        if received:
            tracker.k_lost = 0
            if state is not None:
                tracker.prev_heading = tracker.last_state.heading if tracker.last_state else state.heading
                tracker.last_state = state
        else:
            tracker.k_lost += 1

    # ============================================================
    # §5.1: DECELERATION RISK (R_decel)
    # ============================================================
    def _compute_R_decel(self, ego: VehicleState, target: VehicleState,
                         y_hat: float) -> float:
        """
        R_decel based on friction-limited stopping distance vs bumper-to-bumper gap.
        
        D_stop_req = v_t · T_react + v_t² / (2 · a_max_t)
        a_max_t = μ·g + F_drag/(M_t)
        d_gap = |ŷ_rel| - (L_e + L_t)/2
        R_decel = min(1, exp(-k_brake · (d_gap - D_stop) / D_stop))  if d_gap > 0
                = 1.0  if d_gap ≤ 0
        """
        # a_max with aerodynamic drag assistance
        aero = Params.AERO.get(target.vehicle_type, Params.AERO['sedan'])
        v_t = target.speed
        mu = target.mu if target.mu > 0 else Params.MU_DEFAULT
        
        F_drag = 0.5 * Params.RHO_AIR * aero['Cd'] * aero['Af'] * v_t ** 2
        M_t = target.mass if target.mass > 0 else Params.M_DEFAULT
        a_max_t = mu * Params.G + F_drag / M_t

        # Stopping distance
        D_stop_req = v_t * Params.T_REACT + (v_t ** 2) / (2.0 * a_max_t) if a_max_t > 0 else float('inf')

        # Longitudinal bumper-to-bumper gap
        d_gap = abs(y_hat) - (ego.length + target.length) / 2.0

        if d_gap <= 0:
            return 1.0
        if D_stop_req <= 0:
            return 0.0
        if not np.isfinite(D_stop_req):
            # a_max = 0 → vehicle cannot brake at all → maximum risk
            return 1.0

        ratio = (d_gap - D_stop_req) / D_stop_req
        return float(np.clip(np.exp(-Params.K_BRAKE * ratio), 0.0, 1.0))

    # ============================================================
    # §5.2: TIME-TO-COLLISION (R_ttc) — Second Order
    # ============================================================
    def _compute_R_ttc(self, ego: VehicleState, target: VehicleState,
                       y_hat: float) -> Tuple[float, float, float]:
        """
        Second-order TTC with all edge cases from Section 5.2.
        
        v_rel = v_e - v_t·cos(θ_t - θ_e)  (positive = closing)
        a_rel = a_e - a_t·cos(θ_t - θ_e)
        d_gap = |ŷ_rel| - (L_e + L_t)/2
        """
        heading_diff = target.heading - ego.heading
        v_tgt_proj = target.speed * np.cos(heading_diff)
        a_tgt_proj = target.accel * np.cos(heading_diff)
        
        # Positive = closing speed
        if y_hat >= 0:
            v_rel = ego.speed - v_tgt_proj
            a_rel = ego.accel - a_tgt_proj
        else:
            v_rel = v_tgt_proj - ego.speed
            a_rel = a_tgt_proj - ego.accel

        d_gap = abs(y_hat) - (ego.length + target.length) / 2.0

        ttc = float('inf')

        if d_gap <= 0:
            ttc = 0.0
        # Case 1: vehicles separating
        elif v_rel <= 0 and a_rel >= 0:
            return 0.0, 0.0, 0.0  # TTC = ∞ → R_ttc = 0

        # Case 2: near-zero acceleration (linear)
        elif abs(a_rel) < 1e-5:
            if v_rel > 0:
                ttc = d_gap / v_rel
        else:
            # Case 3: quadratic — d_gap = v_rel·t + 0.5·a_rel·t²
            discriminant = v_rel ** 2 + 2.0 * a_rel * d_gap
            if discriminant < 0:
                return 0.0, 0.0, 0.0  # trajectories diverge → R_ttc = 0

            sqrt_disc = np.sqrt(discriminant)
            t1 = (-v_rel + sqrt_disc) / a_rel
            t2 = (-v_rel - sqrt_disc) / a_rel

            # Take smallest positive root
            candidates = [t for t in [t1, t2] if t > 0]
            if candidates:
                ttc = min(candidates)
            else:
                return 0.0, 0.0, 0.0  # both negative → collision in past

        # TTC to risk score (Section 5.2 table)
        # R_ttc = 1.0                           if TTC ≤ TTC_crit
        #       = (TTC_crit / TTC)²             if TTC_crit < TTC ≤ TTC_max
        #       = 0.0                           otherwise
        if ttc > Params.TTC_MAX:
            R_ttc_longitudinal = 0.0
        elif ttc <= self.ttc_crit:
            R_ttc_longitudinal = 1.0
        else:
            R_ttc_longitudinal = (self.ttc_crit / ttc) ** 2

        # Lateral TTC
        v_lat_rel = target.speed * np.sin(target.heading - ego.heading)
        W_gap = Params.W_LANE - ego.width / 2.0 - target.width / 2.0
        
        if W_gap <= 0:
            R_ttc_lateral = 1.0
        elif not self.use_lateral_ttc or abs(v_lat_rel) < Params.EPS_V:
            R_ttc_lateral = 0.0
        else:
            ttc_lat = W_gap / abs(v_lat_rel)
            ttc_lat = np.clip(ttc_lat, 0.0, Params.TTC_MAX)
            if ttc_lat <= self.ttc_crit:
                R_ttc_lateral = 1.0 - ttc_lat / self.ttc_crit
            else:
                R_ttc_lateral = 0.0

        return max(R_ttc_longitudinal, R_ttc_lateral), R_ttc_longitudinal, R_ttc_lateral

    # ============================================================
    # §5.3: LATERAL INTENT (R_intent) — Direction-Aware
    # ============================================================
    def _compute_R_intent(self, ego: VehicleState, target: VehicleState, side: str) -> float:
        """
        R_intent captures only the Ego vehicle's lane-change intent (turn signal, lateral drift).
        """
        # Ego Intent
        right_blinker = bool(ego.signals & 0x01)
        left_blinker = bool(ego.signals & 0x02)
        I_turn = 1.0 if (side == "RIGHT" and right_blinker) or (side == "LEFT" and left_blinker) else 0.0

        v_lat_e = ego.speed * np.sin(ego.yaw_rate * Params.DT)
        v_lat_toward = max(0.0, v_lat_e) if side == "LEFT" else max(0.0, -v_lat_e)
        lat_ratio = min(1.0, v_lat_toward / Params.V_LAT_MAX) if Params.V_LAT_MAX > 0 else 0.0
        
        return Params.W_SIG * I_turn + Params.W_LAT * lat_ratio

    # ============================================================
    # §6: CRI COMPOSITION
    # ============================================================
    def _compute_cri_for_target(self, ego: VehicleState, target: VehicleState,
                                tracker: TargetTracker) -> dict:
        """
        Compute CRI_final(V_t) for a single target vehicle.
        
        CRI = P(V_t ∈ Z_bs) × (α·R_decel + β·R_ttc + γ·R_intent) × (1 + ε·PLR)
        Clamped to [0, 1].
        
        Returns dict with all intermediate values for dashboard logging.
        """
        # Dead reckoning directly in ego frame (Section 4.2)
        tau_eff = self._compute_tau_eff(tracker)
        stale = self._is_stale(tracker)
        x_rel, y_rel, is_hard_stale = self._dead_reckon_rel(ego, target, tau_eff)
        
        if is_hard_stale:
            return {
                'target_vid': target.vid,
                'side': 'UNKNOWN',
                'cri': 0.0,
                'P': 0.0,
                'R_decel': 0.0,
                'R_ttc': 0.0,
                'R_intent': 0.0,
                'R_weighted': 0.0,
                'plr': self._compute_plr(tracker),
                'plr_multiplier': 1.0,
                'tau_eff': tau_eff,
                'stale': True,
                'in_zone': False,
                'x_rel': x_rel,
                'y_rel': y_rel,
                'd_gap': 0.0,
            }

        # Curvature correction
        x_corrected = self._curvature_correction(ego, x_rel, y_rel)

        # Side identification
        side = self._get_side(x_corrected)

        # GPS probability
        P = self._compute_probability(ego, x_corrected, y_rel)

        # Boolean zone check (for visualization)
        in_zone = self._in_blind_spot_zone(ego, x_corrected, y_rel)

        # Risk components
        R_decel = self._compute_R_decel(ego, target, y_rel)
        R_ttc, R_ttc_lon, R_ttc_lat = self._compute_R_ttc(ego, target, y_rel)
        R_intent = self._compute_R_intent(ego, target, side)

        # Weighted risk
        R_weighted = self.alpha * R_decel + self.beta * R_ttc + self.gamma * R_intent

        # PLR penalty
        plr = self._compute_plr(tracker)
        plr_multiplier = 1.0 + Params.EPSILON * plr

        # Final CRI (clamped to [0, 1])
        cri = np.clip(P * R_weighted * plr_multiplier, 0.0, 1.0)

        return {
            'target_vid': target.vid,
            'side': side,
            'cri': cri,
            'P': P,
            'R_decel': R_decel,
            'R_ttc': R_ttc,
            'R_ttc_lon': R_ttc_lon,
            'R_ttc_lat': R_ttc_lat,
            'R_intent': R_intent,
            'R_weighted': R_weighted,
            'plr': plr,
            'plr_multiplier': plr_multiplier,
            'tau_eff': tau_eff,
            'stale': stale,
            'in_zone': in_zone,
            'x_rel': x_corrected,
            'y_rel': y_rel,
            'd_gap': abs(y_rel) - (ego.length + target.length) / 2.0,
        }

    # ============================================================
    # §7: ALERT LEVELS WITH PER-SIDE HYSTERESIS
    # ============================================================
    def _cri_to_level(self, cri: float) -> AlertLevel:
        """Raw CRI to alert level (no hysteresis)."""
        if cri >= self.theta_3:
            return AlertLevel.CRITICAL
        elif cri >= Params.THETA_2:
            return AlertLevel.WARNING
        elif cri >= Params.THETA_1:
            return AlertLevel.CAUTION
        else:
            return AlertLevel.SAFE

    def _apply_hysteresis(self, side_state: SideState, cri: float) -> AlertLevel:
        """
        Apply hysteresis independently to a given side.
        Upgrade: CRI ≥ θ_k for N_h consecutive timesteps.
        Downgrade: CRI < θ_k - δ_h.
        """
        raw_level = self._cri_to_level(cri)
        current = side_state.current_level

        if raw_level.value > current.value:
            # Potential upgrade
            if side_state.pending_level == raw_level:
                side_state.upgrade_counter += 1
            else:
                side_state.pending_level = raw_level
                side_state.upgrade_counter = 1

            if side_state.upgrade_counter >= Params.N_H:
                side_state.current_level = raw_level
                side_state.upgrade_counter = 0
                side_state.pending_level = None
        elif raw_level.value < current.value:
            # Check downgrade with hysteresis band
            thresholds = [0, Params.THETA_1, Params.THETA_2, self.theta_3]
            threshold = thresholds[current.value]
            if cri < threshold - Params.DELTA_H:
                side_state.current_level = raw_level
            side_state.upgrade_counter = 0
            side_state.pending_level = None
        else:
            # Same level — reset upgrade counter
            side_state.upgrade_counter = 0
            side_state.pending_level = None

        return side_state.current_level

    # ============================================================
    # MAIN PROCESSING — CALLED EACH BSM CYCLE
    # ============================================================
    def process_step(self, ego: VehicleState, 
                     targets: Dict[str, VehicleState],
                     received_vids: set) -> dict:
        """
        Process one BSM cycle for the ego vehicle.
        
        Args:
            ego: Current ego vehicle state
            targets: Dict of target VID → VehicleState (only those received this cycle)
            received_vids: Set of VIDs that were successfully received
            
        Returns:
            Dict with CRI_left, CRI_right, alert levels, and per-target details.
        """
        # Update trackers for all known targets
        all_known = set(self.target_trackers.keys()) | set(targets.keys())
        
        for vid in all_known:
            if vid not in self.target_trackers:
                self.target_trackers[vid] = TargetTracker(vid=vid)
            
            tracker = self.target_trackers[vid]
            received = vid in received_vids
            self._update_tracker(tracker, received, targets.get(vid))

        # Compute CRI for each tracked target with valid state
        left_cris = []
        right_cris = []
        target_details = []

        for vid, tracker in list(self.target_trackers.items()):
            if tracker.last_state is None:
                continue
            
            # Skip if target is beyond communication range
            dx = tracker.last_state.x - ego.x
            dy = tracker.last_state.y - ego.y
            dist = np.sqrt(dx**2 + dy**2)
            if dist > Params.R_COMM:
                continue

            result = self._compute_cri_for_target(ego, tracker.last_state, tracker)
            result['distance'] = dist
            target_details.append(result)

            if result['side'] == "LEFT":
                left_cris.append(result['cri'])
            else:
                right_cris.append(result['cri'])

        # §3.4: CRI per side (empty-set default = 0.0)
        cri_left = max(left_cris) if left_cris else 0.0
        cri_right = max(right_cris) if right_cris else 0.0

        # §7: Apply hysteresis independently per side
        alert_left = self._apply_hysteresis(self.left_state, cri_left)
        alert_right = self._apply_hysteresis(self.right_state, cri_right)

        result = {
            'ego_vid': ego.vid,
            'cri_left': cri_left,
            'cri_right': cri_right,
            'alert_left': alert_left.name,
            'alert_right': alert_right.name,
            'num_targets': len(target_details),
            'target_details': target_details,
        }

        self.last_computation = result
        return result

    # ============================================================
    # CLEANUP: Remove stale trackers periodically
    # ============================================================
    def cleanup_stale_trackers(self, max_stale_steps: int = 50):
        """Remove trackers that have been stale for too long."""
        to_remove = [
            vid for vid, tracker in self.target_trackers.items()
            if tracker.k_lost > max_stale_steps
        ]
        for vid in to_remove:
            del self.target_trackers[vid]
