"""
mark_changes_red_round3.py
==========================
Round-3 red-marking: colour RED exactly the content changed in the round-3
revision, using the round-2 docx as the baseline.

Baseline and input are produced by the same pandoc pipeline, so paragraph
order and table structure line up. Two things still defeat a naive text diff:

  * Every equation paragraph changed its OMML encoding in round 3, because
    build_paper_docx.py now strips the alignment markers texmath used to leak
    into Word as literal ampersands and left-justifies the stacked rows. Only
    the displays whose mathematics actually changed are marked red -- Eqs. (4),
    (11), (13), (14), (16) and the unnumbered lateral-TTC branch added beside
    Eq. (14); for every other equation the difference is a rendering fix, not
    a content change.
  * Figure and table numbers shifted by one from the new Fig. 8 and Table 3,
    so many untouched paragraphs differ by a digit. A whitelist of round-3
    change fragments avoids marking that renumbering noise.

Body paragraphs are therefore coloured red iff their normalised text contains
one of the known round-3 change fragments; a fuzzy pass merely WARNS about
non-whitelisted paragraphs that look changed, so omissions can be reviewed.

Baseline : paper/rebuttals/round2_archive/V2V_paper 14-08-26_round2.docx
Input    : paper/V2V_paper 08-10-26.docx
Output   : paper/V2V_paper 08-10-26_changes_red.docx
"""
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

from docx import Document
from docx.shared import RGBColor
from docx.oxml.ns import qn

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJ     = Path(__file__).resolve().parent.parent
DOCX_OLD = PROJ / 'paper' / 'rebuttals' / 'round2_archive' / 'V2V_paper 14-08-26_round2.docx'
DOCX_IN  = PROJ / 'paper' / 'V2V_paper 08-10-26.docx'
DOCX_OUT = PROJ / 'paper' / 'V2V_paper 08-10-26_changes_red.docx'

RED = RGBColor(0xC0, 0x00, 0x00)
M_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/math}'

# ---------------------------------------------------------------------------
# Round-3 change whitelist. A body paragraph is coloured red iff its
# normalised text contains one of these fragments. Each fragment corresponds
# to a specific Round-3 edit of main.tex.
# ---------------------------------------------------------------------------
CHANGE_FRAGMENTS = [
    # --- Reviewer 1.1: Eqs. (4) and (13) presented more clearly --------------
    # Mathematical-model roadmap: the presentation convention now used
    'where a formula would otherwise need a deeply nested',
    # Eq. (4): new lead-in, new symbol definitions, new reading paragraph
    'the blind-spot zone lengthens with ego speed',
    'bounds its argument to the unit interval',
    'the two lines of eq',
    # Eqs. (5)-(6): the six zone-limit symbols are now defined
    'the four limits are the edges of the blind-spot zone',
    # Eq. (11): duplicated clip definition removed, now cross-referenced
    'the unit-interval bound already defined in eq',
    # Eq. (13): new lead-in and new reading paragraph
    'three-regime piecewise function',
    'how to read eq',
    # Eq. (14): the lateral branch is now stated explicitly
    'producing the lateral counterpart',
    'the two bodies already overlap laterally',
    'whichever of the two geometries is the more urgent',
    # Eq. (12): the engine's short-circuits are now described exactly
    'the implementation applies the same convention to any pair whose closing speed',
    # --- Reviewer 1.2: Results analysis framework ----------------------------
    'analysis framework',
    'because this section contains ten subsections',
    # the five stage labels of the description list ...
    'validity of the measuring stick',
    'how well does the engine detect',
    'is a learned model a better choice',
    'does the result survive a change of conditions',
    'why does it work and where does it break',
    # ... and the five stage bodies, which pandoc emits as separate paragraphs
    'defines the two ground-truth sources',
    'establishes the headline detection result',
    'tests the design decision at the heart of the paper',
    're-measures the stage-2 result',
    'attributes the stage-2 result to specific design choices',
    'read as a whole the five stages form a single argument',
    'function of each results subsection',
]

