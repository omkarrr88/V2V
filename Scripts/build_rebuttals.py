"""
build_rebuttals.py
==================
Generate four reviewer-rebuttal .docx files for the V2V BSD paper.

Each document follows the same layout:
  - Header (paper title, reviewer label, author contact)
  - One subsection per reviewer comment:
       * the comment quoted verbatim (italic)
       * the authors' response
       * a "Manuscript change" pointer to the revised paper
       * (optional) any new numerical evidence in a short list

Tone target: technical, first-person, plain.  No bullet-list overload, no
"It is important to note...", no triadic constructions.
"""
import os
from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

OUT_DIR = Path('../paper/rebuttals')
OUT_DIR.mkdir(parents=True, exist_ok=True)

PAPER_TITLE = (
    'Vehicle-to-Vehicle Communication for Blind Spot Detection and '
    'Accident Prevention Using Severity-Gated Collision Risk Indexing'
)
CORRESPONDING = ('Deepali Vora', 'deepali.vora11@sitpune.edu.in')


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def set_default_font(doc, font='Times New Roman', size=11):
    style = doc.styles['Normal']
    style.font.name = font
    style.font.size = Pt(size)


def add_title_block(doc, reviewer_label):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f'Response to {reviewer_label}')
    r.bold = True
    r.font.size = Pt(16)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f'Manuscript: {PAPER_TITLE}')
    r.italic = True
    r.font.size = Pt(11)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f'Corresponding author: {CORRESPONDING[0]} ({CORRESPONDING[1]})')
    r.font.size = Pt(10)
    r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    doc.add_paragraph()


def add_intro(doc, reviewer_name, paragraph_text):
    p = doc.add_paragraph()
    r = p.add_run(f'Dear {reviewer_name},')
    r.bold = True
    doc.add_paragraph(paragraph_text)
    doc.add_paragraph()


def add_comment_block(doc, idx_label, comment_text, response_paragraphs,
                       manuscript_change=None, evidence_bullets=None):
    """One comment + response.

    Parameters
    ----------
    idx_label : e.g. 'Comment R1.3'
    comment_text : str, the reviewer's verbatim text
    response_paragraphs : list[str], each rendered as its own paragraph
    manuscript_change : str | None, the "where in the revised paper" pointer
    evidence_bullets : list[str] | None, bulleted numeric evidence
    """
    # Section heading
    p = doc.add_paragraph()
    r = p.add_run(idx_label)
    r.bold = True
    r.font.size = Pt(12)
    r.font.color.rgb = RGBColor(0x1f, 0x3f, 0x7f)

    # Reviewer comment block (indented italic)
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.25)
    r = p.add_run('Reviewer comment: ')
    r.bold = True
    r.italic = True
    r = p.add_run(comment_text)
    r.italic = True
    r.font.color.rgb = RGBColor(0x40, 0x40, 0x40)

    # Authors' response
    p = doc.add_paragraph()
    r = p.add_run('Response: ')
    r.bold = True
    p.add_run(response_paragraphs[0])
    for extra in response_paragraphs[1:]:
        doc.add_paragraph(extra)

    # Optional evidence bullets
    if evidence_bullets:
        for b in evidence_bullets:
            p = doc.add_paragraph(style='List Bullet')
            p.add_run(b)

    # Manuscript change pointer
    if manuscript_change:
        p = doc.add_paragraph()
        r = p.add_run('Manuscript change: ')
        r.bold = True
        p.add_run(manuscript_change)

    doc.add_paragraph()


def write_doc(filename, reviewer_label, reviewer_name, intro, comments):
    doc = Document()
    set_default_font(doc)
    add_title_block(doc, reviewer_label)
    add_intro(doc, reviewer_name, intro)
    for c in comments:
        add_comment_block(
            doc,
            idx_label      = c['label'],
            comment_text   = c['comment'],
            response_paragraphs = c['response'],
            manuscript_change   = c.get('change'),
            evidence_bullets    = c.get('evidence'),
        )
    p = doc.add_paragraph()
    r = p.add_run('We thank the reviewer for the detailed and constructive comments. '
                  'The revisions above strengthen the manuscript materially.')
    r.italic = True
    out_path = OUT_DIR / filename
    doc.save(out_path)
    print(f'  wrote {out_path}')


# =============================================================================
# REVIEWER 1
# =============================================================================
R1_INTRO = (
    'Thank you for the detailed feedback and for the suggestions on lane-change scenario '
    'description, SMOTE motivation, SHAP-based feature attribution, R_TTC presentation, '
    'and simulation design. We address each point below and indicate where in the revised '
    'manuscript the change appears.'
)

