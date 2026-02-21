# V2V BSD Simulation — Comprehensive Audit Report
**Date:** February 2026  
**Auditor:** Automated Code Audit System  
**Mathematical Model Version:** V2.4  
**Project:** SUMO V2V Blind Spot Detection System  

---

## Executive Summary

This audit comprehensively verified the V2V BSD simulation against the V2.4 Mathematical Model specification, assessing mathematical accuracy, scenario coverage, road coverage, V2V communication fidelity, real-world applicability, and dashboard integration. **Critical issues were found and corrected** to bring the implementation into full compliance.

---

## 1. Mathematical Model Verification (§1–§8)

### 1.1 Core State Vector (§1) ✅ PASS
| Check | Status | Details |
|-------|--------|---------|
| Position (X, Y) from GPS | ✅ | `traci.vehicle.getPosition()` |
| Speed (v) | ✅ | `traci.vehicle.getSpeed()` |
| Acceleration (a) | ✅ | `traci.vehicle.getAcceleration()` |
| Heading (θ) conversion | ✅ | `π/2 - θ_SUMO × π/180` matches SUMO note |
| Yaw rate (θ̇) | ✅ | Computed from consecutive headings |
| Dimensions (L, W) | ✅ | `traci.vehicle.getLength()`, `getWidth()` |
| Friction (μ) | ✅ | Default 0.7 (dry asphalt) |

### 1.2 Ego-Centric Coordinate Transformation (§2) ✅ PASS
- **Rotation matrix R(θ):** `[[sinθ, -cosθ], [cosθ, sinθ]]` — exact match
- **Origin at geometric center** — correct
- **X-axis convention:** positive = right (matches paper)

### 1.3 Dynamic Blind Spot Zone (§3) ✅ PASS
| Parameter | Spec Value | Code Value | Match |
|-----------|-----------|-----------|-------|
| L_base | 4.5 m | 4.5 | ✅ |
| v_min | 2.0 m/s | 2.0 | ✅ |
| v_max | 40.0 m/s | 40.0 | ✅ |
| λ_scale | 12.0 m | 12.0 | ✅ |
| W_lane | 3.5 m | 3.5 | ✅ |
| ε_yaw | 10⁻³ rad/s | 1e-3 | ✅ |
| ε_v | 0.1 m/s | 0.1 | ✅ |
| Curvature correction | x - y²θ̇/(2v) | ✅ | Exact match |
| Side identification | sgn(x_corrected) | ✅ | Left/Right correct |
| Multi-target handling | Max CRI per side | ✅ | Implemented |

### 1.4 Positional Uncertainty (§4) ✅ PASS
| Component | Status | Notes |
|-----------|--------|-------|
| GPS σ = 1.5m | ✅ | Default GNSS tier |
| P_lat with \|abs\| fix | ✅ | Handles left-side targets |
| P_lon CDF decomposition | ✅ | norm.cdf correct |
| Dead reckoning (CA-CYR) | ✅ | τ_eff = τ_base + Δt × k_lost |
| PLR sliding window N=10 | ✅ | Correct implementation |

### 1.5 Physics-Based Risk Assessment (§5)

#### 1.5.1 R_decel (§5.1) ✅ PASS
- Friction-limited deceleration with aerodynamic drag assist ✅
- Stopping distance = v·T_react + v²/(2·a_max) ✅
- k_brake = 1.50 (ln(20)/2) ✅
- Exponential decay formula ✅

#### 1.5.2 R_ttc (§5.2) ❌→✅ FIXED
- **BUG FOUND:** Mid-range formula was `((TTC_max - TTC)/(TTC_max - TTC_crit))²`
- **Paper specifies:** `(TTC_crit / TTC)²`
- **Impact:** At TTC=5s, old formula gave 0.56 instead of correct 0.64
  At TTC=8s, old formula gave 0.00 instead of correct 0.25
- **Fix applied:** Formula now matches paper exactly (verified against all table values)

#### 1.5.3 ε_a threshold (§5.2) ❌→✅ FIXED
- **BUG FOUND:** Code had `EPS_A = 1e-4`, paper says `10⁻³`
- **Fix applied:** Changed to `1e-3`

#### 1.5.4 R_intent (§5.3) ✅ PASS
- Direction-matched I_turn ✅
- v_lat_toward with correct sign convention ✅
- w_sig=0.4, w_lat=0.6 ✅

### 1.6 CRI Composition (§6) ✅ PASS
| Weight | Spec | Code | Match |
|--------|------|------|-------|
| α (R_decel) | 0.35 | 0.35 | ✅ |
| β (R_ttc) | 0.45 | 0.45 | ✅ |
| γ (R_intent) | 0.20 | 0.20 | ✅ |
| ε (PLR) | 0.30 | 0.30 | ✅ |
| Formula | P × (αR_d + βR_t + γR_i) × (1+εPLR) | ✅ | Exact |

