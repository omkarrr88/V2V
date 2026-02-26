# Comprehensive Mathematical Model for V2V Blind Spot Detection (BSD)

**Version 3.0 — Incorporating Real-World Kinematics, Network Volatility, and Environmental Physics for SUMO & Physical Deployment**

---

## 1. Introduction and Core System State

This model defines a mathematically rigorous, computationally complete framework for a V2V-based Blind Spot Detection (BSD) system. It is designed to be directly executable in microscopic traffic simulators (SUMO via TraCI) while remaining fully valid for real-world deployment on Autonomous Vehicles (AVs) or Advanced Driver Assistance Systems (ADAS).

**System Entities:**
*   **Ego Vehicle** ($V_e$): The subject vehicle performing blind spot monitoring.
*   **Target Vehicle** ($V_t$): Any neighboring vehicle broadcasting its state via V2V.

**Communication Protocol:**
Vehicles broadcast Basic Safety Messages (BSM) conforming to SAE J2735 over DSRC (IEEE 802.11p) or C-V2X (3GPP) at a frequency of $f_{BSM} = 10$ Hz (i.e., every $\Delta t = 0.1$ s). Maximum effective communication range is $R_{comm} = 300$ m for DSRC.

**State Vector:**
The state of vehicle $i \in \{e, t\}$ at time $t$ is:
$$ \mathbf{S}_i(t) = \left[ X_i(t),\; Y_i(t),\; v_i(t),\; a_i(t),\; \theta_i(t),\; \dot{\theta}_i(t),\; L_i,\; W_i,\; M_i,\; \mu(t) \right] $$

**Variable Definitions:**

| Symbol | Description | Source | Unit |
|--------|-------------|--------|------|
| $X_i, Y_i$ | Global position coordinates | RTK-GPS / GNSS | m |
| $v_i$ | Longitudinal velocity (scalar, $\geq 0$) | Wheel speed sensors / CAN bus | m/s |
| $a_i$ | Longitudinal acceleration ($+$ = accelerating, $-$ = braking) | IMU / CAN bus | m/s² |
| $\theta_i$ | Heading angle (counterclockwise from positive X-axis) | GPS/IMU heading | rad |
| $\dot{\theta}_i$ | Yaw rate (rate of heading change) | Gyroscope / IMU / steering angle sensor | rad/s |
| $L_i$ | Vehicle length | Static vehicle parameter | m |
| $W_i$ | Vehicle width | Static vehicle parameter | m |
| $M_i$ | Vehicle mass | OBD-II / CAN bus (Ego); estimated from BSM Part II vehicle classification (Target) | kg |
| $\mu(t)$ | Road surface friction coefficient | ABS/TCS sensor estimation | — |

**Typical Friction Values:**

| Surface Condition | $\mu$ Range |
|-------------------|-------------|
| Dry asphalt | 0.7 – 0.8 |
| Wet asphalt | 0.4 – 0.5 |
| Packed snow | 0.2 – 0.3 |
| Ice | 0.08 – 0.15 |

> **SUMO Implementation Notes:**
> - **Yaw rate:** SUMO does not output yaw rate as a continuous signal. It must be computed from consecutive heading outputs: $\dot{\theta}_i(t) \approx \frac{\theta_i(t) - \theta_i(t - \Delta t)}{\Delta t}$.
> - **Angle conversion:** SUMO's `traci.vehicle.getAngle()` returns heading in degrees measured clockwise from North. Convert to the mathematical convention used in this model via: $\theta_{math} = \frac{\pi}{2} - \theta_{SUMO} \cdot \frac{\pi}{180}$.
> - **Friction coefficient:** In SUMO, $\mu$ is not dynamically sensed. It is read from the road network definition file (`friction` attribute per edge/lane) and treated as a known constant per road segment. In real-world deployment, $\mu$ is estimated dynamically via ABS/TCS wheel slip ratio analysis.

---

## 2. Ego-Centric Coordinate Transformation

Raw GPS/GNSS coordinates are in a global Earth frame and are not directly useful for blind spot geometry. All target positions must be transformed into an **Ego-Centric Local Frame** where:
*   **Origin** is at $V_e$'s **geometric center** (i.e., the midpoint of the vehicle's bounding box).
*   **Positive Y-axis** aligns with $V_e$'s forward heading direction.
*   **Positive X-axis** points to $V_e$'s right side.

With this convention, the Ego vehicle's front bumper is at $y = +L_e/2$ and rear bumper is at $y = -L_e/2$ in the local frame.

> **Simplification Note (GPS Antenna Offset):** This model assumes the GPS antenna position coincides with the vehicle's geometric center. In practice, GPS antennas are mounted on the vehicle roof, offset from the geometric center by up to 1–2 m. In SUMO, the default vehicle reference point may also differ. This offset introduces a small systematic bias ($\leq 2$ m) that is within the GPS uncertainty envelope ($\sigma_{gps} = 1.5$ m) and is therefore absorbed by the probabilistic treatment in Section 4.1 without requiring an explicit correction term.

**Angle Convention:** All heading angles $\theta$ in this model are measured **counterclockwise from the positive X-axis** (standard mathematical convention).

**GPS Antenna Lever-Arm Correction:**
If the GPS antenna is not located at the true center of the vehicle (e.g., mounted on the rear roof), the reported coordinate $(X_{gps}, Y_{gps})$ must be corrected to the true vehicle centroid $(X_{true}, Y_{true})$:
$$ X_{true} = X_{gps} - L_{offset} \cdot \cos(\theta) $$
$$ Y_{true} = Y_{gps} - L_{offset} \cdot \sin(\theta) $$



**Transformation:**

$$ \begin{bmatrix} x_{rel}(t) \\ y_{rel}(t) \end{bmatrix} = \mathbf{R}(\theta_e) \cdot \begin{bmatrix} X_t(t) - X_e(t) \\ Y_t(t) - Y_e(t) \end{bmatrix} $$

Where the rotation matrix is:

$$ \mathbf{R}(\theta_e) = \begin{bmatrix} \sin \theta_e & -\cos \theta_e \\ \cos \theta_e & \sin \theta_e \end{bmatrix} $$

**Interpretation:**
*   $x_{rel} > 0$: Target is to the **right** of Ego.
*   $x_{rel} < 0$: Target is to the **left** of Ego.
*   $y_{rel} > 0$: Target is **ahead** of Ego.
*   $y_{rel} < 0$: Target is **behind** Ego.