# Equation tags whose mathematics changed in round 3. Equation paragraphs
# carry no w:t text at all, so they are matched on their OMML content: by the
# trailing equation tag for numbered displays, and by a distinctive substring
# for the one display added unnumbered (the lateral TTC branch).
CHANGED_EQUATIONS = ('(4)', '(11)', '(13)', '(14)', '(16)')
CHANGED_UNNUMBERED = ('Rttc,lat=',)


def normalise(s: str) -> str:
    s = re.sub(r'[^\w.\[\]%-]', ' ', s.lower())
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def norm_ascii(s: str) -> str:
    """ASCII-only normalisation for table cells: math lives in OMML, which is
    invisible to text extraction, so only the ASCII part of a cell compares."""
    return normalise(s.encode('ascii', 'ignore').decode())


def omml_text(paragraph) -> str:
    """Visible text of every OMML run in a paragraph."""
    return ''.join(n.text or '' for n in paragraph._p.iter(M_NS + 't'))


def has_omml(paragraph) -> bool:
    return next(paragraph._p.iter(M_NS + 'r'), None) is not None


def _colour_omml(paragraph):
    """Colour OMML math runs red (python-docx run API does not reach them)."""
    for mr in paragraph._p.iter(M_NS + 'r'):
        wrPr = mr.find(qn('w:rPr'))
        if wrPr is None:
            wrPr = mr.makeelement(qn('w:rPr'), {})
            mrPr = mr.find(M_NS + 'rPr')
            if mrPr is not None:
                mrPr.addnext(wrPr)
            else:
                mr.insert(0, wrPr)
        color = wrPr.find(qn('w:color'))
        if color is None:
            color = wrPr.makeelement(qn('w:color'), {})
            wrPr.append(color)
        color.set(qn('w:val'), 'C00000')


def colour_red(paragraph):
    for run in paragraph.runs:
        if run.text.strip():
            run.font.color.rgb = RED
    _colour_omml(paragraph)


def old_table_rows(doc):
    """Old tables as row lists of ascii-normalised cells + flat cell sets."""
    out = []
    for tbl in doc.tables:
        rows, cells = [], set()
        for row in tbl.rows:
            r = [norm_ascii(cell.text) for cell in row.cells]
            rows.append(r)
            cells.update(t for t in r if t)
        out.append({'rows': rows, 'cells': cells})
    return out


# Body paragraphs in this manuscript run to a few thousand characters, so the
# advisory similarity pass is capped at a prefix and gated by difflib's cheap
# upper-bound ratios; a full O(n^2) match on every pair takes minutes and buys
# nothing, since the pass only prints warnings.
PREFIX = 400


def best_match_ratio(new_norm, old_paras):
    key = new_norm[:PREFIX]
    best = 0.0
    for op in old_paras:
        if not op:
            continue
        if new_norm in op or op in new_norm:
            return 1.0
        if max(len(op), len(new_norm)) > 10 * min(len(op), len(new_norm)) + 5:
            continue
        sm = SequenceMatcher(None, key, op[:PREFIX], autojunk=False)
        if sm.real_quick_ratio() <= best or sm.quick_ratio() <= best:
            continue
        best = max(best, sm.ratio())
        if best > 0.95:
            return best
    return best


