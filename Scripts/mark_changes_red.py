"""
mark_changes_red.py
===================
Two operations:

  (1) Open paper/V2V_paper 24-06-26.docx, scan every paragraph and table cell,
      and colour RED the runs whose text does NOT appear in the pre-review
      paper (extracted from git tag c54c7f41:paper/main.tex). Untouched runs
      stay the original colour. Layout, font, spacing, table positions are
      not modified.

  (2) Produce paper/rebuttals/Reviewer_Comments_Consolidated.docx with the
      four original reviewer comments verbatim, each under its own heading.

Both outputs go next to the existing files.
"""
import re
import sys
import hashlib
from difflib import SequenceMatcher
from pathlib import Path

from docx import Document
from docx.shared import RGBColor, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

PROJ      = Path(__file__).resolve().parent.parent
DOCX_IN   = PROJ / 'paper' / 'V2V_paper 24-06-26.docx'
DOCX_OUT  = PROJ / 'paper' / 'V2V_paper 24-06-26_changes_red.docx'
DOCX_OLD  = Path(r'D:\Omkar D\Downloads\v2v_paper 15_05_2026.docx')
CONSOL    = PROJ / 'paper' / 'rebuttals' / 'Reviewer_Comments_Consolidated.docx'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def normalise(s: str) -> str:
    """Reduce string to lowercase word stream, alphanumeric only."""
    s = re.sub(r'[^\w]', ' ', s.lower())
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def best_match_ratio(new_norm: str, old_paras: list[str]) -> float:
    """Highest SequenceMatcher ratio between new_norm and any old paragraph
    (also tries against any old paragraph that CONTAINS the new text)."""
    if not new_norm:
        return 1.0
    best = 0.0
    for op in old_paras:
        if not op:
            continue
        # quick reject if length differs by 10x
        if max(len(op), len(new_norm)) > 10 * min(len(op), len(new_norm)) + 5:
            continue
        # also check if new_norm is a substring of op (small edit chunk)
        if new_norm in op or op in new_norm:
            return 1.0
        r = SequenceMatcher(None, new_norm, op, autojunk=False).ratio()
        if r > best:
            best = r
            if best > 0.95:
                return best
    return best


def collect_paragraph_texts(doc: Document) -> list[str]:
    """Return normalised text of every body & cell paragraph (skip empties)."""
    out = []
    for p in doc.paragraphs:
        t = normalise(p.text)
        if t:
            out.append(t)
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    t = normalise(p.text)
                    if t:
                        out.append(t)
    return out


def image_hash_set(doc: Document) -> set[str]:
    """MD5 hashes (first 12 chars) of every embedded image in the document."""
    out = set()
    for r in doc.part.rels.values():
        if 'image' in r.reltype:
            try:
                out.add(hashlib.md5(r.target_part.blob).hexdigest()[:12])
            except Exception:
                pass
    return out


def is_figure_caption(text: str) -> bool:
    """A figure caption looks like 'Fig. 3 ...' or 'Figure 3:'."""
    return bool(re.match(r'\s*Fig(?:ure)?\.?\s*\d+', text))


# Hashes of the new images in the new docx (computed once at startup).
# These captions should be RED; all other figure captions should be BLACK.
_NEW_IMAGE_HASHES = {
    'e69c0409d203',   # scenario diagram (Fig. 1 in new)
    'af41fca67bd9',   # SHAP summary
    '306240151c49',   # SHAP dependence
}

# Caption text fragments that map to NEW images (used to decide colour
# even when we can't reliably link caption->image via XML position).
_NEW_CAPTION_FRAGMENTS = (
    'lane-change blind-spot scenario',
    'occluding truck blocks',
    'shap beeswarm',
    'shap dependence',
)


def figure_caption_is_new(text: str) -> bool:
    low = text.lower()
    return any(frag in low for frag in _NEW_CAPTION_FRAGMENTS)


# ---------------------------------------------------------------------------
# Operation 1 — colour red where changed
# ---------------------------------------------------------------------------
RED = RGBColor(0xC0, 0x00, 0x00)


def colour_runs_red(paragraph):
    for run in paragraph.runs:
        if run.text.strip():
            run.font.color.rgb = RED