---

## 3. Dynamic Blind Spot Zone Definition

Standard blind spots are not static rectangles — they **elongate** with velocity and **bend** with road curvature. This section formally defines the blind spot zone boundaries and the detection function $D_{bs}$.

### 3.1 Longitudinal Extent

The longitudinal length of the blind spot zone is dynamically scaled by the Ego vehicle's velocity:

$$ L_{bs}(v_e) = L_{base} + \left( \frac{\text{clamp}(v_e,\; v_{min},\; v_{max}) - v_{min}}{v_{max} - v_{min}} \right) \cdot \lambda_{scale} $$

Where $\text{clamp}(x, a, b) = \max(a, \min(x, b))$.

**Parameters:**

| Parameter | Value | Justification |
|-----------|-------|---------------|
| $L_{base}$ | 4.5 m | Minimum blind spot ≈ one car length |
| $v_{min}$ | 2.0 m/s | Below this, blind spot risk is negligible |
| $v_{max}$ | 40.0 m/s (144 km/h) | Scaling saturates at highway speeds |
| $\lambda_{scale}$ | 12.0 m | Additional length at maximum speed |

**Resulting Range:** $L_{bs} \in [4.5,\; 16.5]$ m.

### 3.2 Curvature Correction

When $V_e$ is navigating a curve, raw ego-centric coordinates cause lateral drift. A first-order clothoid correction compensates for the Ego's road curvature:

$$ x_{corrected} = \begin{cases} x_{rel} - \dfrac{y_{rel}^2 \cdot \dot{\theta}_e}{2 \cdot v_e} & \text{if } |\dot{\theta}_e| \geq \epsilon_{yaw} \text{ and } v_e > \epsilon_v \\ x_{rel} & \text{otherwise (straight-line driving)} \end{cases} $$

Where:
*   $\epsilon_{yaw} = 10^{-3}$ rad/s (yaw rate threshold for straight-line detection)
*   $\epsilon_v = 0.1$ m/s (minimum velocity for curvature to be meaningful)

> **Note:** The expression $\frac{y_{rel}^2 \cdot \dot{\theta}_e}{2 \cdot v_e}$ is algebraically equivalent to $\frac{y_{rel}^2}{2 R_{curve}}$ where $R_{curve} = v_e / \dot{\theta}_e$, but avoids division by $\dot{\theta}_e$ and the potential division-by-zero.

> **Scope Limitation:** This correction accounts only for the **Ego vehicle's own curvature**. The Target vehicle's independent curvature/heading is not incorporated into the correction. When both vehicles are following the same curved road (e.g., highway curve), this is acceptable since both experience similar curvature. However, in scenarios with significantly differing trajectories (e.g., roundabouts, diverging ramps), the correction accuracy degrades. This is a known first-order approximation and is stated as a formal limitation in Section 9.3.

### 3.3 Formal Blind Spot Boundary Conditions

A target vehicle $V_t$ is detected within the blind spot zone if **both** of the following conditions hold simultaneously:

**Lateral Condition** (the target occupies an adjacent lane):
$$ \frac{W_e}{2} \leq |x_{corrected}| \leq \frac{W_e}{2} + W_{lane} $$

**Longitudinal Condition** (the target is beside or behind the Ego):
$$ -L_{bs}(v_e) \leq y_{rel} \leq \frac{L_e}{2} $$

Where $W_{lane}$ is the lane width (configurable parameter, default $W_{lane} = 3.5$ m per AASHTO / IRC national highway specification; for urban roads $W_{lane} = 3.0$ m or narrower may be appropriate depending on local road standards). Since the origin is at the Ego's geometric center (Section 2), $\frac{L_e}{2}$ corresponds exactly to the Ego's **front bumper**. A vehicle fully ahead of the front bumper is in the Ego's peripheral/forward field of view, not the blind spot.

**Complete Boolean Detection Function:**

$$ D_{bs}(V_t) = \mathbb{1}\!\left[\frac{W_e}{2} \leq |x_{corrected}| \leq \frac{W_e}{2} + W_{lane}\right] \cdot \mathbb{1}\!\left[-L_{bs}(v_e) \leq y_{rel} \leq \frac{L_e}{2}\right] $$

Where $\mathbb{1}[\cdot]$ is the indicator function (returns 1 if the condition is true, 0 otherwise). The zone covers **both sides** (left and right) via the absolute value $|x_{corrected}|$.

### 3.4 Multi-Target Handling and Side Identification

When multiple target vehicles $\{V_{t_1}, V_{t_2}, \ldots, V_{t_n}\}$ are within $R_{comm}$, the system evaluates each independently.

**Side-Specific CRI Output:**

A single scalar CRI is insufficient for driver action — the driver must know **which side** the threat is on. Each target is assigned to a side based on $\text{sgn}(x_{corrected})$:

$$\text{side}(V_t) = \begin{cases} \text{LEFT} & \text{if } x_{corrected} < 0 \\ \text{RIGHT} & \text{if } x_{corrected} \geq 0 \end{cases}$$

The system outputs **two independent CRI values** — one per side:

$$ CRI_{left} = \max_{j \;:\; \text{side}(V_{t_j}) = \text{LEFT}} \; CRI_{final}(V_{t_j}) $$
$$ CRI_{right} = \max_{j \;:\; \text{side}(V_{t_j}) = \text{RIGHT}} \; CRI_{final}(V_{t_j}) $$

If no targets are present on a given side, the CRI for that side defaults to zero: $CRI_{side} = 0.0$ (maximum over an empty set is defined as zero in this model).

Each side is alerted independently using the threshold table in Section 7. This enables side-specific visual indicators (e.g., left mirror LED vs. right mirror LED) and directionally correct steering intervention.

---

## 4. Positional Uncertainty and Network Compensation

Real V2V networks suffer from GPS drift, packet loss, and communication latency. This section accounts for these imperfections.

### 4.1 GPS Uncertainty Modeling

V2V positions are probability distributions, not deterministic points.

**Theoretical Foundation:**
$$ P(V_t \in Z_{bs}) = \iint_{Z_{bs}} \mathcal{N}\!\left(\begin{bmatrix} \hat{x}_{rel} \\ \hat{y}_{rel} \end{bmatrix}, \Sigma_{gps}\right) dx\, dy $$