def main():
    for f in (DOCX_OLD, DOCX_IN):
        if not f.exists():
            raise SystemExit(f'missing input: {f}')

    print(f'Baseline (round 2): {DOCX_OLD.name}')
    print(f'Input    (round 3): {DOCX_IN.name}')
    old_doc = Document(str(DOCX_OLD))
    old_paras = [normalise(p.text) for p in old_doc.paragraphs if p.text.strip()]
    old_tables = old_table_rows(old_doc)

    doc = Document(str(DOCX_IN))
    changed = unchanged = eq_red = 0
    warnings = []

    # ---- Body paragraphs: whitelist, plus the three changed equations ----
    for p in doc.paragraphs:
        txt = p.text.strip()
        if not txt:
            if has_omml(p):
                mt = omml_text(p).rstrip()
                if any(mt.endswith(tag) for tag in CHANGED_EQUATIONS) \
                        or any(frag in mt for frag in CHANGED_UNNUMBERED):
                    colour_red(p)
                    eq_red += 1
            continue
        norm = normalise(txt)
        if any(frag in norm for frag in CHANGE_FRAGMENTS):
            colour_red(p)
            changed += 1
        else:
            unchanged += 1
            if len(norm.split()) >= 6 and best_match_ratio(norm, old_paras) < 0.60:
                warnings.append(txt[:110])

    expected = len(CHANGED_EQUATIONS) + len(CHANGED_UNNUMBERED)
    print(f'  equations marked red: {eq_red} (expected {expected})')

    # ---- Tables: per-table policy ----
    for t_i, tbl in enumerate(doc.tables):
        new_rows = [[norm_ascii(c.text) for c in row.cells] for row in tbl.rows]
        new_cells = {t for r in new_rows for t in r if t}

        if 'stage' in new_cells and 'question it answers' in new_cells:
            policy = 'new'          # results-framework table (added in round 3)
        elif 'symbol' in new_cells and 'meaning' in new_cells:
            policy = 'notation'     # three symbol rows added in round 3
        else:
            policy = 'compare'

        best, best_ov = None, 0.0
        if policy in ('compare', 'notation'):
            for ot in old_tables:
                if not ot['cells']:
                    continue
                ov = len(new_cells & ot['cells']) / max(1, len(new_cells))
                if ov > best_ov:
                    best_ov, best = ov, ot

        # row alignment by first-cell label (positional cell comparison)
        aligned = {}
        if best is not None:
            old_by_label = {r[0]: r for r in best['rows'] if r and r[0]}
            for r_i, nr in enumerate(new_rows):
                if nr and nr[0] and nr[0] in old_by_label \
                        and len(old_by_label[nr[0]]) == len(nr):
                    aligned[r_i] = old_by_label[nr[0]]

        for r_i, row in enumerate(tbl.rows):
            # In the notation table the Symbol column is pure OMML, so a new
            # row is recognised by its Meaning cell and the whole row is
            # coloured together.
            row_red = None
            if policy == 'notation':
                meaning = norm_ascii(row.cells[-1].text)
                row_red = bool(meaning) and best is not None \
                    and meaning not in best['cells']

            for c_i, cell in enumerate(row.cells):
                t = norm_ascii(cell.text)
                if policy == 'new':
                    red = True
                elif row_red is not None:
                    red = row_red
                elif not t:
                    continue
                elif r_i in aligned:
                    red = aligned[r_i][c_i] != t
                else:
                    red = best is None or t not in best['cells']
                for p in cell.paragraphs:
                    if not (p.text.strip() or has_omml(p)):
                        continue
                    if red:
                        colour_red(p)
                        changed += 1
                    else:
                        unchanged += 1

        tag = policy if policy != 'compare' else \
            f'overlap {best_ov:.0%}, {len(aligned)}/{len(new_rows)} rows aligned'
        print(f'  table {t_i}: {tag}')

    print(f'  RED: {changed + eq_red}   black: {unchanged}')
    if warnings:
        print('  ADVISORY - non-whitelisted paragraphs with low similarity to round 2:')
        for w in warnings:
            print('   ?', w)

    doc.save(str(DOCX_OUT))
    print(f'  wrote: {DOCX_OUT}')

    # ---- verification: text & structure identical to the input ----
    a, b = Document(str(DOCX_IN)), Document(str(DOCX_OUT))
    ok = (len(a.paragraphs) == len(b.paragraphs)
          and len(a.tables) == len(b.tables)
          and all(pa.text == pb.text for pa, pb in zip(a.paragraphs, b.paragraphs)))
    print('  VERIFY OK' if ok else '  VERIFY FAILED')


if __name__ == '__main__':
    main()
