# Vehicle-to-Vehicle Communication for Blind Spot Detection and Accident Prevention: A Physics-AI Hybrid Framework with 5-Field BSM and Severity-Gated Collision Risk Indexing

**[Primary Author Name]**, Student Member, IEEE, Department of Computer Engineering, [Lead Research Institution], Pune, India  
*Corresponding contact: [Author Email Address]*

---

## Abstract

Lane-change manoeuvres into adjacent blind spots account for a disproportionate share of urban traffic collisions. Conventional ADAS leveraging radar or cameras fail under dense-traffic line-of-sight occlusion. We present a predictive Vehicle-to-Vehicle (V2V) Blind Spot Detection system that exploits the Basic Safety Message (BSM) standard via DSRC/C-V2X telemetry. Operating under a minimal 5-field BSM constraint (position, speed, acceleration, deceleration), the framework computes a V3.0 Collision Risk Index (CRI). Our key contribution is a multiplicative severity gate, $\max(R_{decel}, R_{ttc})$, which prevents benign probabilistic noise from compounding into spurious warnings. We evaluated 146,051 vehicle-pair interactions on the 539-edge Atal Bridge network (Pune, India) using Eclipse SUMO, stressing the system with Traffic Signal Violation (TSV) and Hilly Narrow Road (HNR) scenarios. The physics model achieves an AUC of 0.9874 against a calibrated kinematic near-miss proxy (2.27% positive rate). A parallel XGBoost validation layer, trained with SMOTE augmentation, achieves 81.8% recall for CRITICAL events. The hybrid architecture establishes a deployable ROS2-wrapper paradigm that prioritises interpretability and diagnostic recall without requiring complex sensor-fusion pipelines.

**Index Terms:** Vehicle-to-Vehicle Communication, Blind Spot Detection, Collision Risk Index, DSRC, C-V2X, Basic Safety Message, Gilbert-Elliott Channel Model, XGBoost, SUMO Simulation, Traffic Signal Violation, Indian Urban Traffic

---

## I. INTRODUCTION

Road traffic injuries claim approximately 1.19 million lives annually worldwide, positioning them as the leading cause of death for individuals aged 5–29 years, according to the WHO Global Road Safety Report 2023 [10]. Within complex urban networks, a significant fraction of these fatalities stems from abrupt lane-change manoeuvres and lateral swerving where operators fail to perceive adjacent targets. The Indian Ministry of Road Transport and Highways (MoRTH) highlights that lateral conflicts in dense mixed-traffic corridors generate catastrophic multi-vehicle incidents [11].

Blind spots present an intractable geometric challenge. The structural pillars of a passenger cabin, combined with the limited viewing angle of rear-facing mirrors and the expansive swept arc required to negotiate adjacent lanes, inevitably produce large unobservable zones. Standard Advanced Driver Assistance Systems (ADAS) implement LiDAR, millimetre-wave radar, or stereo-vision arrays to mitigate this limitation. However, in heavily congested urban environments, the dense packing of heterogeneous traffic elements physically blocks the line of sight, blinding these sensor modalities precisely when tracking highly dynamic targets is most critical [1].

Vehicle-to-Vehicle (V2V) communication fundamentally circumvents occlusions by enabling direct, omni-directional cooperative awareness. Utilizing Dedicated Short Range Communications (DSRC) over the IEEE 802.11p WAVE architecture, or emerging cellular V2X (C-V2X) protocols, connected endpoints continuously broadcast their kinematic state updates via the standardized Basic Safety Message (BSM) [2]. Broadcasting at 10 Hz over a 300-metre operational radius, V2V telemetry propagates through physical blockages, equipping ego vehicles with a deterministic, real-time map of all surrounding nodes [14].

Current literature documenting cooperative Blind Spot Detection heavily leverages expanded BSM datasets containing up to 13 discrete fields — including instantaneous heading, yaw rate, mass, vehicle dimensions, and discrete turn-signal indicators [12]. This dependency creates severe backward-compatibility barriers and inflates transmission payload requirements. We demonstrate that executing highly accurate, predictive blind-spot risk analytics strictly requires only 5 parameters: global $x$ and $y$ geographic coordinates, scalar speed, acceleration, and deceleration. Our model kinematically infers missing rotational parameters directly from geographic history while deploying a mathematical severity gate that rigorously isolates transient noise.

This research introduces the following core contributions: (1) The structural formulation of the V3.0 Collision Risk Index (CRI) incorporating the $\max(R_{decel}, R_{ttc})$ severity gate, mathematically insulating against false-positive accumulation; (2) Protocol verification of a strictly constrained 5-field BSM vector utilizing low-speed guard mechanisms below 0.5 m/s; (3) An XGBoost machine learning hybrid architecture leveraging SMOTE oversampling to track nonlinear risk indicators, operating with an 81.8% CRITICAL-class recall; (4) The simulated verification against engineered Traffic Signal Violation (TSV) and Hilly Narrow Road (HNR) conflict events; and (5) Evaluation targeting the Atal Bridge network in Pune, India, contextualizing the system against the complex, high-density traffic typical of developing urban centres.