Where $\Sigma_{gps}$ is the GPS error covariance matrix:
$$ \Sigma_{gps} = \begin{bmatrix} \sigma_x^2 & 0 \\ 0 & \sigma_y^2 \end{bmatrix}, \quad \sigma_x = \sigma_y = \sigma_{gps} $$

**GPS Accuracy Tiers:**

| GPS Technology | $\sigma_{gps}$ | Typical Use Case |
|----------------|-----------------|------------------|
| RTK-GPS (high-end) | 0.5 m | AV research, high-precision ADAS |
| DGPS (differential) | 1.0 m | Fleet management, commercial V2V |
| Standard GNSS (consumer) | 1.5 – 3.0 m | Consumer vehicles, mass-market V2V |

The default value used in this model is $\sigma_{gps} = 1.5$ m (standard GNSS), representing realistic mass-market V2V deployment conditions. The model's performance under different GPS accuracy tiers should be evaluated via sensitivity analysis. Higher $\sigma_{gps}$ values broaden the probability distribution, causing more conservative (higher) $P(V_t \in Z_{bs})$ estimates and earlier alerts.

**Practical Closed-Form Approximation (for real-time computation at 10 Hz):**

Since the blind spot zone $Z_{bs}$ is a rectangle in the ego frame and the covariance matrix is diagonal, the 2D integral decomposes into a product of independent 1D CDFs:

$$ P(V_t \in Z_{bs}) \approx P_{lat} \times P_{lon} $$

$$ P_{lat} = \left|\;\Phi\!\left(\frac{x_{outer} - \hat{x}_{rel}}{\sigma_x}\right) - \Phi\!\left(\frac{x_{inner} - \hat{x}_{rel}}{\sigma_x}\right)\;\right|$$

$$ P_{lon} = \Phi\!\left(\frac{y_{front} - \hat{y}_{rel}}{\sigma_y}\right) - \Phi\!\left(\frac{y_{rear} - \hat{y}_{rel}}{\sigma_y}\right) $$

Where:
*   $\Phi(\cdot)$ is the standard normal CDF.
*   $x_{outer} = \text{sgn}(\hat{x}_{rel}) \cdot \left(\frac{W_e}{2} + W_{lane}\right)$ (far edge of adjacent lane)
*   $x_{inner} = \text{sgn}(\hat{x}_{rel}) \cdot \frac{W_e}{2}$ (ego vehicle body edge)
*   $y_{front} = \frac{L_e}{2}$, $\; y_{rear} = -L_{bs}(v_e)$
*   $\hat{x}_{rel}, \hat{y}_{rel}$ are the dead-reckoned position estimates from Section 4.2.
*   The naming $x_{outer}$/$x_{inner}$ refers to the **upper** and **lower** integration limits respectively (not geometric left/right). The $\text{sgn}(\hat{x}_{rel})$ automatically selects the correct sign for the target's side.

This approximation is mathematically equivalent to the theoretical integral for rectangular zones with diagonal covariance and executes in microseconds.

> **Forward/Rear Center-Lane Guard:** 
> V2V based BSD can occasionally trigger "phantom" side alerts for vehicles directly in front or behind the Ego due to lateral GPS jitter. To prevent this, a quadratic guard is applied to targets with small lateral offsets:
> If $|x_{hat}| < W_e/2$, then $P_{lat}$ is attenuated by $(\frac{|x_{hat}|}{W_e/2})^2$.
> This ensures that vehicles strictly in-line with the Ego vehicle have $P \to 0$ even if GPS noise pushes them momentarily over the $W_e/2$ boundary.

> **Side-Specificity Note:** The $\text{sgn}(\hat{x}_{rel})$ term in $x_{outer}$ and $x_{inner}$ automatically selects the correct lateral bounds for the side where the target is located. When $\hat{x}_{rel} > 0$ (target on right), the bounds become $[W_e/2,\; W_e/2 + W_{lane}]$. When $\hat{x}_{rel} < 0$ (target on left), the bounds become $[-(W_e/2 + W_{lane}),\; -W_e/2]$. Therefore, $P(V_t \in Z_{bs})$ is inherently side-specific and produces the correct probability for the side on which the target lies — no additional separation into $P_{left}$ and $P_{right}$ is required.

### 4.2 Network Latency Compensation (Dead Reckoning)

When $V_e$ receives a BSM at time $t$, the data was generated at time $t - \tau_{eff}$.

**Effective Delay:**
$$ \tau_{eff} = \tau_{base} + \Delta t \cdot k_{lost} $$

Where:
*   $\tau_{base}$: Base one-way communication latency (typical: 2–5 ms for DSRC, 10–20 ms for C-V2X).
*   $\Delta t = 0.1$ s: BSM broadcast interval at 10 Hz.
*   $k_{lost}$: Count of consecutively lost BSM packets (0 under normal conditions; resets to 0 upon successful reception).

Using a **Constant Acceleration, Constant Yaw Rate (CA-CYR)** prediction model:

$$ \hat{x}_{rel}(t) = x_{rel}(t-\tau_{eff}) + v_{rel,x} \cdot \tau_{eff} + \frac{1}{2}\, a_{rel,x} \cdot \tau_{eff}^2 $$

$$ \hat{y}_{rel}(t) = y_{rel}(t-\tau_{eff}) + v_{rel,y} \cdot \tau_{eff} + \frac{1}{2}\, a_{rel,y} \cdot \tau_{eff}^2 $$

Where relative velocities and accelerations are computed in the ego-centric frame at $t - \tau_{eff}$:
*   $v_{rel,y} = v_t \cos(\theta_t - \theta_e) - v_e$ (longitudinal relative velocity)
*   $v_{rel,x} = v_t \sin(\theta_t - \theta_e)$ (lateral relative velocity)
*   $a_{rel,y} = a_t \cos(\theta_t - \theta_e) - a_e$ (longitudinal relative acceleration)
*   $a_{rel,x} = a_t \sin(\theta_t - \theta_e)$ (lateral relative acceleration)

**Dead Reckoning Validity Constraint:** The CA-CYR model assumes constant acceleration and yaw rate over $\tau_{eff}$. This is valid for $\tau_{eff} \leq 0.5$ s (i.e., up to $k_{lost} \leq 4$ consecutive dropped packets at 10 Hz). When $\tau_{eff} > 0.5$ s, the dead-reckoned estimate becomes unreliable; the system should flag the target's state as **stale** and escalate the PLR penalty accordingly.

