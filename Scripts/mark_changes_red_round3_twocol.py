"""
mark_changes_red_round3_twocol.py
=================================
Round-3 red-marking for the PDF-style (two-column, LaTeX-compiled) docx
export - the companion to mark_changes_red_round3.py, which does the same job
for the pandoc build. Both the baseline (the round-2 docx the reviewers
received) and the input share the same rendering pipeline - math as unicode
text, small runs, line-break hyphenation - so changes are detected by a
word-level diff of the two token streams instead of a whitelist.

Derived from mark_changes_red_17.py; the diff engine, the renumbering filter
and the moved-block rescue pass are unchanged. Round 3 inserts a new Fig. 8
and a new Table 3, so figures 8-18 shift to 9-19 and tables 3-10 to 4-11;
is_renumbering() already treats that as noise rather than a content change.
Equation numbering is unchanged.

Marking rules:
  - Tokens in 'insert' blocks -> red.
  - Tokens in 'replace' blocks -> red, EXCEPT pure renumbering noise:
      * citation brackets on both sides ([26] -> [19]),
      * integer swaps directly after Fig./Table/Figure/Sections tokens
        (figure/table numbers shifted by the new Fig. 8 / Table 3),
      * hyphenation/ligature artifacts (same letters, different splits).
  - A run is coloured red if any of its tokens is marked.
Layout, spacing, tables, images are untouched - only w:color on runs.

Baseline : paper/rebuttals/round2_archive/V2V_paper 17-08-26_round2.docx
Input    : paper/V2V_paper 09-10-26.docx
Output   : paper/V2V_paper 09-10-26_changes_red.docx
"""
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from docx import Document
from docx.shared import RGBColor
from docx.text.paragraph import Paragraph
from docx.table import Table
from docx.oxml.ns import qn

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJ     = Path(__file__).resolve().parent.parent
DOCX_OLD = (PROJ / 'paper' / 'rebuttals' / 'round2_archive'
            / 'V2V_paper 17-08-26_round2.docx')
DOCX_IN  = PROJ / 'paper' / 'V2V_paper 09-10-26.docx'
DOCX_OUT = PROJ / 'paper' / 'V2V_paper 09-10-26_changes_red.docx'

RED = RGBColor(0xC0, 0x00, 0x00)

TOKEN_RE = re.compile(r'\[\d+\]|[a-z0-9]+(?:[.,][0-9]+)*')
CITE_RE  = re.compile(r'^\[\d+\]$')
INT_RE   = re.compile(r'^\d{1,3}(?:\.\d{1,2})?$')
FLOAT_CONTEXT = {'fig', 'fig.', 'figs', 'figs.', 'figure', 'figures',
                 'table', 'tables', 'section', 'sections', 'eq', 'eq.'}


def norm_text(s: str) -> str:
    """Fold unicode (ligatures via NFKD), drop hyphens/soft hyphens so
    line-break hyphenation merges, keep only ascii."""
    s = unicodedata.normalize('NFKD', s)
    s = s.replace('­', '').replace('-', '').replace('‐', '')
    s = s.encode('ascii', 'ignore').decode().lower()
    return s


def iter_block_paragraphs(doc):
    """All paragraphs in body order: body paragraphs and table-cell
    paragraphs interleaved as they appear in the document element."""
    body = doc.element.body

    def walk(el):
        for child in el.iterchildren():
            if child.tag == qn('w:p'):
                yield Paragraph(child, doc)
            elif child.tag == qn('w:tbl'):
                tbl = Table(child, doc)
                for row in tbl.rows:
                    for cell in row.cells:
                        for p in cell.paragraphs:
                            yield p
    yield from walk(body)


def token_stream(doc, with_refs: bool):
    toks, refs = [], []
    for p in iter_block_paragraphs(doc):
        for run in p.runs:
            for t in TOKEN_RE.findall(norm_text(run.text)):
                toks.append(t)
                if with_refs:
                    refs.append(run)
    return (toks, refs) if with_refs else toks


def is_renumbering(a_toks, b_toks, b_start, new_toks):
    """True if a replace block is citation/figure/table renumbering or a
    hyphenation artifact rather than a content change."""
    if not a_toks or not b_toks:
        return False
    # hyphenation / ligature artifact: same letters, different splits
    if ''.join(a_toks) == ''.join(b_toks):
        return True
    # citation renumbering: every token on both sides is [n]
    if all(CITE_RE.match(t) for t in a_toks) and \
       all(CITE_RE.match(t) for t in b_toks):
        return True
    # figure/table/section number shift: short integer swap right after a
    # Fig./Table/Section token in the NEW stream
    if len(a_toks) <= 2 and len(b_toks) <= 2 and \
       all(INT_RE.match(t) for t in a_toks) and \
       all(INT_RE.match(t) for t in b_toks):
        ctx = new_toks[max(0, b_start - 2):b_start]
        if any(c in FLOAT_CONTEXT for c in ctx):
            return True
    return False