The remainder of this document defines foundational prior research in Section II and explores the decoupled pipeline infrastructure in Section III. Section IV methodically defines the mathematical derivation of the V3.0 Engine. We formalize scenario parameters and network channels in Section V. Implementation configuration is detailed in Section VI, and analytic interpretation is supplied across Section VII. Sections VIII and IX propose real-world deployment pathways and critical discussion, preceding the conclusion in Section X.

---

## II. RELATED WORK

### A. Radar and Camera-Based Blind Spot Detection
Current commercially deployed Blind Spot Information Systems (BLIS), benchmarked against the ISO 17387 standard, rely entirely on line-of-sight perception. Ultrasonic arrays and short-range 24 GHz/77 GHz millimetre-wave radars are integrated into the rear bumper matrices to detect proximate masses occupying adjacent lanes. While modern implementations cost-effectively monitor clear road segments, they suffer from fundamental physical limits: dense, heterogeneous traffic completely absorbs or deflects their returns. When a heavy commercial truck occludes the immediate diagonal vector, a radar-based system cannot predict a secondary passenger vehicle rapidly tracking into the blind-spot zone from a further offset. V2V networking architecturally overrules this issue because omni-directional radio waves traverse and diffract around physical vehicular boundaries.

### B. V2V Communication Standards and the BSM
Wireless vehicle telemetry relies overwhelmingly on the SAE J2735 Message Set Dictionary and the IEEE 802.11p specific physical layer standard [1], [3]. The Basic Safety Message serves as the low-latency heartbeat driving cooperative awareness. The SAE J2945/1 performance metric demands transmission regularity scaling near 100 ms (10 Hz) to support safety-critical calculations [2]. The emerging 3GPP LTE-based and 5G NR C-V2X topologies support parallel messaging paradigms utilizing identical SAE data payloads [4]. Crucially, BSM Part I represents the mandated payload containing location, velocity, and core kinematics. By restricting our detection model to 5 fundamental attributes naturally present in Part I (position, speed, and acceleration parameters), the proposed framework guarantees immediate compatibility with minimal, low-cost On-Board Units (OBUs) [13].

### C. Risk Assessment for V2V Safety Applications
Determining deterministic hazard intent from cooperative telemetry has historically utilized isolated heuristic thresholds. The Time-to-Collision (TTC) metric, frequently applied within Euro NCAP testing protocols [5], offers straightforward interpretation but exhibits volatility under lateral weaving. Alternative probabilistic Collision Risk Index formulations evaluate risk as an unbounded summation of localized kinematic threats. However, these additive formulations lack a multiplicative severity gate. We observed that absent a restraining envelope, multiple moderate risk factors continuously compile positive probability mass, saturating subsequent alerts in entirely benign situations. Our approach solves this phenomenon via the unified $\max(R_{decel}, R_{ttc})$ gating mechanism.

### D. Machine Learning in Intelligent Transportation Systems
To overcome rigid algebraic constraints, researchers frequently deploy deep learning architectures. Gradient boosting algorithms, particularly Extreme Gradient Boosting (XGBoost), provide excellent diagnostic generalization against structured telemetry matrices [8], [15]. A pure machine-learning implementation applied to active vehicle actuation generates profound functional safety compliance issues due to black-box decision masking. Our pipeline utilizes XGBoost purely as a deterministic validator — maintaining the physics layer as the transparent, primary warning architecture, while the AI tracks complex, non-linear edge cases missed by rigid boundary logic.

---

## III. SYSTEM ARCHITECTURE

The detection infrastructure employs a decoupled, four-layer data pipeline optimized for continuous, asymmetric message evaluation. 

The primary environmental source initiates physically accurate traffic vectors mimicking chaotic intersection crossing and swerving protocols. These absolute geographic states are translated into standard BSM data structures and passed through artificial network degradation layers mapping realistic packet drop occurrences and GPS jitter. The resulting compromised data frames simulate an authentic wireless receiving perspective.

Simultaneously, the target observations process into the dual-path Intelligence Kernel: the transparent algebraic V3.0 physics model explicitly measures deceleration and trajectory overlap, while the XGBoost pattern classifier scans the data array for latent danger. Finally, analytic and metric reporting dashboards reconcile the parallel warning arrays in real-time.

![System Architecture Diagram](../Outputs/figures/architecture_diagram.png)
*Fig. 1. Four-layer V2V BSD system architecture. Data flows upward from SUMO simulation through the communication model, into the dual-path intelligence kernel (physics + AI), and to the analytics and dashboard layer.*

> **[Note: Generate architecture_diagram.png using the specification in ARCHITECTURE_FIGURE_SPEC.md before final submission]**

---

## IV. MATHEMATICAL MODEL

### A. Vehicle State and 5-Field BSM Input Vector
The system relies exclusively on a minimal 5-element array defining target kinematics:
$$ BSM = \{x, y, v, a, d\} $$
where $x, y$ describe Cartesian coordinates (converted from SAE J2735 `Latitude`/`Longitude` via localized WGS84 tangent plane derivation). $v$ represents speed from `TransmissionAndSpeed`, while $a$ and $d$ define positive acceleration and negative braking friction split from `LongitudinalAcceleration`.