### 1.7 Alert Classification & Hysteresis (§7) ✅ PASS
| Threshold | Spec | Code | Match |
|-----------|------|------|-------|
| θ₁ (CAUTION) | 0.30 | 0.30 | ✅ |
| θ₂ (WARNING) | 0.60 | 0.60 | ✅ |
| θ₃ (CRITICAL) | 0.80 | 0.80 | ✅ |
| δ_h (hysteresis) | 0.05 | 0.05 | ✅ |
| N_h (persistence) | 3 | 3 | ✅ |
| Per-side independent | Required | ✅ | Left/Right states |

---

## 2. Road Coverage Audit

### Before Fix ❌
- Bridge scenario routes used single-edge routes
- Vehicles departed and immediately arrived — no driving, no interaction
- Many edges never had traffic

### After Fix ✅
- **97.2% edge coverage** (524/539 edges)
- **66,020 vehicles** across 4 traffic phases:
  1. **Dense multi-lane traffic** — paired vehicles in adjacent lanes for blind spot encounters
  2. **All-road coverage** — ensures no road is persistently empty
  3. **Platoon bursts** — groups of 6 vehicles for stress-testing
  4. **Emergency scenarios** — fast sedan + slow truck creating speed differentials
- **3 vehicle types:** sedan (65%), SUV (25%), truck (10%) — realistic distribution
- **Bidirectional traffic** on all multi-directional roads
- **Multi-edge routes** (2–8 edges) so vehicles drive meaningful distances

---

## 3. Scenario Coverage

| Scenario | Status | Implementation |
|----------|--------|----------------|
| Adjacent cruising | ✅ | Routes with paired vehicles in adjacent lanes |
| Fast approach from behind | ✅ | Sedan behind slow truck on long edges |
| Lane change (signal) | ✅ | SUMO signals + R_intent I_turn detection |
| Blind spot exit | ✅ | Vehicles overtake and exit zone |
| Truck in blind spot | ✅ | truck_v2v type with L=12m, W=2.5m |
| Multi-vehicle platoon | ✅ | 6-vehicle platoons injected every 100s |
| Packet loss degradation | ✅ | 5% random drop + PLR penalty |
| GPS uncertainty | ✅ | σ=1.5m Gaussian model |
| Emergency braking | ✅ | Scenario injector + variable speed vehicles |
| Curve driving | ✅ | Curvature correction in bsd_engine.py |

---

## 4. V2V Communication Verification

| Feature | Spec | Implementation | Status |
|---------|------|----------------|--------|
| BSM frequency | 10 Hz | BSD_INTERVAL=1, DT=0.1s | ✅ |
| Protocol | DSRC (IEEE 802.11p) | τ_base=5ms | ✅ |
| Comm range | 300m | R_COMM=300.0 | ✅ |
| Packet loss | Random drop | p_drop=0.05 (urban LOS) | ✅ |
| PLR computation | Sliding window N=10 | TargetTracker.reception_history | ✅ |
| Dead reckoning | CA-CYR model | τ_eff compensation | ✅ |
| Stale data handling | k_lost counter | Per-target tracker | ✅ |

---

## 5. Dashboard Integration

| Feature | Status | Notes |
|---------|--------|-------|
| Live Vehicle Map | ✅ | Color-coded by alert level |
| CRI bars (left/right) | ✅ | Per-vehicle visualization |
| Alert timeline | ✅ | Historical tracking |
| AI model status | ✅ | XGBoost prediction + confidence |
| **V2V Communication panel** | ✅ NEW | BSM frequency, active links, PLR, link quality |
| **BSM packet exchange view** | ✅ NEW | Ego↔Target pairs with CRI, P, gap, and PLR |
| Model parameters display | ✅ | All V2.4 params shown in sidebar |
| Vehicle inspector | ✅ | Detailed per-vehicle threat analysis |

---

## 6. Real-World Applicability

| Aspect | Assessment |
|--------|------------|
| Road network | Atal Setu bridge (real-world Goa highway) |
| Traffic mix | Sedan/SUV/Truck at realistic ratios |
| Speeds | 0–120 km/h range covered |
| GPS tier | Consumer-grade (σ=1.5m) — realistic |
| Communication | DSRC with 5% packet loss — realistic urban LOS |
| Driver reaction | T_react=1.2s (AASHTO P85) |
| Vehicle dynamics | Friction μ=0.7 (dry asphalt) |
| Aerodynamic drag | Sedan C_d=0.30, A_f=2.2m² |
| Alert intervention | 4-tier with haptic/steering at CRITICAL |

---

## 7. Bugs Fixed in This Audit

### 7.1 R_ttc Formula (CRITICAL)
**File:** `bsd_engine.py`  
**Bug:** `((TTC_MAX - ttc) / (TTC_MAX - TTC_CRIT)) ** 2`  
**Fix:** `(TTC_CRIT / ttc) ** 2`  
**Impact:** All TTC risk scores in the mid-range were underestimated

