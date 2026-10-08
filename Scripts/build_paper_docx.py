"""
build_paper_docx.py
===================
Convert paper/main.tex into a .docx that approximates the Overleaf rendering,
with all figures embedded.

Approach:
  1. Read main.tex.
  2. resolve_cross_refs(): deterministically resolve everything pandoc cannot
     -- figure/table/equation/section numbers for \\ref, caption prefixes,
     bracketed [n] citations, and a numbered References section -- and render
     the equation numbers into the math itself.
  3. drop_align_markers(): remove the top-level '&' of aligned/align/split.
  4. strip_for_pandoc(): replace the Springer Nature \\documentclass and the
     class-specific commands (\\sn-jnl is not supported by pandoc) with a
     vanilla `article` preamble, rewrite the author/affiliation front matter,
     and drop booktabs \\addlinespace.
  5. Pipe through pandoc -> main.docx with `--resource-path=.` so figure paths
     resolve.
  6. left_justify_stacked_math(): post-process the .docx so the rows of a
     multi-line equation are left-justified rather than flush right.

Steps 3, 4 (\\addlinespace) and 6 exist only to work around pandoc conversion
defects; each is applied to the temp source or the built .docx, never to
paper/main.tex, so the Overleaf build is unaffected. See the comment on each
function for the defect it compensates for.

Output:
  paper/main.docx
"""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

# Resolved from this file, not the working directory, so the script runs from
# anywhere.
PAPER_DIR  = (Path(__file__).resolve().parent.parent / 'paper')
TEX_IN     = PAPER_DIR / 'main.tex'
TEX_TMP    = PAPER_DIR / '_main_for_pandoc.tex'
DOCX_OUT   = PAPER_DIR / 'main.docx'
PANDOC_BIN = (Path(__file__).resolve().parent.parent / '.venv' / 'Scripts' / 'pandoc.exe')


AUTHOR_PAR = (r'Omkar Kadam\textsuperscript{1}, Abhinav Prasad\textsuperscript{1}, '
              r'Gauri Phanse\textsuperscript{1}, Afraz Khan\textsuperscript{1}, '
              r'Vaishali Khairnar\textsuperscript{1}, Safia Sadruddin\textsuperscript{2}, '
              r'Deepali Vora\textsuperscript{3*}')
AFFIL_PAR  = (r'\textsuperscript{1}Department of Information Technology, Terna Engineering '
              r'College, Nerul, Navi Mumbai, India. \textsuperscript{2}Department of Computer '
              r'Engineering, Terna Engineering College, Nerul, Navi Mumbai, India. '
              r'\textsuperscript{3}Symbiosis Institute of Technology, Symbiosis International '
              r'(Deemed University), Pune, India.')
CORR_PAR   = r'*Corresponding author(s). E-mail(s): deepali.vora11@sitpune.edu.in;'