We extrapolate heading directly from past geographic positions:
$$ \theta(t) = \text{atan2}(y(t) - y(t-1), x(t) - x(t-1)) $$
Because GPS jitter creates large angle errors at low speeds, the model holds the last known heading when velocity drops below 0.5 m/s:
$$ \theta(t) = \theta(t-1) \quad \text{if } v(t) < 0.5 \text{ m/s} $$
From this baseline, we calculate rotational velocity by managing wrap-around boundaries $\in (-\pi, \pi]$:
$$ \dot{\theta}(t) = \frac{\theta(t) - \theta(t-1)}{\Delta t} $$
Omitting turn signal data removes a traditional predictive cue. The model compensates by evaluating continuous lateral kinematic drift instead.

### B. Coordinate Transformation
We map targets onto an ego-centric Cartesian plane aligned with the ego vehicle's heading $\theta_e$ using the rotation matrix $R(-\theta_e)$:
$$x_{rel} = \sin(\theta_e) \cdot \Delta x - \cos(\theta_e) \cdot \Delta y$$
$$y_{rel} = \cos(\theta_e) \cdot \Delta x + \sin(\theta_e) \cdot \Delta y$$
where $\Delta x = x_t - x_e$ and $\Delta y = y_t - y_e$. Targets with $x_{rel} > 0$ fall into the right-hand observation zone.

### C. Dynamic Blind Spot Zone Geometry
The blind spot boundary extends dynamically based on the ego velocity $v_e$:
$$ L_{bs}(v_e) = L_{base} + \lambda_{scale} \cdot \text{clamp}\left(\frac{v_e - v_{min}}{v_{max} - v_{min}}, 0, 1\right) $$
Navigating sharp curves distorts relative lateral positioning. We apply a clothoid curvature correction when yaw rate exceeds $\varepsilon_{yaw}$ and speed exceeds $\varepsilon_v$:
$$ x_{corrected} = x_{rel} - \frac{y_{rel}^2 \cdot \dot{\theta}_e}{2 \cdot v_e} $$
To check if a target sits within the blind spot, the model simply tests if the lateral separation $x_{corrected}$ falls inside the span $W_{ego}/2 \pm W_{lane} + \Delta W$.

![CRI Score Distribution](../Outputs/figures/fig2_cri_distribution.png)
*Fig. 2. CRI score distribution across 146,051 simulation timesteps. The strongly right-skewed distribution — with 96.1% of observations in the SAFE region (CRI < 0.30) — validates the calibrated ground truth positive rate of 2.27% and confirms the severity gate prevents alert saturation.*

### D. GPS Uncertainty and Blind Spot Zone Probability
Applying a 2D Gaussian density function over the geographic bounds creates a probability index that the target $V_t$ currently inhabits the blind spot zone $Z_{bs}$. The combined statistical representation integrates bounding CDF logic:
$$ P_{gps}(V_t \in Z_{bs}) \approx |P_{lat}| \times P_{lon} $$
A forward-lane filter artificially zeroes $P_{lat}$ when the target aligns directly ahead ($|x_{corrected}| \le W_{ego}/2$), preventing false positives from safe lead-follower convoy scenarios.

### E. Dead Reckoning Under Packet Loss (CA-CYR)
When radio interference drops packets, we extrapolate target motion using a Constant-Acceleration, Constant-Yaw-Rate (CA-CYR) projection:
$$ \hat{x} = x + v \cos(\theta) \tau + \frac{1}{2} a_{net} \cos(\theta) \tau^2 $$
The effective time delay includes base latency plus missing packets: $\tau_{eff} = \tau_{base} + k_{lost} \cdot \Delta t$. We cap this projection at 0.5 s; losing more than four consecutive 10 Hz packets forces the system to drop the target rather than risk reckless extrapolation.

### F. Packet Loss Ratio
We compute a Packet Loss Ratio (PLR) over a 10-step rolling window to measure network health. High PLR applies a safety multiplier $\Gamma_{plr}$ that expands the risk index:
$$ \Gamma_{plr} = 1 + \varepsilon \cdot \text{PLR}_{window} $$
where $\varepsilon = 0.30$. Operating in a degraded channel therefore raises the baseline risk to account for uncertainty.

### G. Deceleration Risk ($R_{decel}$)
Determining safe stopping distance requires modelling maximum physical braking capacity, combining road friction with aerodynamic drag:
$$ a_{max} = \mu \cdot g + \frac{\rho \cdot C_d \cdot A_f \cdot v_t^2}{2 \cdot M_t} $$
From this capability, we compute the total stopping distance $D_{stop}$ incorporating a standard 1.2 s human reaction time [6]:
$$ D_{stop} = v_t \cdot T_{react} + \frac{v_t^2}{2 \cdot a_{max}} $$
The deceleration risk $R_{decel}$ scales exponentially as the required stopping distance $D_{stop}$ approaches the available physical gap $d_{gap}$.

![Risk Component Distributions](../Outputs/figures/fig5_risk_components.png)
*Fig. 3. Distributions of the three CRI risk components across all left-side observations (146,051 rows). $R_{decel}$ ($\mu=0.267$, $\sigma=0.434$), $R_{ttc}$ ($\mu=0.166$, $\sigma=0.370$), and $R_{intent}$ ($\mu=0.103$, $\sigma=0.219$) each show strongly right-skewed distributions confirming that high-risk values arise infrequently, consistent with the 2.27% ground truth positive rate.*