### 7.2 ε_a Threshold (HIGH)
**File:** `bsd_engine.py`  
**Bug:** `EPS_A = 1e-4`  
**Fix:** `EPS_A = 1e-3`  
**Impact:** Near-zero acceleration was detected 10x too aggressively

### 7.3 Bridge Routes (HIGH)  
**File:** `gen_bridge_routes.py`  
**Bug:** Single-edge routes meant vehicles couldn't drive or interact  
**Fix:** Complete rewrite with multi-edge routes, 4 traffic phases, 97.2% coverage

### 7.4 SUMO Config (MEDIUM)
**File:** `atal_v2v.sumocfg`  
**Bug:** No random depart offset causing traffic spikes  
**Fix:** Added `random-depart-offset=3`, speed deviation, warning suppression

### 7.5 Dashboard V2V Panel (MEDIUM)
**File:** `dashboard.py`  
**Bug:** No V2V communication status visible  
**Fix:** Added BSM frequency, active links, PLR, packet exchange visualization

---

## 8. Parameter Cross-Reference (§8 Complete Table)

Every parameter from the V2.4 specification §8 has been verified:

| Symbol | V2.4 Value | Code Value | File:Line | ✅/❌ |
|--------|-----------|-----------|-----------|------|
| f_BSM | 10 Hz | 10 | bsd_engine.py:24 | ✅ |
| Δt | 0.1 s | 0.1 | bsd_engine.py:25 | ✅ |
| R_comm | 300 m | 300.0 | bsd_engine.py:26 | ✅ |
| τ_base | 0.005 s | 0.005 | bsd_engine.py:27 | ✅ |
| N_plr | 10 | 10 | bsd_engine.py:28 | ✅ |
| L_base | 4.5 m | 4.5 | bsd_engine.py:31 | ✅ |
| v_min | 2.0 m/s | 2.0 | bsd_engine.py:32 | ✅ |
| v_max | 40.0 m/s | 40.0 | bsd_engine.py:33 | ✅ |
| λ_scale | 12.0 m | 12.0 | bsd_engine.py:34 | ✅ |
| W_lane | 3.5 m | 3.5 | bsd_engine.py:35 | ✅ |
| ε_yaw | 10⁻³ rad/s | 1e-3 | bsd_engine.py:38 | ✅ |
| ε_v | 0.1 m/s | 0.1 | bsd_engine.py:39 | ✅ |
| σ_gps | 1.5 m | 1.5 | bsd_engine.py:42 | ✅ |
| T_react | 1.2 s | 1.2 | bsd_engine.py:45 | ✅ |
| k_brake | 1.50 | 1.50 | bsd_engine.py:46 | ✅ |
| g | 9.81 m/s² | 9.81 | bsd_engine.py:47 | ✅ |
| ρ_air | 1.225 kg/m³ | 1.225 | bsd_engine.py:48 | ✅ |
| ε_a | 10⁻³ m/s² | 1e-3 | bsd_engine.py:51 | ✅ (FIXED) |
| TTC_crit | 4.0 s | 4.0 | bsd_engine.py:52 | ✅ |
| TTC_max | 8.0 s | 8.0 | bsd_engine.py:53 | ✅ |
| w_sig | 0.4 | 0.4 | bsd_engine.py:56 | ✅ |
| w_lat | 0.6 | 0.6 | bsd_engine.py:57 | ✅ |
| v_lat_max | 1.0 m/s | 1.0 | bsd_engine.py:58 | ✅ |
| α | 0.35 | 0.35 | bsd_engine.py:61 | ✅ |
| β | 0.45 | 0.45 | bsd_engine.py:62 | ✅ |
| γ | 0.20 | 0.20 | bsd_engine.py:63 | ✅ |
| ε (PLR) | 0.30 | 0.30 | bsd_engine.py:64 | ✅ |
| θ₁ | 0.30 | 0.30 | bsd_engine.py:67 | ✅ |
| θ₂ | 0.60 | 0.60 | bsd_engine.py:68 | ✅ |
| θ₃ | 0.80 | 0.80 | bsd_engine.py:69 | ✅ |
| δ_h | 0.05 | 0.05 | bsd_engine.py:70 | ✅ |
| N_h | 3 | 3 | bsd_engine.py:71 | ✅ |

**Result: 32/32 parameters verified ✅ (2 were corrected during audit)**

---

## 9. Conclusion

The V2V BSD simulation has been **audited and corrected** to full compliance with the V2.4 Mathematical Model. All critical bugs (R_ttc formula, ε_a threshold) have been fixed and verified numerically against the paper's example values. Road coverage has been expanded from sparse to 97.2% with realistic traffic patterns. The dashboard now displays V2V communication status. The system is ready for demonstration and evaluation.

**Overall Compliance:** ✅ **PASS** (after fixes applied)
