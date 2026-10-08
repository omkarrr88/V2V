"""
make_overleaf_bundle.py
=======================
Assemble a self-contained Overleaf project from paper/ and zip it.

Overleaf needs every file the manuscript references in one place, and the
class file is not something pdflatex can find on its own. This collects:

  main.tex                    the manuscript
  sn-jnl.cls                  the Springer Nature journal class
  <19 figures>.png            every file main.tex \\includegraphics
  README.txt                  upload instructions and the format caveat

into paper/overleaf/ and paper/overleaf.zip. Both are build outputs and are
gitignored; re-run this after any change to paper/main.tex or the figures.

Upload paper/overleaf.zip via Overleaf's "New Project -> Upload Project".
"""
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJ   = Path(__file__).resolve().parent.parent
PAPER  = PROJ / 'paper'
OUTDIR = PAPER / 'overleaf'
OUTZIP = PAPER / 'overleaf.zip'

TEX = 'main.tex'
CLS = 'sn-jnl.cls'

README = """\
Overleaf upload bundle -- V2V blind-spot manuscript
===================================================

Created by Scripts/make_overleaf_bundle.py. Do not edit files here by hand:
paper/main.tex is the source of truth, and this folder is regenerated from it.

HOW TO UPLOAD
-------------
Overleaf -> New Project -> Upload Project -> choose paper/overleaf.zip
Then check Menu -> Main document is set to main.tex.

ABOUT sn-jnl.cls  (read this first)
-----------------------------------
The copy included here declares the three options main.tex uses
(sn-mathphys-num, Numbered, iicol), but it is a mirror copy, not necessarily
byte-identical to the one that produced your V2V_paper 17-08-26.pdf.

If your existing Overleaf project still has a sn-jnl.cls that compiled that
PDF, prefer that one -- it guarantees identical formatting. Just delete the
sn-jnl.cls from this bundle after uploading and keep yours.

Sanity check after the first successful compile: the 17-08-26 build was
20 pages, two-column. The Round-3 revision adds one page-wide figure (Fig. 8)
and one page-wide table (Table 3), so expect a slightly longer document in the
same layout.

BIBLIOGRAPHY
------------
main.tex uses a manual \\begin{thebibliography} list with 32 \\bibitem entries,
so BibTeX is not required and no .bst file is needed. The class emits
\\bibliographystyle{sn-mathphys-num} into the .aux; that is harmless. If
Overleaf ever complains about a missing style, drop your own
sn-mathphys-num.bst into the project root.

IF THE COMPILE FAILS INSIDE sn-jnl.cls
--------------------------------------
Errors reported at sn-jnl.cls lines (Undefined control sequence, Missing
\\begin{document}, "The font size command \\normalsize is not defined",
"Loading a class or package in a group") mean the class is not being loaded
as a class. In order of likelihood:

  1. Menu -> Main document is not main.tex. Set it.
  2. sn-jnl.cls uploaded truncated. Re-upload it.
  3. TeX Live version. Menu -> Settings -> TeX Live version -> 2025.
     The 17-08-26 PDF was built with pdfTeX 1.40.27 / TeX Live 2025.

To isolate it, compile this four-line file as the main document:

    \\documentclass[sn-mathphys-num,Numbered,iicol]{sn-jnl}
    \\begin{document}
    Hello.
    \\end{document}

If that fails too, the problem is the project or the class, not the paper.

FILE LIST
---------
"""


def normalise_eol(src: Path, dst: Path) -> str:
    """Write src to dst with LF line endings. The mirrored sn-jnl.cls ships
    with CR-only terminators, which TeX on Linux reads as a single line --
    the whole class would be swallowed by its own leading comment."""
    raw = src.read_bytes()
    cr, lf = raw.count(b'\r'), raw.count(b'\n')
    text = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    dst.write_bytes(text)
    out = text.count(b'\n')
    return f'in CR={cr} LF={lf}  ->  out CR=0 LF={out}'


def main():
    tex_path = PAPER / TEX
    cls_path = PAPER / CLS
    for p in (tex_path, cls_path):
        if not p.exists():
            raise SystemExit(f'missing required file: {p}')

    figs = re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}',
                      tex_path.read_text(encoding='utf-8'))
    figs = sorted(set(figs))
    missing = [f for f in figs if not (PAPER / f).exists()]
    if missing:
        raise SystemExit(f'figures referenced but not in paper/: {missing}')

    if OUTDIR.exists():
        shutil.rmtree(OUTDIR)
    OUTDIR.mkdir(parents=True)

    # Text files are normalised rather than copied: git on Windows checks them
    # out with CRLF, and the mirrored class originally shipped CR-only.
    print('  ' + TEX + ': ' + normalise_eol(tex_path, OUTDIR / TEX))
    print('  ' + CLS + ': ' + normalise_eol(cls_path, OUTDIR / CLS))
    for f in figs:
        shutil.copy2(PAPER / f, OUTDIR / f)

    listing = '\n'.join(f'  {n}' for n in [TEX, CLS, 'README.txt'] + figs)
    (OUTDIR / 'README.txt').write_text(README + listing + '\n', encoding='utf-8')

    names = sorted(p.name for p in OUTDIR.iterdir())
    if OUTZIP.exists():
        OUTZIP.unlink()
    with zipfile.ZipFile(OUTZIP, 'w', zipfile.ZIP_DEFLATED) as z:
        for n in names:
            z.write(OUTDIR / n, n)

    total = sum((OUTDIR / n).stat().st_size for n in names)
    print(f'{OUTDIR}  ({len(names)} files, {total/1e6:.1f} MB)')
    print(f'  main.tex   {(OUTDIR / TEX).stat().st_size:,} bytes')
    print(f'  sn-jnl.cls {(OUTDIR / CLS).stat().st_size:,} bytes')
    print(f'  figures    {len(figs)}')
    print(f'{OUTZIP}  ({OUTZIP.stat().st_size/1e6:.1f} MB)')


if __name__ == '__main__':
    main()