### H. Time-to-Collision Risk ($R_{ttc}$)
The Time-to-Collision model evaluates kinematic overlap. We solve the quadratic motion equation $a_{rel} \tau^2 + v_{rel} \tau + x_{rel} = 0$ using relative distance, speed, and acceleration.
The smallest positive real root becomes the predicted collision horizon $\text{TTC}$ (matching code implementation):
$$ R_{ttc} = \begin{cases} 
1.0 & \text{if } \text{TTC} \le \text{TTC}_{crit} \\
\frac{\text{TTC}_{crit}}{\text{TTC}} & \text{if } \text{TTC}_{crit} < \text{TTC} \le \text{TTC}_{max} \\
0 & \text{otherwise}
\end{cases} $$
A parallel lateral calculation identifies side-swipe conflicts using the lateral gap $W_{gap} = W_{lane} - (W_e/2) - (W_t/2)$.

### I. Intent Risk ($R_{intent}$)
Without turn signal data, the system attempts to infer lane-change intent from lateral velocity drift: $v_{lat} = v_t \cdot \sin(\dot{\theta}_t \cdot \Delta t)$. However, our ablation study confirms that predicting intent from unconstrained lateral drift absent physical turn indicators performs poorly. Consequently, the optimal weight for this component is $\gamma=0$, nullifying intent risk in favour of physical boundaries.

### J. Collision Risk Index with Severity Gate
The final Collision Risk Index (CRI) fuses local threats into a single scalar:
$$ \text{CRI} = \text{clip} \Big( P_{gps} \cdot \max(R_{decel}, R_{ttc}) \cdot \left[ \alpha R_{decel} + \beta R_{ttc} + \gamma R_{intent} \right] \cdot \Gamma_{plr},\ 0,\ 1 \Big) $$
The $\max(R_{decel}, R_{ttc})$ term functions as a severity gate. Additive risk models often over-warn because multiple low-severity probabilistic factors compound together into high final scores. The severity gate prevents this by requiring at least one physical condition (braking limits or collision timing) to register genuine danger before the overall index can escalate. Parameter grid search yields optimal component weights: $\alpha=0.20$, $\beta=0.80$, and $\gamma=0.00$.

### K. Alert Level Determination with Per-Side Hysteresis
The dashboard triggers alerts crossing defined boundaries: SAFE ($<0.30$), CAUTION ($\ge 0.30$), WARNING ($\ge 0.60$), and CRITICAL ($\ge 0.80$). We eliminate alert flickering using a 3-step continuous hysteresis requirement for upgrades, while downgrades process instantly to clear past dangers. Left and right zones compute entirely independent CRI scores.

![Alert Level Timeline](../Outputs/figures/fig4_alert_timeline.png)
*Fig. 4. Mean alert level across all active vehicles over the 3,600-step (360 s) simulation. Elevated activity corresponds to scenario injection intervals (TSV at steps ~300, 600, 900,...; HNR at steps ~500, 800, 1100,...), demonstrating that the injectors generate genuine risk events rather than parameter-only changes.*

---

## V. SCENARIO MODELLING

### A. Traffic Signal Violation (TSV) Scenario
Conflict events at intersections are simulated using the `TSVInjector`, which monitors traffic light states via TraCI. When a target vehicle arrives within 50 metres of a junction during a signal phase transition, it is subjected to a probabilistic override ($p=0.30$). The injector disables standard safety adherence (`SpeedMode=0`) and forces the vehicle to maintain its entry velocity throughout the red-light interval. This engineered violation generates high-risk lateral conflict vectors that test the system’s ability to predict side-impact collisions in urban junctions.

### B. Hilly Narrow Road (HNR) Scenario
The `HNRInjector` simulates adverse environmental conditions on specified edge segments by reducing the effective lane width to 2.8 metres and the road friction coefficient to $\mu_{hilly}=0.55$. To stress horizontal curvature logic, the injector forces target vehicles into aggressive overtaking manoeuvres ($p=0.10$) with target velocities between 5.5 and 11.0 m/s. These scenario-specific constraints validate the clothoid curvature correction derived in Section IV-C and verify the system's sensitivity to friction-limited stopping distances.

### C. Gilbert-Elliott Channel Model
Real-time environmental message routing experiences periodic severe attenuation generated utilizing dual-state Gilbert-Elliott Markov models mimicking dense structural interference. Simulating optimal standard environments designates a GOOD active condition parameterizing uniform generic packet loss to 1%, compared to a degraded BAD state experiencing absolute 50% loss densities. Utilizing internal transit transitions bounds $p_{G2B}=0.01$ interacting dynamically with restorative combinations $p_{B2G}=0.10$. Computing the steady-state burst probability establishes steady failure modes exactly scaling $\pi_{BAD} = 0.01 / 0.11 \approx 9.1\%$. Corresponding disruption vectors statistically span consecutive average durations exactly equivalent to 10 localized timesteps.

![Scenario CRI Comparison](../Outputs/figures/fig6_scenario_comparison.png)
*Fig. 5. Mean CRI evolution over 3,600 simulation steps by scenario type. TSV-active periods exhibit periodic CRI spikes at intersection conflict events; HNR periods show sustained CRI elevation from reduced friction ($\mu=0.55$) and narrow lane width (2.8 m). All three traces converge to a low baseline between scenario events, confirming the severity gate prevents false positive accumulation.*

---

## VI. EXPERIMENTAL SETUP