def mark_doc_changes():
    print('=' * 70)
    print('Marking changed paragraphs RED in', DOCX_IN.name)
    print('=' * 70)
    if not DOCX_OLD.exists():
        raise SystemExit(f'Pre-review baseline not found: {DOCX_OLD}')
    print(f'  loading old baseline:  {DOCX_OLD}')
    old_doc = Document(str(DOCX_OLD))
    old_paras = collect_paragraph_texts(old_doc)
    print(f'  old paragraphs (non-empty): {len(old_paras)}')

    doc = Document(str(DOCX_IN))
    print(f'  loaded:                     {len(doc.paragraphs)} paragraphs, {len(doc.tables)} tables')

    # similarity thresholds
    SAME_THRESHOLD = 0.85  # >= this means unchanged
    # below SAME_THRESHOLD => mark RED (either modified or new)

    changed = unchanged = short = 0

    # set of old headings (low-cased, alphanumeric only) for fast lookup
    old_heading_set = {normalise(p.text) for p in old_doc.paragraphs
                       if p.style and p.style.name and p.style.name.startswith('Heading')
                       and p.text.strip()}
    print(f'  old headings recorded:      {len(old_heading_set)}')

    def process(p):
        nonlocal changed, unchanged, short
        txt = p.text
        if not txt.strip():
            return
        norm = normalise(txt)
        # special-case: figure captions decide by image identity
        if is_figure_caption(txt):
            if figure_caption_is_new(txt):
                colour_runs_red(p)
                changed += 1
            else:
                unchanged += 1
            return
        # section headings: exact match against old heading set
        if p.style and p.style.name and p.style.name.startswith('Heading'):
            if norm in old_heading_set:
                unchanged += 1
            else:
                colour_runs_red(p)
                changed += 1
            return
        # very short non-heading fragments — leave alone
        if len(norm.split()) < 4:
            short += 1
            return
        # general text: sequence-match against best old paragraph
        ratio = best_match_ratio(norm, old_paras)
        if ratio >= SAME_THRESHOLD:
            unchanged += 1
        else:
            colour_runs_red(p)
            changed += 1

    for p in doc.paragraphs:
        process(p)

    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    process(p)

    print(f'  paragraphs/cells marked RED:    {changed}')
    print(f'  paragraphs/cells left untouched: {unchanged}')
    print(f'  short fragments skipped:         {short}')

    doc.save(str(DOCX_OUT))
    print(f'  wrote: {DOCX_OUT}')

    # --- Verification: input vs output must match in text & structure ---
    verify_structure_identical(DOCX_IN, DOCX_OUT)


def verify_structure_identical(orig_path: Path, marked_path: Path):
    """Confirm the marked file has IDENTICAL paragraph count, text, table
    count, and image count as the original. Only colour may differ."""
    a = Document(str(orig_path))
    b = Document(str(marked_path))
    issues = []
    if len(a.paragraphs) != len(b.paragraphs):
        issues.append(f'paragraph count differs: {len(a.paragraphs)} vs {len(b.paragraphs)}')
    if len(a.tables) != len(b.tables):
        issues.append(f'table count differs: {len(a.tables)} vs {len(b.tables)}')
    if image_hash_set(a) != image_hash_set(b):
        issues.append('image set differs')
    diff_text = 0
    for pa, pb in zip(a.paragraphs, b.paragraphs):
        if pa.text != pb.text:
            diff_text += 1
    if diff_text:
        issues.append(f'{diff_text} paragraphs differ in text content')
    # walk tables too
    for ta, tb in zip(a.tables, b.tables):
        for ra, rb in zip(ta.rows, tb.rows):
            for ca, cb in zip(ra.cells, rb.cells):
                if ca.text != cb.text:
                    issues.append(f'table cell text differs: \"{ca.text[:40]}\" vs \"{cb.text[:40]}\"')
                    break
    if issues:
        print('  VERIFY FAILED:')
        for i in issues:
            print(f'    - {i}')
    else:
        print('  VERIFY OK: text, paragraphs, tables, images all preserved.')