def resolve_cross_refs(src: str) -> str:
    """Deterministically resolve everything pandoc cannot: figure/table/equation/
    section numbers for \\ref{}, 'Fig. N' / 'Table N' caption prefixes, bracketed
    [n] citations, and a numbered References section. Applied only to the pandoc
    temp source; the Overleaf/LaTeX version keeps native numbering."""
    label_num = {}

    # ---- bibliography order -> citation numbers ----
    bib_keys = re.findall(r'\\bibitem\{([^}]+)\}', src)
    bib_num = {k: i + 1 for i, k in enumerate(bib_keys)}

    def cite_repl(m):
        keys = [k.strip() for k in m.group(1).split(',')]
        nums = [bib_num.get(k) for k in keys]
        if any(n is None for n in nums):
            missing = [k for k, n in zip(keys, nums) if n is None]
            print(f'  WARNING: \\cite key(s) without bibitem: {missing}')
        return ' [' + ', '.join(str(n) for n in nums if n is not None) + ']'
    src = re.sub(r'~?\\cite\{([^}]+)\}', cite_repl, src)

    # ---- figures: number in order of appearance, prefix captions ----
    def number_float(src, env, prefix, counter_name):
        pat = re.compile(r'\\begin\{' + env + r'\*?\}.*?\\end\{' + env + r'\*?\}',
                         re.DOTALL)
        out, pos, n = [], 0, 0
        for m in pat.finditer(src):
            n += 1
            block = m.group(0)
            for lab in re.findall(r'\\label\{([^}]+)\}', block):
                label_num[lab] = str(n)
            block = block.replace('\\caption{', f'\\caption{{{prefix}~{n}~~', 1)
            out.append(src[pos:m.start()]); out.append(block); pos = m.end()
        out.append(src[pos:])
        print(f'  numbered {n} {counter_name}')
        return ''.join(out)

    src = number_float(src, 'figure', 'Fig.', 'figures')
    src = number_float(src, 'table', 'Table', 'tables')

    # ---- equations: each equation env = 1 number; align = one per row.
    #      Numbers are also rendered into the math itself so the docx shows
    #      the same (N) tags the LaTeX build produces.
    eq_n = 0
    out, pos = [], 0
    for m in re.finditer(r'\\begin\{(equation|align)\}(.*?)\\end\{\1\}', src,
                         re.DOTALL):
        env, body = m.group(1), m.group(2)
        first = eq_n + 1
        for lab in re.findall(r'\\label\{([^}]+)\}', body):
            label_num[lab] = str(first)
        if env == 'align':
            rows = body.split(r'\\')
            tagged = []
            for r_i, r in enumerate(rows):
                eq_n += 1
                tagged.append(r.rstrip() + f' \\qquad\\text{{({eq_n})}}')
            new_body = (' \\\\'.join(tagged))
        else:
            eq_n += 1
            new_body = body.rstrip() + f' \\qquad\\text{{({eq_n})}}\n'
        out.append(src[pos:m.start()])
        out.append(f'\\begin{{{env}}}{new_body}\\end{{{env}}}')
        pos = m.end()
    out.append(src[pos:])
    src = ''.join(out)
    print(f'  counted {eq_n} numbered equations (numbers rendered in-math)')

    # ---- table* -> table: pandoc drops captions of starred floats ----
    src = src.replace(r'\begin{table*}', r'\begin{table}')
    src = src.replace(r'\end{table*}', r'\end{table}')
    src = src.replace(r'\begin{figure*}', r'\begin{figure}')
    src = src.replace(r'\end{figure*}', r'\end{figure}')

    # ---- \textcircled{N} -> precomposed circled digits (Word-safe) ----
    for digit, glyph in (('1', '\u2460'), ('2', '\u2461'), ('3', '\u2462')):
        src = src.replace(r'\textcircled{' + digit + '}', glyph)

    # ---- sections/subsections: number headings and record labels.
    #      Titles may contain nested braces (\texorpdfstring), so the end of
    #      each title is found by balanced-brace scanning, and the number is
    #      injected right after the opening brace without touching the title.
    def sec_scan_and_number(src):
        pat = re.compile(r'\\(section|subsection)(\*)?\{')
        out, pos = [], 0
        nums = [0, 0]
        for m in pat.finditer(src):
            if m.start() < pos:
                continue
            out.append(src[pos:m.start()])
            level, star = m.group(1), m.group(2)
            # find balanced closing brace of the title
            depth, i = 1, m.end()
            while i < len(src) and depth:
                if src[i] == '{':
                    depth += 1
                elif src[i] == '}':
                    depth -= 1
                i += 1
            head = src[m.start():i]          # full \section{...}
            if star:
                out.append(head)
            else:
                if level == 'section':
                    nums[0] += 1; nums[1] = 0
                    num, shown = f'{nums[0]}', f'{nums[0]}.'
                else:
                    nums[1] += 1
                    num = shown = f'{nums[0]}.{nums[1]}'
                lab = re.match(r'\s*\\label\{([^}]+)\}', src[i:])
                if lab:
                    label_num[lab.group(1)] = num
                head = head[:len(m.group(0))] + f'{shown}~' + head[len(m.group(0)):]
                out.append(head)
            pos = i
        out.append(src[pos:])
        return ''.join(out)
    src = sec_scan_and_number(src)

    # ---- resolve \ref ----
    unresolved = []
    def ref_repl(m):
        key = m.group(1)
        if key in label_num:
            return label_num[key]
        unresolved.append(key)
        return '??'
    src = re.sub(r'\\ref\{([^}]+)\}', ref_repl, src)
    if unresolved:
        print(f'  WARNING: unresolved refs: {sorted(set(unresolved))}')
    else:
        print('  all \\ref resolved')

    # ---- bibliography -> plain numbered References section ----
    src = re.sub(r'\\begin\{thebibliography\}\{[^}]*\}',
                 r'\\section*{References}', src)
    src = src.replace(r'\end{thebibliography}', '')
    n_holder = [0]
    def bib_repl(m):
        n_holder[0] += 1
        return f'\\par {{[}}{n_holder[0]}{{]}} '
    src = re.sub(r'\\bibitem\{[^}]+\}\s*', bib_repl, src)

    return src


ALIGN_ENVS = ('aligned', 'align', 'align*', 'split')