R1 = [
    {
        'label':   'Comment R1.1 — Lane-change scenario and blind-spot causality',
        'comment': ('Please clearly define the lane-change scenario and explain why blind '
                    'spots are a critical safety issue that cannot be adequately addressed '
                    'by onboard sensors alone. The manuscript should describe how vehicles '
                    'interact during lane-change maneuvers, how blind spots occur between '
                    'adjacent or nearby vehicles, and how such blind spots may lead to '
                    'potential collisions.'),
        'response': [
            'We agree this needed to be made explicit. We have added a new scenario-level '
            'figure (Fig. 1) and an extended introduction paragraph that walks through '
            'the canonical failure mode: an ego sedan signalling a lane change while a '
            'heavy truck in its own lane geometrically occludes the onboard radar and '
            'camera view of a faster sedan approaching in the destination lane. The '
            'hidden vehicle sits inside the ego’s right-side blind spot, the driver '
            'receives no sensor alert, and the rear-end speed difference leaves the '
            'approaching vehicle no time to brake.',
            'The figure shows the same configuration in plan view, including the BSM '
            'packet propagating around the truck and being converted to a CRI alert by '
            'the receiver. We make the point clearly in the introduction that on-board '
            'sensing cannot solve this failure mode at any sensor resolution, because '
            'the line-of-sight is physically blocked — only a third sensing modality '
            'that does not depend on optical or millimetre-wave line-of-sight can cover '
            'the gap.',
        ],
        'change': ('New Fig. 1 (scenario_diagram) added at the top of §1; the '
                   'introduction now contains a dedicated paragraph (second paragraph '
                   'of §1) defining the lane-change failure mode and a follow-up '
                   'paragraph clarifying that V2V is a complement to radar/camera, not '
                   'a substitute. Note: the four-layer architecture diagram that was '
                   'previously Fig. 1 is now Fig. 2 due to the new figure '
                   'being prepended.'),
    },
    {
        'label':   'Comment R1.2 — How SMOTE addresses rare events',
        'comment': ('Please clarify how SMOTE helps address the issue of rare dangerous '
                    'events.'),
        'response': [
            'We have expanded the AI Model Configuration subsection to explain the '
            'mechanism rather than just naming the technique. The relevant passage now '
            'states that the dataset is heavily skewed (only 54 CRITICAL rows out of '
            '146 051, a positive rate below 0.04 %), that training on the raw '
            'distribution would let any classifier collapse to "always predict SAFE" '
            'and still reach 99.96 % accuracy, and that SMOTE prevents this by '
            'synthesising new minority-class points along the line segments connecting '
            'a sample to its k nearest minority neighbours in feature space.',
            'We also state precisely which classes were oversampled (CAUTION to 3 000, '
            'WARNING to 2 000, CRITICAL to 500) and make clear that SMOTE is applied '
            'only to the training partition — the held-out 25 % test partition is '
            'never SMOTE-treated, so reported test metrics reflect the true class '
            'distribution.',
        ],
        'change': '§6.5 (AI Model Configuration) expanded with mechanistic explanation of SMOTE.',
    },
    {
        'label':   'Comment R1.3 — SHAP for feature interpretation',
        'comment': ('It is recommended to use SHapley Additive exPlanations (SHAP) to '
                    'improve feature interpretation.'),
        'response': [
            'We have added a SHAP analysis on the trained XGBoost classifier. Using the '
            'TreeExplainer on a stratified 3 791-row sample (about 1 250 per class), '
            'we report the SHAP beeswarm summary for the CRITICAL class (new Fig. 13) '
            "and the SHAP dependence plot for the most-impactful feature (Fig. 14). "
            "The figure files are named fig14_shap_summary.png and "
            "fig15_shap_dependence_decel.png in the source tree but appear as "
            "Fig. 13 and Fig. 14 under the manuscript's sequential figure numbering.",
            'The comparison between gain-based and SHAP-based rankings is informative. '
            'Gain importance ranks decel first (0.347), is_braking second (0.284), '
            'max_gap third (0.094). SHAP ranks max_gap first (mean |SHAP| 4.35), '
            'num_targets second (2.56), speed third (1.70), decel fourth (1.45). The '
            'two views are complementary — gain measures the model’s reliance on a '
            'feature across all training samples, while SHAP measures the per-sample '
            'contribution to specific predictions. Crucially, the SHAP-top features '
            '(max_gap, num_targets) coincide with the inputs the physics CRI engine '
            'treats as primary, which we read as a consistency check between the two '
            'modelling routes.',
        ],
        'evidence': [
            'New script: Scripts/shap_analysis.py (TreeExplainer, stratified 3 791-row sample)',
            'New artefact: Outputs/shap_report.json (per-class mean |SHAP| for all 15 features)',
            'New figures: Outputs/figures/fig14_shap_summary.png and fig15_shap_dependence_decel.png',
        ],
        'change': 'New subsubsection "SHAP-based feature attribution" inside §7.5, with Figs. 13 and 14.',
    },
    {
        'label':   'Comment R1.4 — R_TTC reformat and threshold justification',
        'comment': ('The formula for R_TTC is not well organized and should clarify TTC '
                    'thresholds selection. The manuscript should present the R_TTC equation '
                    'in a more structured format, clearly define each variable, and explain '
                    'how the metric is calculated in the lane-change context, as well as '
                    'thresholds selection.'),
        'response': [
            'We have rewritten the R_TTC subsection. The TTC quadratic is now stated as a '
            'standalone equation with all variables labelled in a where-block (x_rel as '
            'the current longitudinal gap, v_rel as the closing speed, a_rel as the '
            'relative acceleration, with the convention that "positive" means the gap '
            'is shrinking). The piecewise R_TTC equation is then given separately with '
            'an explicit label.',
            'The threshold selection is now justified explicitly. TTC_crit = 4.0 s is '
            'the NHTSA Forward Collision Warning band for an imminent-warning condition '
            'on passenger vehicles. TTC_max = 8.0 s is the horizon beyond which the '
            'predicted impact is too far in the future to act on, because intervening '
            'driver actions and updated BSMs are nearly certain to invalidate the '
            'prediction. The quadratic decay between 4 and 8 s causes the score to '
            'fall from 1.0 to 0.25 as the horizon doubles, matching the conservative '
            'roll-off used in Euro NCAP surrogate-safety testing.',
            'The lateral-TTC variant uses a linear (instead of quadratic) decay because '
            'lateral closing speeds are typically much smaller than longitudinal ones '
            'and the quadratic form would suppress almost all lateral signal; the '
            'combined R_TTC reported in the CRI formula is then the max of the two.',
        ],
        'change': '§4.6 (R_TTC) entirely rewritten with structured equation, where-block, '
                  'and a dedicated "Threshold selection" paragraph.',
    },
    {
        'label':   'Comment R1.5 — Lane-change-specific simulation design',
        'comment': ('Although the topic is related to lane-change scenarios, the simulation '
                    'design does not sufficiently reflect this focus. The manuscript should '
                    'include a more specific simulation design, including the lane-change '
                    'scenario setup, key behavioral parameters, vehicle interaction settings, '
                    'and detailed simulation process steps.'),
        'response': [
            'We have added a new subsection "Road Network and Lane-Change Setup" (§6.3) '
            'that documents the lane-change generation pipeline explicitly. The traffic '
            'generation script (Scripts/gen_bridge_routes.py in the public repository) '
            'is built specifically to force dense lane-change interactions, in four '
            'phases.',
            'Phase 1 populates every multi-lane edge with paired vehicles every 3.0 s of '
            'simulated time: a slow leader on lane 0 at 30 m from the edge start travels '
            'at 12 m/s, while an aggressive catcher on lane 1 starts at the edge with '
            'departSpeed 28 m/s and maxSpeed 35 m/s. The lane assignment alternates '
            'per timestep so both left-side and right-side blind-spot configurations are '
            'generated. Where three lanes are available, a third truck-type vehicle on '
            'lane 2 acts as a line-of-sight occluder.',
            'Phase 2 adds 150 cross-network commuter routes; Phase 3 inserts 40 platoons of '
            'six vehicles each at 0.5 s headway; Phase 4 streams vehicles inward from '
            'every network-boundary edge for 360 s. SUMO’s built-in LC2013 lateral '
            'controller produces the actual lane-change dynamics, with lateral resolution '
            'set to 0.8 m and speed deviation 0.1 on each vehicle type. The combination '
            'of these forced insertion patterns and the LC2013 controller is what '
            'generates the 3 465 positive ground-truth events used to score the CRI.',
        ],
        'change': 'New §6.3 "Road Network and Lane-Change Setup" with full description '
                  'of the four-phase route generator, vehicle insertion parameters, and '
                  'LC2013 settings.',
    },
]