# ---------------------------------------------------------------------------
# Operation 2 — consolidated reviewer comments
# ---------------------------------------------------------------------------
REVIEWS = {
    'Reviewer 1':
"""This paper proposes a V2V-based blind spot detection system for lane-change safety. Instead of relying only on radar or cameras, which can fail when another vehicle blocks the sensor view, the system uses wireless vehicle-to-vehicle communication to detect hidden nearby vehicles. The key contribution is that it only needs 5 fields from the Basic Safety Message (BSM), making it simpler than previous methods that required more data. It also designs a Collision Risk Index (CRI) with a severity gate, meaning the system will not trigger a warning unless at least one risk factor is truly high. This helps reduce false alarms. The system was tested on a large simulated dataset of 146,051 vehicle interactions from a real road network and showed strong performance, with AUC = 0.9869 and stable results across multiple traffic simulations.

Here are some suggestions that could improve the paper:

1. Please clearly define the lane-change scenario and explain why blind spots are a critical safety issue that cannot be adequately addressed by onboard sensors alone. For example, the manuscript should describe how vehicles interact during lane-change maneuvers, how blind spots occur between adjacent or nearby vehicles, and how such blind spots may lead to potential collisions.

2. Please clarify how SMOTE helps address the issue of rare dangerous events.

3. It is recommended to use SHapley Additive exPlanations (SHAP) to improve feature interpretation.

4. The formula for RTTC is not well organized and should clarify TTC thresholds selection. The manuscript should present the RTTC equation in a more structured format, clearly define each variable, and explain how the metric is calculated in the lane-change context, as well as thresholds selection.

5. Although the topic is related to lane-change scenarios, the simulation design does not sufficiently reflect this focus. The manuscript should include a more specific simulation design, including the lane-change scenario setup, key behavioral parameters, vehicle interaction settings, and detailed simulation process steps.""",

    'Reviewer 2':
"""A V2V blind spot system using a minimal 5-field BSM (vs. 13) and a physics-based Collision Risk Index with a "severity gate" that suppresses false alarms by requiring one genuinely high danger signal. Clean engineering and honest caveats, but evidence is too narrow and circular for the headline claims.

Drawbacks:

1. The 0.9869 AUC is scored against a proxy that shares inputs with the model — self-consistency, not accuracy. Lead with the independent metric (n=27) and its confidence interval.

2. Many hand-set constants (α, β, K_brake, thresholds) appear fitted on the test set. Calibrate on a held-out split.

3. No pedestrians, cyclists, two-wheelers, or turn signals — and intent was disabled (γ=0), undercutting the lane-change use case. Motivated by mixed Indian traffic, yet excludes its dominant actors.

4. HNR/TSV acronyms misdefined in the setup, class proportions don't reconcile with the 2.37% positive rate.

5. No CIs or significance tests vs. baselines; six-seed result reuses the circular proxy.

6. Most citations pre-2021; missing recent C-V2X cooperative-perception work, so novelty is hard to place.""",

    'Reviewer 3':
"""This is a very timely study on blind spot detection systems using V2V communication. Overall, the paper is nicely written. The following are some suggestions to further improve its quality:

1) A figure showing the entire detection process visually would help readers understand the problem better. The existing Fig. 1 conveys the four-layer system architecture, but a complementary scenario-level figure would be more illustrative here: one depicting two communicating vehicles with a third vehicle occluding the line of sight, the BSM exchange passing through that obstruction, the subsequent CRI computation, and the resulting alert. This would make the core advantage of V2V over line-of-sight sensors immediately clear.

2) Since different vehicle classes have different sizes, and their blind spots vary accordingly, the paper should explicitly state the subject (ego) vehicle under consideration. The blind-spot zone model uses fixed parameters (L_base = 4.5 m, λ_scale = 12 m), which implies a single ego geometry, while the simulated fleet contains sedans, SUVs, and trucks whose blind spots differ substantially in shape and extent. The authors should therefore clarify whether these zone parameters are specific to one vehicle class (presumably a passenger car) or are intended to generalize across classes and justify that choice.

3) It is not clear whether the CRI is extensively validated. As presented, the primary metric (AUC = 0.9869) is computed against a kinematic near-miss proxy that is itself derived from the same TTC and gap quantities used to construct the CRI, so it measures internal rank-ordering consistency rather than independent validation. The authors should validate the CRI against an independent ground truth, such as the SUMO collision events reported with a confidence interval given the small sample or against real-world data.""",

    'Reviewer 4':
"""Dear authors,

Hereafter, some comments about your paper:

• With reference to page 1, in the introduction Section, you mentioned you want to use V2V communication to overcome some current limitations of on-board sensors: are you thinking about a kind of fusion, or a substitution?

• Overall, can you check throughout the text some formatting issues? For example: some overlapping formulas and "strange symbols" on page 3; some introductory text between title level 1 and 2 (e.g., Section 2 and section 2.1); acronyms should be explicit the first time you use it (e.g., CDF on page 3); missing number of Tables.

• On page 2, with reference to formula (1), can you detail it a little bit more? Which is its meaning?

• On page 3, with reference to formula (9), the road friction "mu" is statis or dynamic (e.g., changing value based on the external conditions or type of roads)?

• Same page, formula (11) is not totally clear: what "0,1" at the end represent?

• On page 4, at the beginning, you wrote that indicators are fundamental for your system, but what happens if the driver does not use it? Because it can occur the driver forgets it…

• As far as I know, SUMO is a traffic simulator, without the participation of human subjects; have you ever considered also this possibility, to collect more reliable data?

• On page 5, Section 6.1, which are the deterministic rules you used to define the ground-truth? And how did you define the threshold values?

• On page 6, what are you referring to, with "Tier 1", "Tier 2", and so on? To the friction of road?

• On page 7, you mentioned that the performances of XG-Boost are quite poor; have you also tried other methods? Just to know if there is an intrinsic problem in the data, for example.

• Finally, with reference to your conclusions, you could consider also more scenarios and conditions, even in simulators, especially in static type.""",
}