# A multi-line display reaches Word as a single-column OMML matrix, and pandoc
# justifies those rows RIGHT, so the lines of e.g. Eq. (4) end up flush right
# instead of reading as a left-aligned block. Multi-column matrices (the cases
# environments) are already emitted left-justified and must not be touched, so
# the rewrite matches only an <m:mcs> holding exactly one <m:mc>.
SINGLE_COL_MCS = re.compile(
    r'(<m:mcs>\s*<m:mc>\s*<m:mcPr>\s*<m:mcJc m:val=")right("\s*/>\s*'
    r'<m:count m:val="1"\s*/>\s*</m:mcPr>\s*</m:mc>\s*</m:mcs>)')


def left_justify_stacked_math(docx_path: Path) -> int:
    """Rewrite word/document.xml in place so stacked equation rows are
    left-justified. Returns the number of matrices changed."""
    import zipfile

    with zipfile.ZipFile(docx_path) as zf:
        items = [(i, zf.read(i.filename)) for i in zf.infolist()]

    changed = 0
    out = []
    for info, data in items:
        if info.filename == 'word/document.xml':
            xml = data.decode('utf-8')
            xml, changed = SINGLE_COL_MCS.subn(r'\1left\2', xml)
            data = xml.encode('utf-8')
        out.append((info, data))

    tmp = docx_path.with_suffix('.docx.tmp')
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zf:
        for info, data in out:
            zf.writestr(info, data)
    tmp.replace(docx_path)
    return changed


def drop_align_markers(src: str) -> str:
    """pandoc/texmath leaks the '&' column markers of aligned/align/split into
    the Word equation as a literal ampersand ("CRI &= clip(...)"), which is
    what makes multi-line equations look broken in the .docx export. Nested
    cases/array/matrix markers are converted correctly, so only the markers at
    the top level of an align-family body are removed, and only in the pandoc
    temp source -- the LaTeX/Overleaf build keeps its native alignment."""
    out, pos, dropped = [], 0, 0
    pat = re.compile(r'\\begin\{(' + '|'.join(re.escape(e) for e in ALIGN_ENVS) + r')\}')
    while True:
        m = pat.search(src, pos)
        if not m:
            out.append(src[pos:])
            break
        env = m.group(1)
        end_tok = '\\end{' + env + '}'
        end = src.find(end_tok, m.end())
        if end == -1:                       # unbalanced; leave the rest alone
            out.append(src[pos:])
            break
        out.append(src[pos:m.end()])

        # Walk the body, tracking nested \begin/\end so that only the markers
        # belonging to this environment are removed.
        body, depth, i, buf = src[m.end():end], 0, 0, []
        while i < len(body):
            if body.startswith('\\begin{', i):
                depth += 1
            elif body.startswith('\\end{', i):
                depth -= 1
            elif body[i] == '&' and depth == 0 and (i == 0 or body[i - 1] != '\\'):
                dropped += 1
                i += 1
                continue
            buf.append(body[i])
            i += 1
        out.append(''.join(buf))
        out.append(end_tok)
        pos = end + len(end_tok)
    print(f'  dropped {dropped} align markers from math (OMML readability)')
    return ''.join(out)