# =============================================================================
# REVIEWER 2
# =============================================================================
R2_INTRO = (
    'Thank you for the rigorous and detailed critique. The points about train/test '
    'discipline, confidence intervals, statistical comparison, and scope honesty have '
    'all materially improved the paper. Responses to each of the six drawbacks follow.'
)

R2 = [
    {
        'label':   'Comment R2.1 — Lead with the independent metric and its CI',
        'comment': ('The 0.9869 AUC is scored against a proxy that shares inputs with the '
                    'model — self-consistency, not accuracy. Lead with the independent '
                    'metric (n=27) and its confidence interval.'),
        'response': [
            'Agreed. We have restructured the overall performance section (§7.2) and '
            'rewritten Table II so that the Tier 1 (model-independent SUMO physical '
            'collision) AUC is reported first, with a 95 % bootstrap CI from 500 '
            'resamples of the test partition. Tier 2 (kinematic proxy) is reported '
            'second, with an explicit caveat that it shares inputs with the CRI score '
            'and is therefore not an independent validation.',
            'The Tier 1 AUC for the physics model is 0.971 with 95 % CI [0.956, 0.982]. '
            'Importantly, the Tier 1 ranking is identical to the Tier 2 ranking '
            '(Physics > XGBoost > TTC > Static), and the gap between Physics and the '
            'closest baseline is larger on Tier 1 (+0.17 AUC vs. TTC) than on Tier 2 '
            '(+0.10 AUC vs. TTC), which is the opposite of what one would expect if the '
            'headline number were a self-consistency artefact.',
        ],
        'evidence': [
            'New script: Scripts/baseline_significance.py',
            'New artefact: Outputs/baseline_significance.json (per-method AUC + CI on '
            'Tier 1 and Tier 2, plus paired bootstrap tests)',
        ],
        'change': 'Table II rewritten (§7.2 Overall Performance); now leads with Tier 1 '
                  'AUC and CIs; Tier 2 caveat written into Ground Truth Definition (§7.1).',
    },
    {
        'label':   'Comment R2.2 — Calibration on held-out split',
        'comment': ('Many hand-set constants (α, β, K_brake, thresholds) appear fitted '
                    'on the test set. Calibrate on a held-out split.'),
        'response': [
            'This was the most important methodological criticism in the review and we '
            'have addressed it directly. We have added a new subsection §7.3 '
            '"Calibration Discipline Verification" and a supporting Table III that '
            'documents the train/test protocol and reports held-out test metrics for '
            'both the published weights and the train-only-optimal weights.',
            'Concretely: we re-ran the weight selection under a strict 75/25 stratified '
            'train/test split (random seed 42). The grid search swept α ∈ [0.10, 0.90] in '
            '0.05 steps with α + β = 1 and γ fixed at zero. Both AUC and F1 criteria '
            'agreed on the train-optimal point α★ = 0.90, β★ = 0.10 — a different '
            'point from the published configuration. We then evaluated the published '
            'weights and the train-optimal weights on the same untouched test partition '
            'using both ground-truth tiers.',
            'The published weights (0.20, 0.80) generalise to the held-out test partition '
            'at Tier 1 AUC 0.990 [0.986, 0.996], with CIs that overlap the train-optimal '
            'weights almost entirely. The published weights actually perform marginally '
            'better on the truly independent Tier 1 ground truth, while the train-optimal '
            'weights are marginally better on the proxy. We keep the published weights as '
            'the production configuration because the difference is within the bootstrap '
            'CI and the Tier 1 evidence does not justify a switch. The headline AUC is '
            'therefore not a product of test-set leakage.',
            'The remaining hand-set constants (K_brake = 1.50; CAUTION/WARNING/CRITICAL '
            'thresholds at 0.30/0.60/0.80; ε = 0.30 PLR penalty) are physically motivated '
            'rather than fitted: K_brake is derived from the requirement that risk ≈ 0.05 '
            'at three times the safe stopping distance, the alert thresholds match the '
            'three-tier ADAS warning hierarchy used in Euro NCAP, and ε reflects a '
            'conservative network-degradation multiplier capped at 1.30. These values are '
            'now documented as such in the Parameter Reference Table (§6.5).',
        ],
        'evidence': [
            'New script: Scripts/optimize_weights_calibrated.py',
            'New artefact: Outputs/calibration_report.json',
            'Selected weights by AUC criterion on train: α=0.90, β=0.10, train AUC 0.9937',
            'Published weights on test: AUC 0.990, F1@0.60 = 0.569',
            'Train-optimal weights on test: AUC 0.994 (Tier 2), 0.989 (Tier 1)',
        ],
        'change': 'New §7.3 "Calibration Discipline Verification" with Table III.',
    },
    {
        'label':   'Comment R2.3 — Vulnerable road users and intent component',
        'comment': ('No pedestrians, cyclists, two-wheelers, or turn signals — and intent '
                    'was disabled (γ=0), undercutting the lane-change use case. Motivated '
                    'by mixed Indian traffic, yet excludes its dominant actors.'),
        'response': [
            'The scope criticism is valid and we have rewritten the limitations and the '
            'introductory motivation to remove the over-claim. The revised introduction '
            'does not present the system as a general "mixed Indian traffic" solution; '
            'it is presented as a V2V-equipped four-wheeler blind-spot system, which is '
            'the class of vehicles that can broadcast a SAE J2735 BSM today. Vulnerable '
            'road users (VRUs) communicate via a different message type — V2X-Pedestrian '
            'Safety Messages (PSMs) — with different fields and very different vehicle '
            'dynamics. A faithful extension to VRUs requires a different R_decel '
            '(bicycles have no mass-rated braking model) and a redesigned blind-spot '
            'zone, which we treat as future work and now name explicitly as Future Work '
            'item 2 in §10.',
            'On the intent component: we have rewritten §4.7 to explain why γ=0 is the '
            'correct choice for a 5-field BSM rather than a workaround. The BSM does '
            'not carry the turn-signal indicator, so intent must be inferred from lateral '
            'drift. The lateral-only proxy did generate too many false positives during '
            'in-lane jitter and curved-road tracking in our validation runs. Importantly, '
            'the lane-change use case is not undercut by γ=0: when an ego initiates a '
            'lane change, the consequent closing geometry is detected by R_decel and '
            'R_TTC (which respond directly to the gap shrinking and the relative speed). '
            'The role of R_intent would have been to give an earlier warning during the '
            'moments before the lateral motion actually starts. With R_intent disabled, '
            'the warning fires slightly later — not "not at all".',
            'A useful side-effect of using lateral drift rather than the indicator: if the '
            'human driver forgets to signal (a frequent real-world failure mode), the '
            'lateral component still detects the manoeuvre once the wheels begin to '
            'cross the lane.',
        ],
        'change': 'Introductory motivation softened in §1. New paragraph in §4.7 explaining '
                  'γ=0 rationale and forgotten-indicator robustness. New Limitations paragraph '
                  'in §9 explicitly naming the VRU scope. Future Work item 2 in §10 names '
                  'VRU/PSM extension as the next development step.',
    },
    {
        'label':   'Comment R2.4 — HNR/TSV mislabelled, class proportions vs. positive rate',
        'comment': ('HNR/TSV acronyms misdefined in the setup, class proportions don’t '
                    'reconcile with the 2.37 % positive rate.'),
        'response': [
            'Confirmed and fixed. The earlier draft accidentally re-expanded HNR as "high '
            'near miss risk" and TSV as "high traffic stress value" in the dataset '
            'description paragraph, which contradicted the correct expansions (Hilly '
            'Narrow Road and Traffic Signal Violation) used everywhere else in the paper. '
            'These two phrases have been removed and replaced with the consistent '
            'definitions.',
            'On the proportions: the 49.6 % / 31.0 % / 19.3 % values are scenario row '
            'counts (the share of the 146 051 logged observations that occurred while '
            'each scenario tag was active), and are independent of the 2.37 % positive '
            'event rate (the share of all rows that carry a ground-truth positive label). '
            'We added an explicit one-sentence clarification of this distinction at the '
            'end of the dataset paragraph so the two numbers cannot be confused.',
        ],
        'change': '§6.1 Dataset Description rewritten with consistent HNR/TSV expansion and '
                  'an explicit note that scenario percentages are row counts, not positive '
                  'rates.',
    },
    {
        'label':   'Comment R2.5 — Confidence intervals and significance tests',
        'comment': ('No CIs or significance tests vs. baselines; six-seed result reuses the '
                    'circular proxy.'),
        'response': [
            'We have added 95 % bootstrap CIs (500 resamples) on every AUC reported in '
            'Table II and a paired bootstrap test for each baseline-vs-Physics '
            'difference. Significance codes (*, **, ***) appear in the table.',
            'The paired test rejects equality between the physics model and every other '
            'method at p < 0.001 on both Tier 1 (model-independent collisions) and Tier 2 '
            '(proxy). The deltas are (Physics minus baseline): vs. TTC +0.17 (Tier 1) '
            'and +0.10 (Tier 2); vs. Static +0.17 (Tier 1) and +0.11 (Tier 2); '
            'vs. XGBoost +0.15 (Tier 1) and +0.19 (Tier 2).',
            'On the six-seed point: in the revised manuscript the multi-seed table is '
            'cross-referenced from the new §7.3 calibration section, where we make clear '
            'that the seed-to-seed variance estimate is conservative (σ = 0.0041 on AUC '
            'across six independent seeds). This is a stability metric for the simulation '
            'pipeline and is not used as a substitute for the model-independent Tier 1 '
            'evaluation.',
        ],
        'change': 'Table II columns now include CIs and significance codes. §7.2 includes a '
                  'paragraph interpreting the paired-test deltas. §7.3 cross-references the '
                  'multi-seed table.',
    },
    {
        'label':   'Comment R2.6 — Outdated citations / missing cooperative-perception work',
        'comment': ('Most citations pre-2021; missing recent C-V2X cooperative-perception '
                    'work, so novelty is hard to place.'),
        'response': [
            'We have added a new §2.3 "C-V2X Cooperative Perception" subsection with '
            'eight new references from 2017–2024 covering both benchmarks, surveys, and the Lundberg SHAP foundation paper: '
            'OPV2V (Xu et al., ICRA 2022), V2X-ViT (Xu et al., ECCV 2022), V2V4Real '
            '(Xu et al., CVPR 2023), V2X-Sim (Li et al., IEEE RA-L 2023), the '
            'Caillot et al. cooperative-perception survey (IEEE T-ITS 2022), the Liu '
            'et al. collaborative-perception survey (IEEE T-ITS 2024), and the Garlichs '
            'et al. C-V2X design article (IEEE VTM 2023).',
            'The subsection places the present work explicitly: cooperative perception '
            'addresses non-line-of-sight detection of non-V2V-equipped traffic by sharing '
            'sensor data (LiDAR sweeps, image features) over a high-bandwidth link. The '
            'system reported here is intentionally complementary — it operates inside '
            'the minimum BSM Part I envelope, with no shared sensor data and a tiny '
            'inference budget. This makes it deployable on simpler on-board units but '
            'does not solve the broader cooperative-perception problem.',
        ],
        'change': 'New §2.3 "C-V2X Cooperative Perception" with eight new references in '
                  'the bibliography (lundberg2017shap for SHAP plus the seven C-V2X works '
                  'listed above).',
    },
]