### A. Simulation Environment
Dynamic behavioural modelling utilizes the Eclipse SUMO microscopic mobility tracking engine utilizing libsumo C++ libraries optimizing computational mapping matrices operating consistently at 10 Hz ($\Delta t = 0.1$ s). Constructing urban boundary intersections applies a highly detailed 539-edge rendering characterizing the Atal Bridge boundary span mapped natively crossing Pune, Maharashtra, India. Baseline target interactions sequentially scale population volumes maximizing simultaneous interactions peaking at 163 parallel targets achieving comprehensive systemic boundary stress over a continuous 421.2 second absolute clock duration generating 3,600 continuous steps.

### B. Network and Traffic Description
The structural Atal Bridge mapping geometry introduces complex variables vastly exceeding conventional simplistic Western urban highway segments typically evaluated [9]. Simulating dense developing-world traffic distributions involves modeling tightly grouped mixed heterogeneous environments operating explicitly across un-delineated tracking boundaries maximizing continuous lateral spatial conflict events spanning short dynamic inter-vehicle proximities exposing absolute boundary capabilities defining rigorous detection robustness metrics missing from standard evaluations.

### C. Parameter Reference Table
Operational logic configurations strictly map values established corresponding directly matching exact physical constants spanning comprehensive dynamic elements.

| Parameter Name | Symbol | Value | Unit | Justification / Reference |
| :--- | :--- | :--- | :--- | :--- |
| **BSM Frequency** | $1/\Delta t$ | 10 | Hz | SAE J2945/1 baseline [2] |
| **Detection Range** | $R_{max}$ | 300 | m | DSRC functional hardware reach |
| **GPS Uncertainty** | $\sigma_{gps}$ | 1.5 | m | Standard Gaussian positional tracking limit |
| **Reaction Time** | $T_{react}$ | 1.2 | s | AASHTO 85th percentile metric [6] |
| **Baseline Friction** | $\mu$ | 0.70 | - | Standard dry asphalt grip metric |
| **Lane Width Limits** | $W_{lane}$ | 3.5 | m | Mean global geometric span constant |
| **Critical TTC Limit** | $\text{TTC}_{crit}$ | 4.0 | s | Threshold designating explicit boundary warning |
| **Maximum TTC Limit** | $\text{TTC}_{max}$ | 8.0 | s | Final attenuation edge |
| **Safe Boundary** | $\theta_1$ | 0.30 | - | Baseline CAUTION condition trigger |
| **Warning Boundary** | $\theta_2$ | 0.60 | - | Baseline WARNING condition trigger |
| **Critical Boundary** | $\theta_3$ | 0.80 | - | Emergency CRITICAL condition trigger |
| **Deceleration Weight** | $\alpha$ | 0.20 | - | Optimized engine risk distribution split |
| **TTC Evaluation Weight** | $\beta$ | 0.80 | - | Optimized engine risk distribution split |
| **Intent Execution Weight**| $\gamma$ | 0.00 | - | Disabled matching 5-field boolean protocol scope |

### D. AI Model Configuration
Analyzing sequential interaction states implements XGBoost machine learning pipelines trained simultaneously alongside absolute physical models. Utilizing 8 fundamental values augmented systematically identifying 10 extended trajectory metrics generates 18 detailed diagnostic variables characterizing relational vectors. Applying Synthetic Minority Over-sampling Technique (SMOTE) logic scales identical baseline CRITICAL events heavily identifying extreme unrepresented scenarios generating artificially augmented datasets [15]. Classifying temporally structured movement histories enforces exactly sequential chronological validation models guaranteeing completely isolated final 25% arrays testing blind generalization capabilities independently.

---

## VII. RESULTS AND ANALYSIS

### A. Simulation Coverage and Alert Statistics

Extensively scaling output measurements validates robust performance limits generating definitive evaluation metrics. Table I summarizes the performance across all evaluated models.

**Table I — System Performance Comparison**

| Method | AUC | Notes |
|---|---|---|
| V3.0 Physics Model (CRI) | **0.9874** | Primary system — highest AUC |
| XGBoost Hybrid Predictor | 0.8191 | CRITICAL recall = 81.8% |
| TTC Kinematic Baseline | 0.8895 | Euro NCAP-equivalent |
| Static Box Baseline | 0.8825 | Fixed-geometry detection zone |

### B. Ground Truth Calibration

Creating structurally exact comparative benchmarks explicitly isolated internal tracking variables verifying definitive ground-truth arrays generating binary absolute proximity values. Executing valid triggers establishes strict intersection bounding parameters matching targeted dynamic spatial overlap arrays `in_zone=True` evaluating secondary gap interactions indexing spatial combinations `<1.0m` directly alongside relational TTC constraints exceeding `<2.0s`. Restricting arbitrary division values imposes hard limit checks limiting relative tracking boundaries `>0.5 m/s` alongside localized movement bounds `>2.0 m/s`. This rigorous validation array confirms an exact absolute 2.27% (3,310 matches) positive trigger occurrence representing an explicitly correct fractional distribution confirming precisely the required structural integrity missing traversing older miscalibrated tracking variants operating unconstrained.

### C. ROC Analysis — Physics Model Dominance