### 4.3 Packet Loss Ratio (PLR) — Gilbert-Elliott Markov Model

The probability of packet loss is modeled via a 2-state Markov channel (Gilbert-Elliott), capturing the bursty nature of DSRC/C-V2X shadowing:
- **GOOD State (G):** Low baseline loss rate (e.g., $PLR_{good} = 1\%$)
- **BAD State (B):** High burst loss rate (e.g., $PLR_{bad} = 50\%$)

Transitions are governed by:
- $p_{g \to b}$: Probability of entering a burst loss state.
- $p_{b \to g}$: Probability of recovering from a burst.

The PLR used in CRI weighting is defined empirically by the active channel state dynamically.

### 4.4 Packet Loss Penalty — Formal Definition

The PLR used in the CRI formula (Section 6) is defined as a **sliding window average** over the most recent $N_{plr}$ BSM intervals:

$$ PLR(t) = \frac{1}{N_{plr}} \sum_{k=0}^{N_{plr}-1} \mathbb{1}[\text{BSM from } V_t \text{ was not received at } t - k \cdot \Delta t] $$

Where $N_{plr} = 10$ (averaging window of 1.0 second at 10 Hz). $PLR \in [0, 1]$: a value of 0 indicates all packets were received; a value of 1 indicates complete communication failure over the window.

> **SUMO Note:** PLR should be simulated by randomly dropping BSM packets with probability $p_{drop}$ per timestep. Typical values: $p_{drop} = 0.05$ (urban LOS), $p_{drop} = 0.15$ (urban NLOS), $p_{drop} = 0.30$ (heavy congestion). When a packet is dropped, $k_{lost}$ increments for dead reckoning; upon successful reception, $k_{lost}$ resets to 0.

---

## 5. Physics-Based Risk Assessment

Once a target is detected in or near the blind spot zone, three independent risk components quantify the collision danger. Each component outputs a value in $[0, 1]$.

### 5.1 Friction-Limited Deceleration Risk ($R_{decel}$)

This component answers: *If the Ego vehicle suddenly merges, can the Target vehicle physically stop in time?*

**Step 1 — Maximum Physical Deceleration Capability of Target:**

$$ a_{max,t} = \mu \cdot g + \frac{C_d \cdot A_f \cdot \rho_{air} \cdot v_t^2}{2 \cdot M_t} $$

Where:
*   $\mu \cdot g$: Tire-road friction deceleration ($g = 9.81$ m/s²).
*   Second term: Aerodynamic drag **assists** deceleration (opposes forward motion).

| Parameter | Symbol | Typical Value |
|-----------|--------|---------------|
| Prob. Good $\to$ Burst | {g \to b}$ | 0.01 |
| Prob. Burst $\to$ Good | {b \to g}$ | 0.10 |
| Base PLR (Good) | {good}$ | 1\% |
| Burst PLR (Bad) | {bad}$ | 50\% |
| Lateral Gap | {gap}$ | {lane} - W_e/2 - W_t/2$ |
|
| Gravitational acceleration | $g$ | 9.81 m/s² |
| Drag coefficient | $C_d$ | 0.30 (sedan), 0.35 (SUV), 0.60 (truck) |
| Frontal area | $A_f$ | 2.2 m² (sedan), 3.0 m² (SUV), 8.0 m² (truck) |
| Air density | $\rho_{air}$ | 1.225 kg/m³ (at sea level, 15°C) |

**Step 2 — Required Stopping Distance:**

$$ D_{stop\_req} = v_t \cdot T_{react} + \frac{v_t^2}{2 \cdot a_{max,t}} $$

*   $T_{react} = 1.2$ s (85th-percentile human driver reaction time from AASHTO Green Book).
*   For ADAS-equipped vehicles: $T_{react} = 0.3$ s may be used (sensor-to-actuator loop).

**Step 3 — Bumper-to-Bumper Gap:**

$$ d_{gap} = |\hat{y}_{rel}(t)| - \frac{L_e + L_t}{2} $$

This is the **longitudinal** bumper-to-bumper gap: $|\hat{y}_{rel}|$ is the longitudinal center-to-center distance in the ego frame, and subtracting the half-lengths of both vehicles converts it to the physical gap between the nearest bumpers. If $d_{gap} \leq 0$, the bounding boxes overlap longitudinally.

**Step 4 — Deceleration Risk Factor:**

$$ R_{decel} = \begin{cases} 1.0 & \text{if } d_{gap} \leq 0 \\ \min\!\left(1,\; \exp\!\left(-k_{brake} \cdot \dfrac{d_{gap} - D_{stop\_req}}{D_{stop\_req}}\right)\right) & \text{if } d_{gap} > 0 \end{cases} $$

**Derivation of $k_{brake}$:**
We require $R_{decel} \approx 0.05$ (effectively zero risk) when $d_{gap} = 3 \times D_{stop\_req}$ (the target has 3× the needed stopping distance — a clearly safe margin):
$$ 0.05 = \exp(-k_{brake} \cdot 2) \implies k_{brake} = \frac{\ln 20}{2} \approx 1.50 $$

**$k_{brake} = 1.50$**

**Behavior Verification:**

| $d_{gap}$ | $R_{decel}$ | Interpretation |
|-----------|-------------|----------------|
| $\leq 0$ | 1.00 | Overlap — maximum risk |
| $= D_{stop\_req}$ | 1.00 | At stopping limit |
| $= 2 \times D_{stop\_req}$ | 0.22 | Some margin |
| $= 3 \times D_{stop\_req}$ | 0.05 | Safe |
| $\gg D_{stop\_req}$ | $\to 0$ | No risk |

### 5.2 Second-Order Time-To-Collision ($R_{ttc}$)

Standard TTC uses only relative velocity. This model incorporates **relative acceleration** for higher fidelity.

**Relative Motion Variables (along longitudinal ego axis):**
*   $v_{rel} = v_e - v_t \cos(\theta_t - \theta_e)$ (positive = Ego is closing on Target)
*   $a_{rel} = a_e - a_t \cos(\theta_t - \theta_e)$ (positive = Ego is accelerating toward Target)

> **Sign Convention Note:** The sign convention for $v_{rel}$ here (positive = closing) is the **opposite** of $v_{rel,y}$ in Section 4.2 (where positive = target moving ahead of ego). Both are internally consistent within their respective sections: Section 4.2 measures target velocity relative to ego for dead reckoning (position prediction), while this section measures closing speed for collision prediction. Implementers must maintain this distinction.