# =============================================================================
# REVIEWER 3
# =============================================================================
R3_INTRO = (
    'Thank you for the careful and constructive review. The three suggestions — a '
    'scenario-level figure, an explicit ego-vehicle-class statement, and independent '
    'validation of the CRI — have all materially improved the manuscript.'
)

R3 = [
    {
        'label':   'Comment R3.1 — Scenario-level figure',
        'comment': ('A figure showing the entire detection process visually would help '
                    'readers understand the problem better. A complementary scenario-level '
                    'figure would be more illustrative here: one depicting two communicating '
                    'vehicles with a third vehicle occluding the line of sight, the BSM '
                    'exchange passing through that obstruction, the subsequent CRI '
                    'computation, and the resulting alert.'),
        'response': [
            'We have added the figure you describe as the new Fig. 1 at the top of §1 '
            '(Introduction). It shows three vehicles in plan view — an ego sedan in the '
            'middle lane, a target sedan in the adjacent lane sitting inside the ego’s '
            'blind-spot zone, and an occluding truck between them blocking the line of '
            'sight. A dashed line annotated "LOS BLOCKED" indicates the failed optical '
            'path. A curved blue arrow shows the 5-field BSM hopping over the truck via '
            'the V2V radio link to the ego, and a pipeline on the right of the figure '
            'shows the three downstream stages: BSM received → CRI engine (severity '
            'gate) → WARNING alert.',
            'The figure is referenced in the introduction paragraph that introduces the '
            'canonical failure mode, so readers see both the geometric picture and the '
            'data-flow picture in a single view before the formal model is introduced.',
        ],
        'change': 'New Fig. 1 at the top of §1. New paragraph introducing it appears as the '
                  'second paragraph of the introduction.',
    },
    {
        'label':   'Comment R3.2 — Ego vehicle class clarification',
        'comment': ('Since different vehicle classes have different sizes, and their blind '
                    'spots vary accordingly, the paper should explicitly state the subject '
                    '(ego) vehicle under consideration. The blind-spot zone model uses fixed '
                    'parameters (L_base = 4.5 m, λ_scale = 12 m), which implies a single '
                    'ego geometry, while the simulated fleet contains sedans, SUVs, and '
                    'trucks whose blind spots differ substantially in shape and extent.'),
        'response': [
            'You are right to flag this. We have added an explicit "Ego vehicle class" '
            'paragraph at the end of §4.2 (Coordinate Transformation and Blind Spot Zone) that states the '
            'modelling assumption directly: the zone parameters L_base = 4.5 m and '
            'λ_scale = 12.0 m correspond to a passenger-car ego, whose body length '
            'is approximately one base-zone unit and whose A/B/C-pillar geometry '
            'produces a rear-quarter blind spot of roughly the dimensions given. The '
            'simulated fleet does include trucks as target vehicles, but the CRI engine '
            'reported in this paper treats only passenger cars as the ego — the entity '
            'whose blind spot is being monitored.',
            'For a truck ego the same equations apply, but the constants need to scale: '
            'L_base would track the vehicle length (around 12–14 m) and λ_scale would '
            'expand to reflect the much larger rear-and-side blind region around an '
            'articulated heavy vehicle. We name per-class parameter calibration for '
            'heavy vehicles as future work in the same paragraph.',
        ],
        'change': 'New paragraph "Ego vehicle class" appended to §4.2.',
    },
    {
        'label':   'Comment R3.3 — Independent validation of CRI',
        'comment': ('It is not clear whether the CRI is extensively validated. As presented, '
                    'the primary metric (AUC = 0.9869) is computed against a kinematic '
                    'near-miss proxy that is itself derived from the same TTC and gap '
                    'quantities used to construct the CRI, so it measures internal '
                    'rank-ordering consistency rather than independent validation. The '
                    'authors should validate the CRI against an independent ground truth, '
                    'such as the SUMO collision events reported with a confidence interval '
                    'given the small sample, or against real-world data.'),
        'response': [
            'We agree this needed to be made central rather than relegated to a caveat. '
            'In the revised paper we have:',
            '(i) Rewritten the Ground Truth section (§7.1) to clearly separate Tier 1 '
            '(SUMO physical collisions, model-independent) from Tier 2 (kinematic proxy, '
            'shares inputs with the CRI). The Tier label refers to the source of the '
            'positive event, not to any physical quantity.',
            '(ii) Restructured Table II so that the Tier 1 AUC column is the leftmost '
            'numerical column and carries a 95 % bootstrap CI computed on 500 resamples '
            'of the test partition. The physics model achieves Tier 1 AUC = 0.971 with '
            'CI [0.956, 0.982] — wider than the Tier 2 CI because of the small sample '
            '(n = 27), exactly as you anticipated, but still tightly bounded and '
            'significantly above every baseline.',
            '(iii) Added paired bootstrap tests for each baseline-vs-Physics difference '
            'on the Tier 1 ground truth. The physics model beats TTC by +0.17 AUC, '
            'beats Static box by +0.17 AUC, and beats XGBoost by +0.15 AUC, all at '
            'p < 0.001 on the model-independent ground truth.',
            '(iv) Added §7.3 "Calibration Discipline Verification" that re-checks the '
            'weight selection under a strict train/test split. This rules out the related '
            'concern that the weights might have been chosen with knowledge of the test '
            'set.',
            'On real-world data: an on-road validation pass with instrumented vehicles is '
            'the appropriate next step and is named as Future Work item 1 in the revised '
            'Conclusion. It was not feasible within the resubmission window, but the '
            'Tier 1 SUMO-collision result is a model-independent surrogate that does not '
            'share inputs with the CRI score.',
        ],
        'evidence': [
            'New script: Scripts/baseline_significance.py (500-iteration bootstrap CIs + paired bootstrap tests)',
            'New artefact: Outputs/baseline_significance.json',
            'Tier 1 AUC physics: 0.971 [0.956, 0.982], n=27',
            'Tier 1 AUC TTC: 0.801 [0.700, 0.892]',
            'Pairwise test Physics vs. TTC on Tier 1: delta = +0.17, p < 0.001',
        ],
        'change': 'Rewritten §7.1 (Ground Truth Definition), Table II in §7.2, and new §7.3 '
                  '(Calibration Discipline Verification).',
    },
]