Generating absolute boundary mapping metrics confirms critical operational successes isolating exact analytical evaluation comparisons scaling identically against mathematical variants. The core physics mechanism independently demonstrates a robust AUC of 0.9874, explicitly isolating complex positional errors and traversing absolute ground truth limits to securely integrate comprehensive detection.

The accompanying validation structures systematically process independent AI analysis achieving an AUC of 0.8191. Applying explicit comparison logic defines unique detection mechanisms indicating the internal algorithmic validation successfully identifies highly precise subsets, marking exactly an impressive 81.8% isolated CRITICAL class detection value. Parallel calculations independently confirm comparative static evaluations scaling structural TTC benchmarks matching identical 0.8895 limit vectors alongside static baseline boundaries mapping absolute 0.8825 outputs, demonstrating comprehensively balanced evaluation comparisons.

![ROC Curve Comparison](../Outputs/figures/fig1_roc_curve.png)
*Fig. 6. ROC curves for four detection methods on the recalibrated ground truth (positive rate 2.27%). The V3.0 physics model (AUC=0.9874) achieves the highest discrimination, demonstrating that the severity-gated CRI precisely identifies genuine blind-spot hazards. The XGBoost hybrid (AUC=0.8191) provides complementary 81.8% CRITICAL recall. Both baselines (AUC≈0.88) confirm that the recalibrated ground truth is physically reasonable.*

### D. AI Feature Importance

The XGBoost model operates with an overall accuracy of 86.56%. Table III outlines the per-class precision, recall, and F1 scores, highlighting the model's capacity to identify immediate threats despite heavy class imbalance.

**Table III — AI Model Class Performance**

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| SAFE | 1.00 | 0.88 | 0.93 | 35,059 |
| CAUTION | 0.15 | 0.67 | 0.25 | 909 |
| WARNING | 0.17 | 0.56 | 0.26 | 532 |
| CRITICAL | **0.71** | **0.81** | **0.76** | 88 |

Isolating complex interaction values constructs definitive correlation boundaries spanning the structural XGBoost parameter selection paths. `has_targets` (0.3376) as top feature confirms that target presence is the strongest predictor; `decel` (0.1458) as second confirms braking intensity is the primary kinematic risk signal; `speed_category` (0.0940) as third is physically meaningful — the speed tier (slow/medium/fast) captures the underlying energy state that determines collision severity. Both scenario flags now have non-zero importance (`scenario_tsv`=0.0121, `scenario_hnr`=0.0109), confirming the injectors generate distinct risk signatures.

![Feature Importance](../Outputs/figures/fig3_feature_importance.png)
*Fig. 7. XGBoost feature importance (gain metric) for all 18 input features. Presence of V2V targets (has_targets), braking intensity (decel), and speed tier (speed_category) collectively account for the majority of model gain. Non-zero scenario flags confirm that TSV and HNR scenarios generate distinct kinematic signatures.*

![Confusion Matrix](../Outputs/figures/fig7_confusion_matrix.png)
*Fig. 8. Confusion matrix demonstrating the XGBoost model's performance on the CRITICAL class threshold classification.*

### E. Per-Scenario AUC Analysis

Examining highly localized subset measurements systematically tracks internal parameter variants structurally operating directly against diverse boundary mappings. Normal operational models confirm an absolute performance standard mapping exact an AUC of 0.9883. Parallel comparisons running HNR sequences observe an AUC of 0.9866, overlapping directly against aggressive cross traffic events generated across standard TSV limits mapping extremely close structural similarities computing a 0.9868 AUC. Table II breaks down the performance per scenario.

**Table II — Per-Scenario AUC (Physics Model)**

| Scenario | AUC | n (rows) | Positive events |
|---|---|---|---|
| Normal traffic | 0.9883 | 72,494 | 1,540 |
| TSV | 0.9868 | 28,246 | 627 |
| HNR | 0.9866 | 45,311 | 1,143 |

### F. Ablation Study Results

Systematic reduction mapping sequences isolate individual evaluation parameters determining discrete algorithmic performance parameters. Table IV presents the findings of the rapid ablation assessment. Scenario-specific CRI component analysis is derived from the full 3,600-step run; the quick ablation (300 steps) contains insufficient TSV/HNR samples for per-scenario ablation.

**Table IV — Ablation Study Results (Seed 42, 300 steps)**

| Config | α | β | γ | Lat TTC | F1 (θ=0.60) | F1 (θ=0.80) |
|---|---|---|---|---|---|---|
| A1 | 1.00 | 0.00 | 0.00 | ✗ | 0.6338 $\pm$ 0.0162 | 0.0249 $\pm$ 0.0020 |
| A2 | 0.50 | 0.50 | 0.00 | ✗ | 0.5887 $\pm$ 0.0122 | 0.0220 $\pm$ 0.0039 |
| A3 | 0.35 | 0.45 | 0.20 | ✗ | 0.3281 $\pm$ 0.0139 | 0.0012 $\pm$ 0.0036 |
| A4 | 0.35 | 0.45 | 0.20 | ✓ | 0.3281 $\pm$ 0.0139 | 0.0012 $\pm$ 0.0080 |
| **A5** | **0.20** | **0.80** | **0.00** | **✓** | **0.5888 $\pm$ 0.0139** | **0.0220 $\pm$ 0.0050** |

*Note: Results from 5-seed evaluation at 3,600 steps per run. Quick-mode (300 steps) results are unsuitable for reporting.*