def strip_for_pandoc(src: str) -> str:
    """Rewrite the few constructs pandoc cannot parse out of the Springer
    Nature template into vanilla LaTeX that pandoc handles."""

    # 1. Replace the \documentclass + sn-jnl preamble with a vanilla article preamble.
    new_preamble = r"""\documentclass[11pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{array}
\usepackage{url}
\usepackage{hyperref}
\usepackage{geometry}
\geometry{margin=1in}

\DeclareMathOperator{\atantwo}{atan2}
"""
    # The original preamble runs from \documentclass to \begin{document}. The
    # lookahead is anchored to the start of a line so that a comment merely
    # mentioning \begin{document} does not truncate the replacement.
    src, n_pre = re.subn(
        r'\\documentclass\[.*?\]\{sn-jnl\}.*?(?=^\\begin\{document\})',
        lambda m: new_preamble,
        src,
        count=1,
        flags=re.DOTALL | re.MULTILINE,
    )
    if n_pre != 1:
        raise SystemExit('preamble replacement failed: could not match '
                         r'\documentclass...\begin{document}')
    # The \atantwo operator is declared by the replacement preamble above; the
    # original declaration went out with the rest of the sn-jnl preamble.

    # 1b. booktabs' \addlinespace is a pure vertical-spacing command, but
    #     pandoc's reader swallows the token that follows it, which silently
    #     blanks the first cell of the next table row. Drop it from the
    #     pandoc source; the LaTeX build keeps the spacing.
    n_als = len(re.findall(r'\\addlinespace(\[[^\]]*\])?', src))
    src = re.sub(r'\\addlinespace(\[[^\]]*\])?\s*', '', src)
    if n_als:
        print(f'  removed {n_als} \\addlinespace spacers (pandoc eats the next cell)')

    # 2. Author/affiliation front matter is injected verbatim after \maketitle
    #    (round-1 docx style: author line with superscripts, affiliation
    #    paragraph, corresponding-author line).
    author_block = ''
    src = src.replace('\\maketitle',
                      '\\maketitle\n\n' + AUTHOR_PAR + '\n\n' + AFFIL_PAR +
                      '\n\n' + CORR_PAR + '\n', 1)

    # 3. Strip out the original \author / \affil declarations + their \email lines.
    src = re.sub(r'\\author\*?\[\d+\][^\n]*\n', '', src)
    src = re.sub(r'\\email\{[^}]*\}', '', src)
    src = re.sub(r'\\affil\[\d+\]\{.*?\}\s*\n', '', src, flags=re.DOTALL)

    # 4. Convert \title[...]{...} -> \title{...}
    src = re.sub(r'\\title\[[^\]]*\]\{', r'\\title{', src)

    # 5. \abstract{...} -> standard abstract environment
    src = re.sub(
        r'\\abstract\{(.+?)\}\s*\n\s*\\keywords',
        lambda m: '\\begin{abstract}' + m.group(1) + '\\end{abstract}\n\\keywords',
        src, flags=re.DOTALL)

    # 6. \keywords{...} -> textual line under abstract
    src = re.sub(
        r'\\keywords\{(.+?)\}',
        lambda m: '\n\\noindent\\textbf{Keywords:} ' + m.group(1) + '\n',
        src)

    # 7. \bmhead{...} (Springer-only) -> \subsubsection*{...}. The paper's
    #    acknowledgements use \bmhead too, like Springer's own sample article,
    #    so no separate environment handling is needed.
    src = re.sub(r'\\bmhead\{([^}]+)\}', r'\n\\subsubsection*{\1}\n', src)

    # 9. Inject the author block right after \title{...} if not already present.
    if author_block and '\\author{' not in src:
        src = re.sub(r'(\\title\{[^}]+\})',
                     lambda m: m.group(1) + '\n' + author_block,
                     src, count=1)

    # 10. Pandoc handles \thebibliography natively (it becomes a numbered list).
    #     Nothing to change there.

    return src


def main():
    if not PANDOC_BIN.exists():
        raise SystemExit(f'pandoc not found at {PANDOC_BIN}')

    print(f'Reading {TEX_IN}')
    src = TEX_IN.read_text(encoding='utf-8')
    print(f'  source length: {len(src):,} chars')

    print('Resolving cross-references, captions, citations...')
    src = resolve_cross_refs(src)

    print('Rewriting for pandoc compatibility...')
    src = drop_align_markers(src)
    src_clean = strip_for_pandoc(src)
    TEX_TMP.write_text(src_clean, encoding='utf-8')
    print(f'  wrote {TEX_TMP}')

    cmd = [
        str(PANDOC_BIN),
        str(TEX_TMP.name),               # use relative name so resource-path resolves
        '-o', str(DOCX_OUT.name),
        '--standalone',
        '--resource-path=.',
        '--from', 'latex',
        '--to',   'docx',
    ]
    print('Running pandoc:', ' '.join(cmd))
    result = subprocess.run(cmd, cwd=PAPER_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        print('STDOUT:', result.stdout[-2000:] if result.stdout else '')
        print('STDERR:', result.stderr[-2000:] if result.stderr else '')
        raise SystemExit(f'pandoc returned {result.returncode}')
    print(f'  pandoc stdout: {result.stdout[-500:] if result.stdout else "(empty)"}')
    print(f'  pandoc stderr: {result.stderr[-500:] if result.stderr else "(empty)"}')
    print(f'  wrote {DOCX_OUT}')

    n_just = left_justify_stacked_math(DOCX_OUT)
    print(f'  left-justified {n_just} stacked equation blocks')

    # Clean up intermediate file
    try:
        TEX_TMP.unlink()
        print(f'  removed {TEX_TMP}')
    except Exception:
        pass

    if DOCX_OUT.exists():
        size_kb = DOCX_OUT.stat().st_size / 1024
        print(f'\nDone: {DOCX_OUT.name}  ({size_kb:.1f} KB)')


if __name__ == '__main__':
    main()