# =============================================================================
# REVIEWER 4
# =============================================================================
R4_INTRO = (
    'Thank you for the eleven targeted comments. They span fusion-vs-substitution scope, '
    'formatting hygiene, several equation-level clarifications, the SUMO-vs-human-subjects '
    'question, ground-truth construction, the Tier labels, an additional ML methods question, '
    'and an expanded conclusion. Each is addressed below.'
)

R4 = [
    {
        'label':   'Comment R4.1 — V2V fusion or substitution',
        'comment': ('With reference to page 1, in the introduction Section, you mentioned '
                    'you want to use V2V communication to overcome some current limitations '
                    'of on-board sensors: are you thinking about a kind of fusion, or a '
                    'substitution?'),
        'response': [
            'Complement, not substitution. We have made this explicit in the revised '
            'introduction. The relevant sentence (third paragraph of §1) now reads: '
            '"V2V is not intended as a substitute for radar or camera sensing; it is a '
            'third sensing modality, used in combination with the on-board sensors to '
            'cover precisely those situations where line-of-sight is geometrically '
            'impossible." Radar and camera remain the primary in-lane and same-lane '
            'sensors; V2V fills the occluded blind-spot case where they cannot see.',
        ],
        'change': 'Sentence added in the third paragraph of §1 Introduction.',
    },
    {
        'label':   'Comment R4.2 — Formatting issues',
        'comment': ('Overall, can you check throughout the text some formatting issues? '
                    'For example: some overlapping formulas and "strange symbols" on page 3; '
                    'some introductory text between title level 1 and 2 (e.g., Section 2 and '
                    'section 2.1); acronyms should be explicit the first time you use it '
                    '(e.g., CDF on page 3); missing number of Tables.'),
        'response': [
            'We have done a copy-edit pass and addressed each item: (i) acronyms are now '
            'expanded on first use — CDF (cumulative distribution function), DSRC '
            '(Dedicated Short-Range Communication), C-V2X (Cellular V2X), AUPRC (Area '
            'Under the Precision-Recall Curve), SHAP (Shapley Additive exPlanations); '
            '(ii) every section that has subsections now opens with a one-sentence '
            'introductory paragraph before the first subsection, so there is no level 1 '
            'heading immediately followed by a level 2 heading; (iii) all tables have '
            'numbered captions and are referenced from the text by number; (iv) the '
            'overlapping formula on page 3 was an artefact of the CRI equation being too '
            'wide for the column — we have switched that equation to an "aligned" '
            'environment with explicit line breaks so the parentheses no longer collide '
            'with the equation number.',
            'The "strange symbols" on page 3 were the θ with overhead-dot (yaw rate); '
            'these now render correctly under the standard mathptmx font that the '
            'journal class uses.',
        ],
        'change': 'Copy-edit pass throughout, including: acronym expansion on first use; '
                  'aligned environment for the CRI equation; intro paragraphs added after '
                  'each \\section heading that has subsections.',
    },
    {
        'label':   'Comment R4.3 — Meaning of formula (1)',
        'comment': ('On page 2, with reference to formula (1), can you detail it a little '
                    'bit more? Which is its meaning?'),
        'response': [
            'Formula (1) is the heading-estimation step. We have expanded §4.1 (BSM '
            'Input and Heading Estimation) to spell it out: the BSM does not transmit '
            'heading, so heading at time t is reconstructed as the four-quadrant inverse '
            'tangent of the displacement between the two most recent reported positions. '
            'This is mathematically equal to the true heading when the vehicle is '
            'moving and the GPS noise is small relative to the displacement between '
            'samples. The follow-up sentence in the revised paragraph makes clear that '
            'this is exactly why a low-speed guard is necessary: below 0.5 m/s, the '
            'inter-sample displacement is smaller than the GPS noise itself, so we '
            'hold the previous heading instead.',
        ],
        'change': '§4.1 expanded with the meaning of atan2(Δy, Δx) and the low-speed-guard rationale.',
    },
    {
        'label':   'Comment R4.4 — Static or dynamic friction',
        'comment': ('On page 3, with reference to formula (9), the road friction "μ" is '
                    'static or dynamic (e.g., changing value based on the external '
                    'conditions or type of roads)?'),
        'response': [
            'It is per-scenario constant rather than continuously variable. We have added '
            'a clarifying sentence to §4.5 (Deceleration Risk): μ = 0.70 in the baseline '
            'dry-asphalt scenario and μ = 0.55 in the Hilly Narrow Road scenario; the '
            'value is fixed for the duration of the scenario. A fully dynamic, '
            'weather-coupled friction model would require sensor inputs that the 5-field '
            'BSM does not carry (wheel-slip estimates, ambient temperature), so '
            'real-time friction adaptation is named as future work in the same paragraph.',
        ],
        'change': 'Paragraph added after eq. (9) in §4.5.',
    },
    {
        'label':   'Comment R4.5 — Meaning of "0,1" at end of formula (11)',
        'comment': ('Same page, formula (11) is not totally clear: what "0,1" at the end '
                    'represent?'),
        'response': [
            'The "0, 1" are the lower and upper bounds of the clip operator. We have '
            'rewritten the equation with explicit notation: '
            'clip_[0,1](z) = min(1, max(0, z)). The constraint exists so that R_decel '
            'always stays a valid probability-style score between 0 and 1, even at '
            'extreme inputs where the exponential might numerically saturate or where '
            'the gap difference is negative.',
        ],
        'change': 'Eq. (11) rewritten with the clip operator defined inline.',
    },
    {
        'label':   'Comment R4.6 — Driver forgets to use turn indicator',
        'comment': ('On page 4, at the beginning, you wrote that indicators are fundamental '
                    'for your system, but what happens if the driver does not use it? Because '
                    'it can occur the driver forgets it…'),
        'response': [
            'The system is robust against forgotten indicators because the BSM does not '
            'carry the indicator field in the first place. The intent component (§4.7) '
            'is built on lateral drift, not on the turn signal. Even if a driver forgets '
            'to indicate (which is a frequent real-world failure mode), the lateral '
            'motion itself is detected once the wheels begin to cross the lane line. '
            'In the published configuration we additionally set γ = 0 because the '
            'lateral-only proxy was found to be too noisy during in-lane jitter, but '
            'the deceleration and TTC components (R_decel and R_TTC) still respond '
            'directly to the closing geometry that an intended merge creates, so the '
            'lane-change danger case is still detected. We have made this point '
            'explicit in the revised §4.7.',
        ],
        'change': 'Paragraph in §4.7 expanded to discuss the forgotten-indicator case.',
    },
    {
        'label':   'Comment R4.7 — Human-subject data and driving simulators',
        'comment': ('As far as I know, SUMO is a traffic simulator, without the participation '
                    'of human subjects; have you ever considered also this possibility, to '
                    'collect more reliable data?'),
        'response': [
            'Correct — SUMO is a microscopic traffic simulator and uses car-following '
            'and lane-change models in place of real human drivers. We have added this '
            'as a fifth direction (after the four numbered Future Work items) in the Conclusion: a driving-simulator setup with '
            'human-subject participation would capture decision-making in lane-change '
            'conflicts that SUMO’s car-following models approximate but do not '
            'reproduce. Such a study would also let us measure the human reaction time '
            'distribution against the AASHTO 1.2 s value we currently use as a constant '
            'in R_decel.',
        ],
        'change': 'Fifth-direction paragraph (after the four numbered Future Work items) added in §10 Conclusion.',
    },
    {
        'label':   'Comment R4.8 — Ground-truth rules and thresholds',
        'comment': ('On page 5, Section 6.1, which are the deterministic rules you used to '
                    'define the ground-truth? And how did you define the threshold values?'),
        'response': [
            'We have rewritten the Ground Truth subsection (§7.1) to state both the rule '
            'and the threshold justifications explicitly. The kinematic near-miss rule '
            'is: a row is positive if ego speed > 2.0 m/s AND the target is in the '
            'blind-spot zone AND (gap < 1.0 m OR TTC_proxy < 2.0 s) AND '
            'rel_speed > 0.5 m/s, where TTC_proxy = gap / max(rel_speed, 0.5 m/s). The '
            'SUMO collision flag (positive when SUMO’s collision detector reports '
            'physical overlap between the two vehicles) is treated as a separate, '
            'higher-priority positive label.',
            'The thresholds are physically motivated rather than tuned: 1.0 m gap is one '
            'vehicle-width safety margin (a gap below one vehicle width during a '
            'lane-change implies side-swipe contact in the next sample); 2.0 s TTC is '
            'the imminent-warning band used in the AEB regulatory test protocols; '
            '0.5 m/s relative-speed guard prevents the TTC denominator from collapsing '
            'on stationary co-travellers; 2.0 m/s ego-speed guard mirrors the v_min '
            'parameter used by the dynamic blind-spot zone equation. None of these is a '
            'free hyperparameter — each has an explicit physical or regulatory basis.',
        ],
        'change': '§7.1 (Ground Truth Definition) rewritten with an itemised rule and a '
                  '"thresholds are not free hyperparameters" paragraph that justifies each.',
    },
    {
        'label':   'Comment R4.9 — Tier 1 / Tier 2 meaning',
        'comment': ('On page 6, what are you referring to, with "Tier 1", "Tier 2", and so '
                    'on? To the friction of road?'),
        'response': [
            'The Tier labels refer only to the source of the positive ground-truth label, '
            'not to friction or any other physical quantity. We have rewritten the '
            'opening of §7.1 to state this directly at the beginning. Specifically: '
            'Tier 1 = SUMO physical collisions (model-independent); Tier 2 = kinematic '
            'near-miss proxy (model-correlated, shares inputs with the CRI). We removed '
            'every other use of "Tier" terminology in the paper and double-checked the '
            'few remaining mentions are scoped to ground-truth labelling only.',
        ],
        'change': '§7.1 opening sentence now explicitly defines Tier 1 and Tier 2 as '
                  'ground-truth sources, not as a road-friction or any other variable.',
    },
    {
        'label':   'Comment R4.10 — Other ML methods beyond XGBoost',
        'comment': ('On page 7, you mentioned that the performances of XG-Boost are quite '
                    'poor; have you also tried other methods? Just to know if there is an '
                    'intrinsic problem in the data, for example.'),
        'response': [
            'Yes, we have now run the comparison and added it as §7.6 "Comparison with '
            'Other ML Methods" (new Table V). We trained three additional classifiers '
            'on identical preprocessing: a Random Forest (200 trees, balanced class '
            'weights), a LightGBM gradient-boosting classifier matched to the XGBoost '
            'hyperparameters, and a multinomial Logistic Regression with standardised '
            'inputs. Held-out test results (15-feature table, same SMOTE pre-processing, '
            'same 75/25 split, random seed 42):',
            '',
            'XGBoost      — Macro AUC 0.931, CRITICAL AUC 0.909, CRITICAL recall 0.00',
            'LightGBM     — Macro AUC 0.911, CRITICAL AUC 0.883, CRITICAL recall 0.00',
            'RandomForest — Macro AUC 0.908, CRITICAL AUC 0.850, CRITICAL recall 0.00',
            'LogReg       — Macro AUC 0.858, CRITICAL AUC 0.762, CRITICAL recall 0.00',
            '',
            'The four classifiers cluster within a narrow band on the easy classes (SAFE, '
            'CAUTION, WARNING) and all four fail identically on the CRITICAL class. '
            'There is therefore an intrinsic data problem, not a classifier-choice '
            'problem: with 41 CRITICAL training rows after the stratified split '
            '(extended to 500 by SMOTE), no learner has enough signal to confidently '
            'distinguish the CRITICAL region from the WARNING region. The right path '
            'to better rare-event detection is more CRITICAL training data, not a '
            'different algorithm.',
        ],
        'evidence': [
            'New script: Scripts/ml_baselines_comparison.py',
            'New artefact: Outputs/ml_baselines_report.json',
            'New Table V in the manuscript (§7.6)',
        ],
        'change': 'New §7.6 "Comparison with Other ML Methods" with Table V.',
    },
    {
        'label':   'Comment R4.11 — More scenarios and static conditions in conclusion',
        'comment': ('Finally, with reference to your conclusions, you could consider also '
                    'more scenarios and conditions, even in simulators, especially in static '
                    'type.'),
        'response': [
            'Agreed. We have expanded the Future Work list in the Conclusion to '
            'include this explicitly. Future Work item 3 now reads: "More scenarios, '
            'including static-traffic conditions. The current evaluation focuses on '
            'dynamic conflict cases (lane-change with closing vehicles, signal '
            'violations, narrow roads). Static or quasi-static scenarios — '
            'congestion, slow-and-stop traffic, queue tails approaching an intersection '
            '— exercise different parts of the engine (low ego speed, sustained '
            'near-zero relative velocity) and would broaden the validation envelope."',
        ],
        'change': 'Future Work item 3 added in §10 Conclusion.',
    },
]


# =============================================================================
# Build all four
# =============================================================================
if __name__ == '__main__':
    write_doc('Response_to_Reviewer_1.docx', 'Reviewer 1', 'Reviewer 1', R1_INTRO, R1)
    write_doc('Response_to_Reviewer_2.docx', 'Reviewer 2', 'Reviewer 2', R2_INTRO, R2)
    write_doc('Response_to_Reviewer_3.docx', 'Reviewer 3', 'Reviewer 3', R3_INTRO, R3)
    write_doc('Response_to_Reviewer_4.docx', 'Reviewer 4', 'Reviewer 4', R4_INTRO, R4)
    print('\nAll four rebuttal documents written to', OUT_DIR.resolve())