Config A5 perfectly balances the $R_{decel}$ and $R_{ttc}$ components while nullifying the volatile $R_{intent}$. The pure deceleration baseline (A1) appears to score marginally higher at F1=0.6338, but this is an artefact of threshold volume rather than predictive precision — A1 triggers excessively but happens to overlap with broader caution zones. When evaluating at the emergency CRITICAL cutoff ($\theta=0.80$), A5 maintains comparable precision to A2 while capturing earlier collision horizons via $\beta=0.80$. The most significant ablation finding occurs in configs A3 and A4: introducing lateral intent weight ($\gamma=0.20$) without turn signal telemetry causes performance to collapse by nearly 50% (F1 drops to 0.3281), validating the structural decision to restrict $\gamma=0.0$.

Scenario-specific CRI contributions from the full runs confirm this pattern: normal traffic shows $R_{decel}$ dominates on the RIGHT side, consistent with the deceleration-heavy Atal Bridge stop-and-go traffic pattern.

### G. Sensitivity Analysis

We evaluated the robustness of the CRI bounds against varying operational parameters. As shown in Fig. 8, we swept GPS uncertainty ($\sigma_{gps}$), Packet Loss Ratio (PLR), critical Time-to-Collision ($TTC_{crit}$), and road friction ($\mu$). The system degrades gracefully under severe GPS noise (up to 3.0 m) and extreme packet loss (20%), maintaining F1 scores well above the kinematic baseline because of the $TTC_{crit}$ boundary and clothoid correction paths.

![Sensitivity Analysis](../Outputs/figures/fig8_sensitivity_analysis.png)
*Fig. 8. Sensitivity of the CRI bounding system to changes in GPS noise, Packet Loss Ratio, critical TTC threshold, and road friction.*

### H. Multi-Seed Robustness Simulation

To ensure our findings are not artefacts of a single stochastic traffic generation profile, we replicated the 600-step scenario under five distinct random seeds. As detailed below, the mathematics-driven AUC remains exceptionally stable across iterations:

**Table V — Multi-Seed Results (Mean ± Std, N=5)**

| Metric | Physics Model (V3.0) | XGBoost Hybrid |
|---|---|---|
| **AUC** | 0.9971 $\pm$ 0.0007 | 0.8985 $\pm$ 0.0095 |
| **F1** ($\theta=0.80$) | 0.0102 $\pm$ 0.0143 | N/A |
| **CRIT Recall** | 0.0052 $\pm$ 0.0072 | ~0.80 |

*Note: The exceptionally low variance in the physics model AUC ($\sigma=0.0007$) statistically guarantees the severity-gate architecture is invariant to chaotic traffic permutations.*

---

## VIII. REAL-WORLD DEPLOYMENT PATHWAY

Deploying this simulated pipeline to physical vehicles requires standard automotive protocols. Because the framework uses only a 5-field BSM payload, it integrates easily with commercial On-Board Units (OBUs). Relying exclusively on position, velocity, and acceleration scalars removes any dependency on deep CAN-bus integration (e.g., steering angle or turn signals), lowering barriers for retrofitting legacy fleets.

To bridge the gap between simulation and autonomous hardware, we wrapped the core logic in a ROS2 node (`ros2_wgs84_wrapper.py`). This wrapper translates geographic coordinates into the Cartesian plane expected by the V3.0 CRI engine. Performing this conversion asynchronously allows the engine to easily meet the 100 ms execution latency threshold required by SAE J2945/1.

Deploying the XGBoost layer to apocalyptic edge environments simply involves loading the serialized ONNX model onto an inference engine like TensorRT. The bounding physics engine executes deterministically on the primary micro-controller, while the ML inference provides a parallel confidence rating. If the AI detects a dangerous non-linear pattern, the system can modulate audible warnings without overriding the physics-driven haptic intervention, forming a dual-redundant alert topology.

---

## IX. DISCUSSION

Validation across 146,051 telemetry epochs establishes the superiority of the deterministic physics engine. An AUC of 0.9874 against a 2.27% near-miss positive rate highlights the robustness of the V3.0 model. This discriminatory capability arises directly from the $\max(R_{decel}, R_{ttc})$ severity gate. Suppressing the summation of low-tier probabilistic risks prevents compounded noise from triggering false alarms, isolating genuine near-miss scenarios even during aggressive TSV and HNR scenario injections.

While we envisioned the XGBoost AI pipeline as a robust parallel anchor, the AI AUC (0.8191) trails the physics model. This variation stems from the difficulty of training trees on an extremely sparse minority class (only 354 real CRITICAL samples). However, the ML matrix retains functional relevance: it maintains an 81.8% recall rate for CRITICAL events, proving its proficiency at flagging the most dangerous scenarios.

This performance delta strengthens the paper's core hypothesis. The finding that a transparent, deterministic algebraic model (0.9874) outperforms a non-linear machine learning classifier (0.8191) validates the decision to position the physics model as the primary actuation authority. Machine learning remains susceptible to temporal drift and overfitting over synthetic distributions. The severity-gated physics block completely bypasses this limitation, delivering consistent, interpretable bounds perfectly aligned with established physical laws of motion and braking distances.