def main():
    print(f'Baseline (round 2): {DOCX_OLD.name}')
    print(f'Input    (round 3): {DOCX_IN.name}')
    old_doc = Document(str(DOCX_OLD))
    new_doc = Document(str(DOCX_IN))

    old_toks = token_stream(old_doc, with_refs=False)
    new_toks, new_refs = token_stream(new_doc, with_refs=True)
    print(f'  old tokens: {len(old_toks):,}   new tokens: {len(new_toks):,}')

    sm = SequenceMatcher(None, old_toks, new_toks, autojunk=False)
    # Colour the stored run wrappers directly: p.runs creates fresh wrapper
    # objects on every iteration, so identity tests across passes fail.
    red_runs = []
    seen = set()
    n_equal = n_marked = n_skipped = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            n_equal += j2 - j1
            continue
        if tag == 'delete':
            continue                      # nothing in the new doc to colour
        a_toks, b_toks = old_toks[i1:i2], new_toks[j1:j2]
        if tag == 'replace' and is_renumbering(a_toks, b_toks, j1, new_toks):
            n_skipped += j2 - j1
            continue
        for j in range(j1, j2):
            run = new_refs[j]
            if id(run._r) not in seen:
                seen.add(id(run._r))
                red_runs.append(run)
            n_marked += 1

    print(f'  tokens equal: {n_equal:,}  marked red: {n_marked:,}  '
          f'renumbering skipped: {n_skipped:,}')

    # ---- rescue pass: difflib cannot detect MOVED blocks (pagination pushes
    #      floats/captions/sections around between the two PDF exports), so a
    #      moved-but-unchanged block arrives here marked red. Unmark any
    #      paragraph, run-group, or table row whose full normalised text
    #      exists verbatim anywhere in the round-2 document.
    def squash(s: str) -> str:
        return re.sub(r'[^a-z0-9.,%\[\]]', '', norm_text(s))

    old_char = squash(' '.join(p.text for p in iter_block_paragraphs(old_doc)))
    # The round-2 PDF export scrambles column order, splitting sentences
    # across distant stream positions, so contiguous substring membership
    # under-matches. n-gram window vote: a fragment counts as round-2 text
    # if >= 80% of its 30-char windows occur anywhere in the old document.
    GRAM = 30
    old_grams = set()
    for i in range(max(0, len(old_char) - GRAM + 1)):
        old_grams.add(old_char[i:i + GRAM])

    def in_old(sq: str) -> bool:
        if len(sq) < GRAM:
            return sq in old_char
        starts = list(range(0, len(sq) - GRAM + 1, 10))
        if starts[-1] != len(sq) - GRAM:
            starts.append(len(sq) - GRAM)
        hits = sum(1 for s in starts if sq[s:s + GRAM] in old_grams)
        return hits / len(starts) >= 0.8
    red_ids = {id(r._r) for r in red_runs}
    rescued = 0

    # (a) table rows that exist verbatim in round 2
    for tbl in new_doc.tables:
        for row in tbl.rows:
            row_runs = [r for c in row.cells for p in c.paragraphs
                        for r in p.runs]
            if not any(id(r._r) in red_ids for r in row_runs):
                continue
            row_t = squash(''.join(c.text for c in row.cells))
            if len(row_t) >= 20 and in_old(row_t):
                for r in row_runs:
                    red_ids.discard(id(r._r))
                    rescued += 1

    # (b) whole paragraphs that exist verbatim in round 2
    for p in iter_block_paragraphs(new_doc):
        p_runs = list(p.runs)
        if not any(id(r._r) in red_ids for r in p_runs):
            continue
        t = squash(p.text)
        if len(t) >= 30 and in_old(t):
            for r in p_runs:
                if id(r._r) in red_ids:
                    red_ids.discard(id(r._r))
                    rescued += 1
            continue
        # (c) contiguous red run-groups inside mixed paragraphs. Runs whose
        #     text squashes to nothing (pure whitespace between words in the
        #     PDF export) are neutral: they join a group without breaking it.
        group = []
        for r in p_runs + [None]:
            if r is not None and (id(r._r) in red_ids or not squash(r.text)):
                if group or id(r._r) in red_ids:
                    group.append(r)
                continue
            if group:
                g = squash(''.join(x.text for x in group))
                if len(g) >= 25 and in_old(g):
                    for x in group:
                        if id(x._r) in red_ids:
                            red_ids.discard(id(x._r))
                            rescued += 1
                group = []

        # (d) sentence-level backstop: unmark red runs lying inside a
        #     sentence whose full text exists verbatim in round 2.
        raw = p.text
        offsets, pos = [], 0
        for r in p_runs:
            offsets.append((pos, pos + len(r.text), r))
            pos += len(r.text)
        # sentence bounds: split only at enders followed by whitespace and an
        # uppercase letter, so decimals (4.7) do not fragment sentences
        bounds = [0] + [m.end() for m in
                        re.finditer(r'(?<=[.!?])\s+(?=[A-Z(\[])', raw)] + [len(raw)]
        for b0, b1 in zip(bounds[:-1], bounds[1:]):
            t = squash(raw[b0:b1])
            if len(t) >= 25 and in_old(t):
                for s, e, r in offsets:
                    if id(r._r) in red_ids and s >= b0 and e <= b1:
                        red_ids.discard(id(r._r))
                        rescued += 1

    coloured = 0
    for run in red_runs:
        if id(run._r) in red_ids:
            run.font.color.rgb = RED
            coloured += 1
    print(f'  moved-block runs rescued (kept black): {rescued:,}')
    print(f'  runs coloured red: {coloured:,}')

    new_doc.save(str(DOCX_OUT))
    print(f'  wrote: {DOCX_OUT}')

    # ---- verification: text and structure identical, only colour differs ----
    a = Document(str(DOCX_IN))
    b = Document(str(DOCX_OUT))
    pa = [p.text for p in a.paragraphs]
    pb = [p.text for p in b.paragraphs]
    ok = (pa == pb and len(a.tables) == len(b.tables))
    for ta, tb in zip(a.tables, b.tables):
        for ra, rb in zip(ta.rows, tb.rows):
            for ca, cb in zip(ra.cells, rb.cells):
                if ca.text != cb.text:
                    ok = False
    print('  VERIFY OK: text/structure identical' if ok else '  VERIFY FAILED')


if __name__ == '__main__':
    main()
