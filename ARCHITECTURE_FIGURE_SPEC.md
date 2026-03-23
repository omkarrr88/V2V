# Architecture Diagram Generation Specification

**Target file:** `Outputs/figures/architecture_diagram.png`  
**Dimensions:** 1400 × 800 pixels, 300 DPI  
**Format:** Professional IEEE-style block diagram, no 3D, no gradients, no shadows

## Layer Specification

### Layer 1 (Bottom, fill: #E8F4FD) — "Simulation & Environment"
- **Box 1** (left): "Eclipse SUMO (TraCI / libsumo)"  
- **Box 2** (right): "Scenario Injector (TSV + HNR)"  
- Arrow from Box 1 → Box 2, labelled "vehicle states"

### Layer 2 (fill: #EDF7ED) — "Communication & Perception"
- **Box 3** (left): "Gilbert-Elliott Channel (p_G2B=0.01, p_B2G=0.10)"  
- **Box 4** (centre): "Dead Reckoning (CA-CYR, τ_eff = τ_base + k_lost·Δt)"  
- **Box 5** (right): "GNSS Noise Filter (σ = 1.5 m Gaussian)"

### Layer 3 (fill: #FEF9E7) — "Intelligence Kernel"
- **Box 6** (left, larger): "BSD Engine V3.0 — CRI = P × max(R_d, R_t) × [αR_d + βR_t + γR_i] × Γ_PLR"  
- **Box 7** (right): "XGBoost Hybrid — 18 features | SMOTE | CRITICAL recall 81.8%"

### Layer 4 (Top, fill: #FDF2F8) — "Presentation & Analytics"
- **Box 8** (left): "Streamlit Dashboard (bsd_live.json)"  
- **Box 9** (centre): "Evaluation (ROC/AUC, Ablation)"  
- **Box 10** (right): "Paper Figures (300 DPI)"

## Annotations
- Vertical arrows on left margin between layers, labelled "BSM @ 10 Hz (5 fields)"
- Horizontal feedback arrow from Layer 4 → Layer 3 on right margin, labelled "model training"

## Style
- Font: Arial or Helvetica, 11pt labels, 9pt sublabels
- All boxes: rounded rectangles (r=8px), thin black border (1px), light fill
- IEEE Transactions figure style: clean line art only