**Kinematic Equation:**
$$ d_{gap} = v_{rel} \cdot TTC + \frac{1}{2}\, a_{rel} \cdot TTC^2 $$

**Consolidated Piecewise Definition of $TTC_{accel}$:**

$$ TTC_{accel} = \begin{cases} \dfrac{d_{gap}}{v_{rel}} & \text{if } |a_{rel}| < \epsilon_a \text{ and } v_{rel} > 0 \\[8pt] \min^{+}\!\left\{\dfrac{-v_{rel} \pm \sqrt{\Delta}}{a_{rel}}\right\} & \text{if } |a_{rel}| \geq \epsilon_a \text{ and } \Delta \geq 0 \text{ and } \exists \text{ positive root} \\[8pt] \infty & \text{otherwise (no collision on current trajectory)} \end{cases} $$

Where:
*   $\epsilon_a = 10^{-3}$ m/s² (threshold below which relative acceleration is treated as zero)
*   $\Delta = v_{rel}^2 + 2 \cdot a_{rel} \cdot d_{gap}$ (discriminant of the kinematic quadratic)
*   $\min^{+}\{\cdot\}$ denotes the smallest **positive** root from the two solutions

**The "otherwise" case ($TTC_{accel} = \infty$) applies when any of the following holds:**
1.  $|a_{rel}| < \epsilon_a$ and $v_{rel} \leq 0$ → vehicles are separating or maintaining gap at constant velocity.
2.  $\Delta < 0$ → no real solution to the quadratic; trajectories diverge.
3.  Both roots of the quadratic are negative → the "collision" solution lies in the past, not the future.

**TTC Risk Function:**

$$ R_{ttc} = \begin{cases} 1.0 & \text{if } 0 < TTC_{accel} \leq TTC_{critical} \\ \left(\dfrac{TTC_{critical}}{TTC_{accel}}\right)^2 & \text{if } TTC_{critical} < TTC_{accel} \leq TTC_{max} \\ 0 & \text{otherwise (including } TTC_{accel} = \infty\text{)} \end{cases} $$

| Parameter | Value | Justification |
|-----------|-------|---------------|
| $TTC_{critical}$ | 4.0 s | NHTSA forward collision warning timing standard |
| $TTC_{max}$ | 8.0 s | Beyond this, collision is not imminent for BSD context |

**Behavior:**

### 5.2.1 Lateral Time-To-Collision ($TTC_{lat}$)

Blind spot collisions are primarily lateral side-swipes. The purely longitudinal TTC must be combined with a lateral closure analysis to detect side-swipe threats from swerving targets:

$$ TTC_{lat} = \frac{W_{gap}}{|v_{lat, rel}|} $$

Where:
*   $W_{gap} = W_{lane} - \frac{W_e}{2} - \frac{W_t}{2}$ (available lateral space)
*   $v_{lat, rel} = v_t \cdot \sin(\theta_t - \theta_e)$ (target lateral velocity relative to ego)
*   If $|v_{lat, rel}| < \varepsilon_v$, $TTC_{lat} = TTC_{max}$ (parallel track)

The unified TTC risk considers both axes:
$$ R_{ttc} = \max(R_{ttc, long}, R_{ttc, lat}) $$

Where the lateral risk mapping is linear:
$$ R_{ttc, lat} = \begin{cases} 1.0 - \frac{TTC_{lat}}{TTC_{critical}} & \text{if } TTC_{lat} \leq TTC_{critical} \\ 0 & \text{otherwise} \end{cases} $$

**Behavior:**



| $TTC_{accel}$ | $R_{ttc}$ | Interpretation |
|---------------|-----------|----------------|
| $\leq 4.0$ s | 1.00 | Imminent collision |
| 5.0 s | 0.64 | High risk |
| 6.0 s | 0.44 | Moderate risk |
| 8.0 s | 0.25 | Low risk |
| $> 8.0$ s | 0.00 | No imminent threat |

### 5.3 Lateral Intent and Lane-Change Prediction ($R_{intent}$)

A vehicle in the blind spot is primarily dangerous if the Ego vehicle **intends to merge** into its lane. This component captures lane-change intent from the Ego's own behavior.

**Turn Signal Indicator (Direction-Matched):**

$$ I_{turn} = \begin{cases} 1 & \text{if } (\text{side}(V_t) = \text{LEFT} \text{ and left blinker active}) \text{ or } (\text{side}(V_t) = \text{RIGHT} \text{ and right blinker active}) \\ 0 & \text{otherwise} \end{cases} $$

Only a blinker toward the **same side as the detected target** contributes to intent. A left blinker with a right-side target (or vice versa) produces $I_{turn} = 0$.

**Lateral Velocity Toward Threat (Direction-Aware):**

The ego's instantaneous lateral velocity component is derived from its yaw rate:

$$ v_{lat,e} = v_e \cdot \sin(\dot{\theta}_e \cdot \Delta t) $$

This represents the rate at which the ego vehicle is drifting sideways due to steering input. For small $\dot{\theta}_e \cdot \Delta t$, this approximates $v_e \cdot \dot{\theta}_e \cdot \Delta t$.

To prevent false intent escalation when the ego drifts **away** from the threat, only the component **toward** the threat side is used:

$$ v_{lat,toward} = \begin{cases} \max(0,\; +v_{lat,e}) & \text{if } \text{side}(V_t) = \text{LEFT} \quad \text{(left turn} \to \dot{\theta}_e > 0 \to v_{lat,e} > 0\text{)} \\ \max(0,\; -v_{lat,e}) & \text{if } \text{side}(V_t) = \text{RIGHT} \quad \text{(right turn} \to \dot{\theta}_e < 0 \to v_{lat,e} < 0\text{)} \end{cases} $$

> **Sign Rationale:** In this model's convention, counterclockwise (left turn) gives $\dot{\theta}_e > 0$ and thus $v_{lat,e} > 0$. Clockwise (right turn) gives $\dot{\theta}_e < 0$ and thus $v_{lat,e} < 0$. The $\max(0, \cdot)$ with appropriate sign ensures only drift **toward** the threat side produces a positive contribution.

**Intent Risk:**
$$ R_{intent} = w_{sig} \cdot I_{turn} + w_{lat} \cdot \min\!\left(1,\; \frac{v_{lat,toward}}{v_{lat,max}}\right) $$