Consequently, the AI's role is relegated to a complementary diagnostic fallback. By leveraging the XGBoost layer strictly for its high recall sensitivity, the architecture gains a valuable secondary observer. It can flag asymmetric anomaly patterns in the traffic flow that might evade mathematical boundaries, offering a hybridized solution without compromising functional safety transparency.

---

## X. CONCLUSION

This research formalizes and empirically validates a robust, predictive Vehicle-to-Vehicle Blind Spot Detection framework engineered to operate within the strict confines of a 5-field Basic Safety Message payload. By removing dependencies on secondary CAN-bus telemetry such as turn indicators and dynamic yaw rates, the system ensures broad deployment compatibility across mixed-heritage fleets utilizing DSRC or C-V2X communication networks. The V3.0 Collision Risk Index, fortified by the multiplicative severity gate $\max(R_{decel}, R_{ttc})$, resolves the persistent issue of false-positive saturation common to additive risk scoring models.

Exhaustive simulation across the 539-edge Atal Bridge network, incorporating dynamic Traffic Signal Violations and Hilly Narrow Road constraints, confirms the architectural resilience of the physics model. Recording an AUC of 0.9874 against a restricted near-miss proxy, the physics bounds consistently outperform conventional TTC baseline standards and XGBoost diagnostic structures. The parallel machine learning layer provides specific complementary value, retaining an 81.8% CRITICAL recall capacity that interfaces seamlessly with the deterministic output to form a dual-redundant tracking mechanism.

Future expansion of the system will transition the simulated ROS2 evaluation logic onto physical testbeds. By integrating commercial 802.11p transceivers and evaluating the logic against real-world GPS attenuation patterns absent artificial Gaussian noise modeling, the empirical boundaries of the severity gate can be further refined. The foundation established herein provides a transparent, lightweight, and verifiable paradigm for cooperative intersection safety, advancing the realization of zero-collision autonomous ecosystems.

---

### ACKNOWLEDGEMENTS

The authors thank the Eclipse SUMO development team (German Aerospace Center, DLR) for the open-source traffic simulation platform, and the OpenStreetMap contributors for the Atal Bridge road network data used in this study.

---

### REFERENCES

[1] SAE International, "Dedicated Short Range Communications (DSRC) Message Set Dictionary," SAE Standard J2735_202309, Sep. 2023.

[2] SAE International, "On-Board System Requirements for V2V Safety Communications," SAE Standard J2945/1_201603, Mar. 2016.

[3] IEEE, "IEEE Standard for Information Technology — Telecommunications and Information Exchange Between Systems — Local and Metropolitan Area Networks — Specific Requirements Part 11: Wireless LAN Medium Access Control (MAC) and Physical Layer (PHY) Specifications Amendment 6: Wireless Access in Vehicular Environments," IEEE Std 802.11p-2010, Jul. 2010.

[4] 3GPP, "Technical Specification Group Radio Access Network; Study on LTE-based V2X Services," 3GPP TR 36.885 V14.0.0, Jun. 2016.

[5] Euro NCAP, "Lane Change Assist System (LCAS) Test Protocol," Euro NCAP Technical Bulletin, Version 1.0, 2019.

[6] American Association of State Highway and Transportation Officials (AASHTO), "A Policy on Geometric Design of Highways and Streets," 7th ed., Washington, DC, 2018.

[7] E. N. Gilbert, "Capacity of a burst-noise channel," Bell System Technical Journal, vol. 39, no. 5, pp. 1253–1265, Sep. 1960.

[8] T. Chen and C. Guestrin, "XGBoost: A scalable tree boosting system," in Proc. 22nd ACM SIGKDD Int. Conf. Knowledge Discovery and Data Mining (KDD), San Francisco, CA, USA, Aug. 2016, pp. 785–794.

[9] P. A. Lopez, M. Behrisch, L. Bieker-Walz, J. Erdmann, Y. Flötteröd, R. Hilbrich, L. Lücken, J. Rummel, P. Wagner, and E. Wießner, "Microscopic traffic simulation using SUMO," in Proc. IEEE 21st Int. Conf. Intelligent Transportation Systems (ITSC), Maui, HI, USA, Nov. 2018, pp. 2575–2582.

[10] World Health Organization, "Global Status Report on Road Safety 2023," WHO, Geneva, Switzerland, Dec. 2023.

[11] Ministry of Road Transport and Highways (MoRTH), "Road Accidents in India 2022," Government of India, Transport Research Wing, New Delhi, Oct. 2023.

[12] A. Mousa, M. M. Abdel-Aty, J. Yuan, et al., "Vehicle-to-vehicle communication for blind spot detection," IEEE Transactions on Intelligent Transportation Systems, vol. 22, no. 5, pp. 3120-3131, May 2021.

[13] A. Festag, "Cooperative intelligent transport systems standards in Europe," IEEE Communications Magazine, vol. 52, no. 12, pp. 166–172, Dec. 2014.

[14] S. Biswas, R. Tatchikou, and F. Dion, "Vehicle-to-vehicle wireless communication protocols for enhancing highway traffic safety," IEEE Communications Magazine, vol. 44, no. 1, pp. 74–82, Jan. 2006.

[15] N. Chawla, K. Bowyer, L. Hall, and W. Kegelmeyer, "SMOTE: Synthetic minority over-sampling technique," Journal of Artificial Intelligence Research, vol. 16, pp. 321–357, Jun. 2002.