def _copy_paragraph_style(src_p, dst_p):
    """Copy text + simple character formatting from src run-by-run."""
    for sr in src_p.runs:
        if not sr.text:
            continue
        dr = dst_p.add_run(sr.text)
        dr.bold = sr.bold
        dr.italic = sr.italic
        try:
            if sr.font.color and sr.font.color.rgb is not None:
                dr.font.color.rgb = sr.font.color.rgb
        except Exception:
            pass


def _append_response_section(out_doc, reviewer_key):
    """Read Response_to_Reviewer_X.docx and append its body (skipping the
    big title/intro block, which would duplicate what the consolidated doc
    already says) to out_doc."""
    rev_num = reviewer_key.split()[-1]
    path = PROJ / 'paper' / 'rebuttals' / f'Response_to_Reviewer_{rev_num}.docx'
    if not path.exists():
        out_doc.add_paragraph(f'[Response document not found: {path.name}]')
        return
    rdoc = Document(str(path))
    # Skip the first ~4 paragraphs (Title / Manuscript / Corresponding /
    # "Dear Reviewer N,") because the consolidated file has its own header.
    skip_until_seen = False
    for p in rdoc.paragraphs:
        txt = p.text.strip()
        if not skip_until_seen:
            if txt.startswith('Comment ') or txt.startswith('Comment R'):
                skip_until_seen = True
            else:
                continue
        # copy paragraph with style preserved
        new_p = out_doc.add_paragraph()
        new_p.alignment = p.alignment
        # preserve simple style hints (Heading vs Normal vs List)
        try:
            new_p.style = p.style
        except Exception:
            pass
        _copy_paragraph_style(p, new_p)


def build_consolidated():
    print()
    print('=' * 70)
    print('Building consolidated reviewer-comments + responses document')
    print('=' * 70)
    CONSOL.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()

    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(11)

    # title
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('Reviewer Comments and Author Responses — Consolidated')
    r.bold = True
    r.font.size = Pt(16)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('Manuscript: Vehicle-to-Vehicle Communication for Blind Spot '
                  'Detection and Accident Prevention Using Severity-Gated '
                  'Collision Risk Indexing')
    r.italic = True
    r.font.size = Pt(10)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('Corresponding author: Deepali Vora (deepali.vora11@sitpune.edu.in)')
    r.font.size = Pt(10)
    r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    doc.add_paragraph()

    for reviewer, text in REVIEWS.items():
        # reviewer heading
        p = doc.add_paragraph()
        r = p.add_run(reviewer)
        r.bold = True
        r.font.size = Pt(15)
        r.font.color.rgb = RGBColor(0x1f, 0x3f, 0x7f)

        # ---- Original reviewer comments ----
        p = doc.add_paragraph()
        r = p.add_run('Original comments:')
        r.bold = True
        r.font.size = Pt(12)
        for block in text.strip().split('\n\n'):
            block = block.strip()
            if not block:
                continue
            doc.add_paragraph(block)
        doc.add_paragraph()

        # ---- Author responses (imported from individual rebuttal docs) ----
        p = doc.add_paragraph()
        r = p.add_run('Author responses:')
        r.bold = True
        r.font.size = Pt(12)
        _append_response_section(doc, reviewer)
        doc.add_paragraph()
        # visual separator
        sep = doc.add_paragraph('—' * 30)
        sep.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph()

    doc.save(str(CONSOL))
    print(f'  wrote: {CONSOL}')


# ---------------------------------------------------------------------------
if __name__ == '__main__':
    mark_doc_changes()
    build_consolidated()
    print('\nDone.')