| Parameter | Value | Justification |
|-----------|-------|---------------|
| $w_{sig}$ | 0.4 | Turn signal is a strong intent indicator |
| $w_{lat}$ | 0.6 | Actual lateral drift is an even stronger indicator |
| $v_{lat,max}$ | 1.0 m/s | Typical lane change (3.5 m over 3–5 s ≈ 0.7–1.2 m/s) |

Since $w_{sig} + w_{lat} = 1.0$ and each term is in $[0, 1]$, $R_{intent} \in [0, 1]$ is guaranteed.

> **SUMO Note:** Turn signal state is accessible via `traci.vehicle.getSignals()`. Bit 0 = right blinker, Bit 1 = left blinker. For lateral velocity, the **primary method** is the yaw-rate-based formula above. As a verification alternative, `traci.vehicle.getLateralLanePosition()` differential between consecutive timesteps can be used, but the yaw-rate method takes precedence as it is available in both SUMO and real-world deployments.

---

## 6. Collision Risk Index (CRI)

The final CRI combines the probabilistic presence, physical risk components, and communication reliability into a single score in $[0, 1]$. This is computed **per target vehicle** and then assigned to the appropriate side (left/right) per Section 3.4.

$$ CRI_{final}(V_t) = P(V_t \in Z_{bs}) \times \left( \alpha \cdot R_{decel} + \beta \cdot R_{ttc} + \gamma \cdot R_{intent} \right) \times (1 + \epsilon \cdot PLR) $$

**Weight Definitions and Justification:**

| Parameter | V2.4 Default | V3.0 Optimized | Optimization Method |
|-----------|-------------|----------------|---------------------|
| $\alpha$ ($R_{decel}$) | 0.35 | 0.15 | Grid search (run optimize_weights.py to update) |
| $\beta$ ($R_{ttc}$)   | 0.45 | 0.80 | Grid search, lateral-aware near-miss proxy |
| $\gamma$ ($R_{intent}$) | 0.20 | 0.05 | Grid search |
| $\epsilon$ | 0.30 | 0.30 | PLR penalty |

*Constraint:* $\alpha + \beta + \gamma = 1.0$, ensuring the weighted risk sum is in $[0, 1]$ before the PLR modifier.

*Note:* Weights were selected based on relative collision causation priority and are subject to empirical calibration using SUMO simulation data. The PLR modifier $(1 + \epsilon \cdot PLR)$ scales the risk upward under degraded communication (maximum amplification at $PLR = 1.0$ is $1.30$).

**Boundary Behavior Justification:** The multiplicative structure ensures that if $P(V_t \in Z_{bs}) = 0$ (the target is definitively outside the blind spot zone), then $CRI_{final} = 0$ regardless of the risk component values. This is physically correct — a vehicle that is not in the blind spot poses no blind-spot-specific collision risk. The probabilistic GPS treatment in Section 4.1 ensures that $P$ transitions smoothly (not as a hard binary step) across the zone boundary, with the transition width governed by $\sigma_{gps}$. At $\sigma_{gps} = 1.5$ m, the transition band is approximately $\pm 3$ m (3σ) around each boundary, providing a sufficiently smooth gradient.

**Final Clamping:**
$$ CRI_{final} = \text{clamp}(CRI_{final},\; 0,\; 1) $$

---

## 7. Alert Classification and Intervention Protocol

### 7.1 Alert Threshold Definitions

Alert levels are computed **independently for each side** (left and right), using the respective $CRI_{left}$ and $CRI_{right}$ from Section 3.4. For a given side's CRI value:

$$ \text{Alert Level} = \begin{cases} \textbf{CRITICAL} & CRI_{side} \geq \theta_3 \\ \textbf{WARNING} & \theta_2 \leq CRI_{side} < \theta_3 \\ \textbf{CAUTION} & \theta_1 \leq CRI_{side} < \theta_2 \\ \textbf{SAFE} & CRI_{side} < \theta_1 \end{cases} $$

Where $CRI_{side} \in \{CRI_{left},\; CRI_{right}\}$.

| Level | Threshold | CRI Range | Driver Feedback |
|-------|-----------|-----------|-----------------|
| **SAFE** | — | $[0, 0.30)$ | No alert; lane is clear |
| **CAUTION** | $\theta_1 = 0.30$ | $[0.30, 0.60)$ | Visual indicator on side mirror (amber LED / icon) |
| **WARNING** | $\theta_2 = 0.60$ | $[0.60, 0.80)$ | Visual + audible alert (beep pattern) |
| **CRITICAL** | $\theta_3 = 0.80$ | $[0.80, 1.00]$ | Visual + audible + haptic/steering torque intervention |

> **Design Rationale:** The CRITICAL threshold is set at 0.80 (not lower) because false positives at this level trigger steering intervention, which itself can be dangerous. A higher bar for intervention reduces the risk of the safety system causing an accident.

### 7.2 Alert Hysteresis (Flicker Prevention)

To prevent rapid oscillation between alert levels at boundary CRI values, a hysteresis band $\delta_h$ is applied **independently to each side** (left and right). Each side maintains its own upgrade counter.

*   **Upgrade:** Alert level for a given side increases when $CRI_{side} \geq \theta_k$ for $N_h$ consecutive timesteps.
*   **Downgrade:** Alert level for a given side decreases when $CRI_{side} < \theta_k - \delta_h$.

Where $CRI_{side} \in \{CRI_{left},\; CRI_{right}\}$, each with its own independent counter state.

**Parameters:**
*   $\delta_h = 0.05$ (hysteresis band width)
*   $N_h = 3$ timesteps (at 10 Hz, this is 0.3 seconds — prevents flicker without introducing dangerous delay)

---

## 8. Complete System Parameters Reference

All parameters used in this model, in one consolidated table:

| Symbol | Value | Unit | Description | Section |
|--------|-------|------|-------------|---------|
| $f_{BSM}$ | 10 | Hz | BSM broadcast frequency | §1 |
| $\Delta t$ | 0.1 | s | BSM broadcast interval | §1 |
| $R_{comm}$ | 300 | m | Maximum V2V communication range | §1 |
| $g$ | 9.81 | m/s² | Gravitational acceleration | §5.1 |
| $W_{lane}$ | 3.5 (default) | m | Standard lane width (configurable) | §3.3 |
| $L_{base}$ | 4.5 | m | Minimum blind spot length | §3.1 |
| $v_{min}$ | 2.0 | m/s | Minimum velocity for BSD scaling | §3.1 |
| $v_{max}$ | 40.0 | m/s | Maximum velocity for BSD scaling | §3.1 |
| $\lambda_{scale}$ | 12.0 | m | Blind spot length scaling factor | §3.1 |
| $\epsilon_{yaw}$ | $10^{-3}$ | rad/s | Straight-line yaw rate threshold | §3.2 |
| $\epsilon_v$ | 0.1 | m/s | Minimum velocity for curvature | §3.2 |
| $\sigma_{gps}$ | 1.5 (default) | m | GPS position uncertainty — 1σ CEP (configurable per tier) | §4.1 |
| $\tau_{base}$ | 0.005 (DSRC) / 0.015 (C-V2X) | s | Base communication latency (protocol-dependent) | §4.2 |
| $N_{plr}$ | 10 | packets | PLR sliding window size (1.0 s at 10 Hz) | §4.3 |
| $T_{react}$ | 1.2 | s | Human driver reaction time (P85) | §5.1 |
| $k_{brake}$ | 1.50 | — | Deceleration risk decay constant | §5.1 |
| $C_d$ | 0.30 (sedan) | — | Aerodynamic drag coefficient | §5.1 |
| $A_f$ | 2.2 (sedan) | m² | Vehicle frontal area | §5.1 |
| $\rho_{air}$ | 1.225 | kg/m³ | Air density at sea level | §5.1 |
| $\epsilon_a$ | $10^{-3}$ | m/s² | Relative acceleration threshold | §5.2 |
| $TTC_{critical}$ | 4.0 | s | TTC imminent collision threshold | §5.2 |
| $TTC_{max}$ | 8.0 | s | TTC maximum evaluation horizon | §5.2 |
| $w_{sig}$ | 0.4 | — | Turn signal intent weight | §5.3 |
| $w_{lat}$ | 0.6 | — | Lateral drift intent weight | §5.3 |
| $v_{lat,max}$ | 1.0 | m/s | Maximum expected lateral velocity | §5.3 |
| $\alpha$ | 0.15 | — | CRI weight: deceleration risk | §6 |
| $\beta$ | 0.80 | — | CRI weight: TTC risk | §6 |
| $\gamma$ | 0.05 | — | CRI weight: intent risk | §6 |
| $\epsilon$ | 0.30 | — | CRI weight: PLR penalty | §6 |
| $\theta_1$ | 0.30 | — | Alert threshold: CAUTION | §7.1 |
| $\theta_2$ | 0.60 | — | Alert threshold: WARNING | §7.1 |
| $\theta_3$ | 0.80 | — | Alert threshold: CRITICAL | §7.1 |
| $\delta_h$ | 0.05 | — | Alert hysteresis band | §7.2 |
| $N_h$ | 3 | timesteps | Alert upgrade persistence count | §7.2 |

---

## 9. Assumptions, Scope, and Limitations

### 9.1 Core Assumptions
1.  All vehicles in the network are equipped with V2V communication hardware and broadcast BSMs at 10 Hz conforming to SAE J2735.
2.  GPS/GNSS provides position with accuracy characterized by $\sigma_{gps}$. The default value of $1.5$ m represents standard consumer-grade GNSS. RTK-GPS ($\sigma_{gps} = 0.5$ m) improves performance but is not assumed. Degraded GPS (urban canyons, tunnels) is only partially addressed via dead reckoning; extended GNSS outage is outside scope.
3.  The road surface friction coefficient $\mu$ is assumed known or estimable in real-time via ABS/TCS wheel slip ratio sensors. In SUMO, $\mu$ is read from the network definition file (`friction` attribute per edge/lane) and treated as a known constant per road segment.
4.  Vehicles are modeled as axis-aligned bounding boxes in the ego-centric frame. Complex vehicle geometries (e.g., articulated trucks) are approximated.
5.  The CA-CYR dead reckoning model assumes constant acceleration and constant yaw rate over the prediction horizon $\tau_{eff}$. This is valid for $\tau_{eff} \leq 0.5$ s. Beyond this, the target state should be flagged as stale (see Section 4.2).
6.  The GPS antenna position is assumed to coincide with the vehicle's geometric center. The lever-arm offset (typically 1–2 m) is within $\sigma_{gps}$ and is absorbed by the probabilistic treatment (see Section 2).
7.  **Vehicle mass ($M_t$):** The standard SAE J2735 BSM does not include vehicle mass. In this model, $M_t$ is estimated from the vehicle type classification field available in BSM Part II (e.g., passenger car ≈ 1500 kg, SUV ≈ 2200 kg, heavy truck ≈ 15000 kg). **Fallback:** When BSM Part II data is absent (which is common in early deployments), a default mass of $M_{default} = 1800$ kg (approximate average passenger vehicle) is used. For the Ego vehicle, $M_e$ is known from the local OBD-II / CAN bus. In SUMO, mass is directly accessible via `traci.vehicle.getParameter()`.

### 9.2 Scope Statement
This model is a **pure V2V-based** blind spot detection system. It relies exclusively on data received via V2V BSM broadcasts. Real-world ADAS/AV systems typically fuse V2V data with onboard sensors (radar, camera, LiDAR, ultrasonic). Sensor fusion architectures are outside the scope of this model but represent a natural extension. The V2V-only approach is valid for both simulation evaluation and as the V2V processing module within a larger sensor-fused ADAS pipeline.

### 9.3 Known Limitations
1.  **Non-V2V-equipped vehicles** (legacy vehicles, pedestrians, cyclists) are invisible to this system.
2.  **Multi-lane scenarios** (3+ lanes): The lateral boundary checks the immediately adjacent lane only. Extension to multi-lane blindspot would require expanding $W_{lane}$ to $n \cdot W_{lane}$.
3.  **Elevation changes** (hills, ramps): The model operates in a 2D horizontal plane. Significant grade differences may cause false positives/negatives in $y_{rel}$.
4.  **Communication security:** The model assumes BSM data is authentic. Spoofing and misbehavior detection are outside scope.
5.  **NLOS (Non-Line-Of-Sight) propagation:** DSRC/C-V2X signals can be blocked or attenuated by large vehicles, buildings, and terrain features. NLOS conditions degrade communication reliability (increasing $PLR$ and $\tau_{eff}$) and are a primary failure mode of real DSRC systems. This model accounts for the *effects* of NLOS via the PLR penalty term in the CRI, but does not explicitly model NLOS geometry or signal propagation.
6.  **Ego-only curvature correction:** The clothoid correction in Section 3.2 compensates only for the Ego vehicle's own trajectory curvature. The Target vehicle's independent curvature is not modeled. This approximation is valid when both vehicles follow the same road curve, but accuracy degrades in diverging-trajectory scenarios (e.g., roundabouts, exit ramps).
7.  **Aerodynamic drag approximation:** The drag term in $a_{max,t}$ uses vehicle-class-typical values for $C_d$ and $A_f$. Per-vehicle aerodynamic data is not available via BSM. At typical urban/highway speeds ($\leq 120$ km/h), the drag contribution to deceleration is $< 5\%$ of total braking force, making this approximation acceptable.
8.  **Intent detection is Ego-only:** $R_{intent}$ captures only the **Ego vehicle's** lane-change intent (turn signal, lateral drift). A target vehicle drifting into the Ego's lane would not be captured by $R_{intent}$. However, this scenario IS captured by $R_{ttc}$ (closing distance) and $R_{decel}$ (stopping distance), so the overall CRI still responds to target-side lateral intrusions — just via the physics components rather than the intent component.
9.  **[V3.0 RESOLVED]** Lateral sideswipe risk is now captured by the Lateral TTC section. The combined $R_{ttc}$ = max($R_{ttc,lon}$, $R_{ttc,lat}$) accounts for both longitudinal closure and lateral convergence of adjacent-lane vehicles. Remaining open limitation: W_gap assumes constant 1-lane separation; in multi-lane merges this may underestimate lateral gap.

> **Implementation Note (Dual Counter Requirement):** Each target vehicle requires two separate counters maintained per-side: (1) $k_{lost}$ — consecutive dropped packets for dead reckoning $\tau_{eff}$ computation, and (2) a sliding window buffer of $N_{plr} = 10$ reception flags for PLR computation. These track different aspects of communication quality and must not be conflated.


---

## 10. Experimental Validation

The V3.0 model is validated through four complementary experimental methodologies, each 
implemented in the accompanying Python scripts and designed to run on SUMO simulation data.

### 10.1 AI Label Generation (Ground Truth for ML Validation)

The XGBoost hybrid predictor is trained on labels generated by a **kinematic near-miss proxy** 
that is deliberately independent of the physics model's intermediate outputs ($R_{ttc}$, $R_{decel}$):

$$
y_{true} = \begin{cases}
  1 & \text{if } \texttt{ground\_truth\_collision} = 1 \text{ (SUMO bounding-box collision)}\\
  1 & \text{if } gap < 2.0\text{m} \text{ OR } TTC_proxy < 1.5 s \text{ (near-miss)}\\
  0 & \text{otherwise}
\end{cases}
$$

where $TTC\_proxy = gap / \max(v_{rel}, 0.001)$ is computed solely from raw BSM fields. 
*(Note: As of V3.0, this ground truth logic is centralized in `bsd_utils.py` to guarantee identical evaluation across all testing scripts).*

**Label mapping for multi-class training:**

| Label | Class | Condition |
|-------|-------|-----------|
| 3 | CRITICAL | $gap < 2.0$ m OR $TTC_proxy < 1.5$ s |
| 2 | WARNING  | $gap < 5.0$ m OR $TTC_proxy < 3.0$ s |
| 1 | CAUTION  | $gap < 8.0$ m AND $TTC_proxy < 5.0$ s |
| 0 | SAFE     | None of the above |

### 10.2 ROC Curve Comparison (4 Systems)

The ROC evaluation (`evaluate_system.py`) compares four systems on the same ground truth:

| System | Description | Score |
|--------|-------------|-------|
| Mathematical Model (V3.0) | CRI = max(cri_left, cri_right) | Continuous [0,1] |
| AI Hybrid Predictor | XGBoost critical probability | Continuous [0,1] |
| TTC Kinematic Baseline | TTC-threshold alert (WARNING/CRITICAL) | Ordinal {0, 0.5, 1.0} |
| Static Box Baseline | Fixed 3.5m×8.0m geometric zone | Ordinal {0, 0.5, 1.0} |

The TTC Kinematic Baseline uses: CRITICAL if $TTC_{lon} < 1.5$ s, WARNING if $TTC_{lon} < 2.5$ s.
The Static Box Baseline triggers WARNING if target is within $\pm 3.5$ m lateral and $-8.0$ to $+L_{ego}/2$ m longitudinal.

### 10.3 Ablation Study (N=5 Seeds)

The ablation study (`ablation_study.py`) evaluates 5 configurations across N=5 independent 
SUMO random seeds (42–46), reporting mean ± std F1:

| Config | α | β | γ | Lateral TTC | Purpose |
|--------|---|---|---|-------------|---------|
| A1 | 1.0 | 0.0 | 0.0 | OFF | Decel-only baseline |
| A2 | 0.5 | 0.5 | 0.0 | OFF | Decel + TTC, no intent |
| A3 | 0.35 | 0.45 | 0.20 | OFF | V2.0 weights, no lateral TTC |
| A4 | 0.35 | 0.45 | 0.20 | ON | V2.0 weights + lateral TTC |
| A5 | 0.15 | 0.80 | 0.05 | ON | V3.0 optimized weights (this model) |

### 10.4 Sensitivity Analysis

The sensitivity analysis (`sensitivity_analysis.py`) sweeps four parameters while holding all 
others at their V3.0 defaults, measuring F1 score degradation:

| Parameter | Sweep Range | V3.0 Default | Measures |
|-----------|-------------|--------------|---------|
| $\sigma_{GPS}$ | 0.5 – 3.0 m | 1.5 m | Robustness to GPS degradation |
| $PLR_{g2b}$ | 0.01 – 0.20 | 0.05 | Robustness to V2V channel loss |
| $TTC_{crit}$ | 2.0 – 8.0 s | 4.0 s | Sensitivity to TTC horizon |
| $\theta_3$ | 0.70 – 0.85 | 0.80 | Sensitivity to CRITICAL threshold |

### 10.5 Multi-Seed Statistical Validation

`run_multi_seed.py` runs the full system across 5 independent seeds (10, 20, 30, 40, 50) and 
reports mean ± std F1 and AUC for the mathematical model, providing confidence bounds on 
the reported performance metrics for IEEE submission.
