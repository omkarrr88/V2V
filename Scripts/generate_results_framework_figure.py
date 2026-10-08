"""
generate_results_framework_figure.py
====================================
Produces the analysis-framework flowchart for the Results section: the ten
result subsections grouped into five stages.

The topology is a hub, not a chain, and the drawing says so. Stage 1 feeds
Stage 2 (nothing can be measured before the ground truth is defined), and
Stages 3, 4 and 5 are three independent interrogations of the Stage-2 result,
drawn as a fan-out rather than a sequence. Two dashed arrows carry the
conclusions that flow back into Stage 2: the ablation is where the published
weights are chosen, and the rare-event ceiling is why the physics engine
remains the sole decision-maker.

The canvas is sized to the final printed width of a Springer two-column
page-wide float, so the lettering prints at its nominal point size instead of
being shrunk by \\includegraphics.

Addresses Reviewer 1 (Round 3, point 2).

Output: Outputs/figures/fig17_results_framework.png
        paper/fig17_results_framework.png
"""
import shutil
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.lines import Line2D
from matplotlib.path import Path as MplPath

PROJ  = Path(__file__).resolve().parent.parent
OUT   = PROJ / 'Outputs' / 'figures' / 'fig17_results_framework.png'
PAPER = PROJ / 'paper' / 'fig17_results_framework.png'

# Final printed size of a page-wide float in the Springer two-column layout
# (\textwidth is about 17.4 cm there). The canvas is drawn at that size and
# included at width=\textwidth, so every point size below is also the size the
# lettering prints at -- nothing is shrunk by \includegraphics.
FIG_W_IN = 6.9

# High-contrast palette (Reviewer 1, Round 2 point 6): a saturated edge colour
# over a pale fill of the same hue, so the figure stays legible in greyscale
# and under colour-vision deficiency.
BLACK, GREY_F = '#1a1a1a', '#e9e9e9'
BLUE,  BLUE_F = '#0b3d91', '#dce7f8'
PURP,  PURP_F = '#7a1b6b', '#f3dbf1'
GREEN, GREEN_F = '#0a6b4a', '#d6efe5'
ORANGE, ORANGE_F = '#9c3b00', '#fce5d2'

# Row 1: Stage 1 and Stage 2, side by side, sequential.
# Row 2: Stages 3, 4 and 5, side by side, each a branch off Stage 2.
ROW1 = [
    dict(num='1', title='Validity of the\nmeasuring stick', edge=BLACK, fill=GREY_F,
         w=0.33,
         rows=[('7.1', 'Ground truth',
                'Tier 1: 27 SUMO collisions\n'
                '(label-independent)\n'
                'Tier 2: kinematic proxy\n'
                '(shares inputs with CRI)')]),
    dict(num='2', title='How well does the engine detect?', edge=BLUE, fill=BLUE_F,
         w=0.67,
         rows=[('7.2', 'Overall performance',
                'AUC with 95% CI, pairwise significance'),
               ('7.3', 'Calibration discipline',
                'held-out 75/25 split rules out leakage'),
               ('7.4', 'ROC and PR analysis',
                'full threshold sweep behind the AUC')]),
]
ROW2 = [
    dict(num='3', title='Is a learned model\na better choice?', edge=PURP, fill=PURP_F,
         rows=[('7.5', 'Exploratory AI model',
                'XGBoost, per-class\nrecall, SHAP check'),
               ('7.6', 'Other ML methods',
                'RF / LightGBM / LogReg,\ncost-sensitive thresholds')]),
    dict(num='4', title='Does the result survive\na change of conditions?', edge=GREEN, fill=GREEN_F,
         rows=[('7.7', 'Per-scenario performance',
                'Normal / TSV / HNR,\nspeed-CRI, calibration'),
               ('7.8', 'Multi-seed robustness',
                'six random traffic seeds,\ncross-seed spread')]),
    dict(num='5', title='Why does it work, and\nwhere does it break?', edge=ORANGE, fill=ORANGE_F,
         rows=[('7.9', 'Ablation study',
                'vary the weight\nconfiguration A1-A5'),
               ('7.10', 'Sensitivity analysis',
                'GPS noise, PLR,\nthresholds, friction')]),
]

# Geometry, in axes units (1 unit = FIG_W_IN / TOTAL_W inches).
TOTAL_W = 12.0
COL_GAP = 0.30
HEAD_H1, HEAD_H2 = 0.62, 0.86   # header height, row 1 / row 2 (2-line titles)
CARD_H1, CARD_H2 = 0.90, 1.02
CARD_GAP = 0.12
PAD = 0.14
INSET = 0.13
ROW_GAP = 1.55                  # vertical space for the fan-out arrows

FS_STAGE  = 7.0                 # stage title
FS_BADGE  = 7.6
FS_SEC    = 7.4                 # subsection number
FS_NAME   = 6.9                 # subsection name
FS_DETAIL = 6.3                 # subsection detail (Springer floor is ~6 pt)
FS_EDGE   = 6.6                 # arrow labels / legend


def band(ax, x0, y_top, w, h, stage, head_h, card_h, two_line_title):
    ax.add_patch(FancyBboxPatch(
        (x0, y_top - h), w, h,
        boxstyle='round,pad=0,rounding_size=0.10',
        facecolor=stage['fill'], edgecolor=stage['edge'], linewidth=1.3, zorder=1))

    bx, by = x0 + 0.16, y_top - 0.12 - 0.34
    ax.add_patch(FancyBboxPatch(
        (bx, by), 0.34, 0.34,
        boxstyle='round,pad=0,rounding_size=0.07',
        facecolor=stage['edge'], edgecolor=stage['edge'], linewidth=1.0, zorder=3))
    ax.text(bx + 0.17, by + 0.17, stage['num'], ha='center', va='center',
            fontsize=FS_BADGE, fontweight='bold', color='white', zorder=4)
    ax.text(bx + 0.46, by + 0.34 if two_line_title else by + 0.17, stage['title'],
            ha='left', va='top' if two_line_title else 'center',
            fontsize=FS_STAGE, fontweight='bold', color=stage['edge'],
            linespacing=1.28, zorder=4)

    centres = {}
    cy = y_top - head_h - PAD
    for sec, name, detail in stage['rows']:
        cx0, cw = x0 + INSET, w - 2 * INSET
        ax.add_patch(FancyBboxPatch(
            (cx0, cy - card_h), cw, card_h,
            boxstyle='round,pad=0,rounding_size=0.07',
            facecolor='white', edgecolor=stage['edge'], linewidth=0.9, zorder=2))
        ax.text(cx0 + 0.12, cy - 0.13, sec, ha='left', va='top',
                fontsize=FS_SEC, fontweight='bold', color=stage['edge'], zorder=4)
        ax.text(cx0 + 0.76, cy - 0.13, name, ha='left', va='top',
                fontsize=FS_NAME, color='#111111', zorder=4)
        ax.text(cx0 + 0.12, cy - 0.40, detail, ha='left', va='top',
                fontsize=FS_DETAIL, color='#454545', style='italic',
                linespacing=1.38, zorder=4)
        centres[sec] = cy - card_h / 2
        cy -= card_h + CARD_GAP
    return centres


def elbow(ax, verts, color, dashed=False, lw=1.3, ms=11):
    ax.add_patch(FancyArrowPatch(
        path=MplPath(verts, [MplPath.MOVETO] + [MplPath.LINETO] * (len(verts) - 1)),
        arrowstyle='-|>', mutation_scale=ms,
        facecolor=color, edgecolor=color, lw=lw,
        linestyle=(0, (4, 2.5)) if dashed else 'solid',
        joinstyle='miter', zorder=6))


def badge(ax, x, y, text, color):
    ax.add_patch(FancyBboxPatch(
        (x - 0.13, y - 0.13), 0.26, 0.26,
        boxstyle='circle,pad=0',
        facecolor='white', edgecolor=color, linewidth=1.2, zorder=8))
    ax.text(x, y, text, ha='center', va='center', fontsize=FS_EDGE,
            fontweight='bold', color=color, zorder=9)


def main():
    h1 = HEAD_H1 + 1 * CARD_H1 + 2 * PAD
    h2_top = HEAD_H1 + 3 * CARD_H1 + 2 * CARD_GAP + 2 * PAD
    row1_h = max(h1, h2_top)
    row2_h = HEAD_H2 + 2 * CARD_H2 + CARD_GAP + 2 * PAD

    y_r1 = row2_h + ROW_GAP + row1_h          # top of row 1
    y_r2 = row2_h                              # top of row 2
    legend_y = -0.40
    note_y = legend_y - 0.40
    total_h = y_r1

    x_lo, x_hi = -0.60, TOTAL_W + 0.60
    span_x, span_y = x_hi - x_lo, (total_h + 0.15) - (note_y - 0.52)
    fig, ax = plt.subplots(figsize=(FIG_W_IN, FIG_W_IN * span_y / span_x))
    # Let the axes fill the canvas, so one axes unit is exactly
    # FIG_W_IN / span_x inches and the point sizes above really are the sizes
    # the lettering prints at. With the default subplot margins the drawing
    # would be squeezed into 77% of the width and every box would be
    # correspondingly narrower than the font sizes assume.
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    ax.set_xlim(x_lo, x_hi)
    ax.set_ylim(note_y - 0.52, total_h + 0.15)
    ax.axis('off')

    # ---- row 1: Stage 1 -> Stage 2 -------------------------------------
    x = 0.0
    r1_boxes, card_y = [], {}
    for st in ROW1:
        w = st['w'] * (TOTAL_W - COL_GAP)
        ch = (row1_h - HEAD_H1 - 2 * PAD - (len(st['rows']) - 1) * CARD_GAP) / len(st['rows'])
        card_y.update(band(ax, x, y_r1, w, row1_h, st, HEAD_H1, ch, two_line_title=True))
        r1_boxes.append((x, w))
        x += w + COL_GAP

    (x1, w1), (x2, w2) = r1_boxes
    elbow(ax, [(x1 + w1 + 0.03, y_r1 - row1_h / 2), (x2 - 0.03, y_r1 - row1_h / 2)],
          BLACK, lw=1.6, ms=13)

    # ---- row 2: Stages 3, 4, 5 ------------------------------------------
    w3 = (TOTAL_W - 2 * COL_GAP) / 3.0
    r2_x = []
    for i, st in enumerate(ROW2):
        xi = i * (w3 + COL_GAP)
        band(ax, xi, y_r2, w3, row2_h, st, HEAD_H2, CARD_H2, two_line_title=True)
        r2_x.append(xi)

    # ---- fan-out from Stage 2 into each of Stages 3, 4, 5 ---------------
    hub_x = x2 + w2 / 2
    bus_y = y_r2 + ROW_GAP * 0.62
    # Plain connector from the Stage-2 band down to the fan-out bus. Drawn as
    # a Line2D rather than an arrow: FancyArrowPatch with mutation_scale=0
    # divides by zero while placing the head and renders nothing at all.
    ax.add_line(Line2D([hub_x, hub_x], [y_r1 - row1_h - 0.03, bus_y],
                       color=BLACK, lw=1.6, solid_capstyle='butt', zorder=6))
    for xi in r2_x:
        tx = xi + w3 / 2
        elbow(ax, [(hub_x, bus_y), (tx, bus_y), (tx, y_r2 + 0.03)],
              BLACK, lw=1.6, ms=13)
    # Centred in the clear span between the feedback riser and the hub riser.
    ax.text((x2 - COL_GAP / 2 + hub_x) / 2, bus_y + 0.09,
            'tested three independent ways',
            ha='center', va='bottom', fontsize=FS_EDGE, color=BLACK, style='italic',
            zorder=7)

    # ---- feedback 1: Stage 3 -> Stage 2, up the inter-band gap ----------
    # The arrowhead lands on card 7.2, which is the subsection note 1 names.
    gap_x = x2 - COL_GAP / 2
    y_fb1 = y_r2 + 0.56
    y_in1 = card_y['7.2']
    elbow(ax, [(r2_x[0] + 0.30, y_r2 + 0.02), (r2_x[0] + 0.30, y_fb1),
               (gap_x, y_fb1), (gap_x, y_in1), (x2 + INSET, y_in1)],
          PURP, dashed=True)
    badge(ax, gap_x, (y_fb1 + y_in1) / 2, '1', PURP)

    # ---- feedback 2: Stage 5 -> Stage 2, up the right margin ------------
    # The arrowhead lands on card 7.3, the subsection note 2 names.
    lane_r = TOTAL_W + 0.30
    y_fb2 = y_r2 + 0.56
    y_in2 = card_y['7.3']
    elbow(ax, [(r2_x[2] + w3 - 0.30, y_r2 + 0.02), (r2_x[2] + w3 - 0.30, y_fb2),
               (lane_r, y_fb2), (lane_r, y_in2), (x2 + w2 - INSET, y_in2)],
          ORANGE, dashed=True)
    badge(ax, lane_r, (y_fb2 + y_in2) / 2, '2', ORANGE)

    # ---- legend + the two feedback notes --------------------------------
    elbow(ax, [(0.05, legend_y), (0.70, legend_y)], BLACK, lw=1.5, ms=11)
    ax.text(0.80, legend_y, 'dependency', ha='left', va='center',
            fontsize=FS_EDGE, color=BLACK)
    lx = TOTAL_W * 0.26
    elbow(ax, [(lx, legend_y), (lx + 0.65, legend_y)], '#555555',
          dashed=True, lw=1.4, ms=11)
    ax.text(lx + 0.75, legend_y,
            'feedback: a later subsection constrains an earlier one',
            ha='left', va='center', fontsize=FS_EDGE, color='#555555')

    badge(ax, 0.17, note_y, '1', PURP)
    ax.text(0.42, note_y,
            'the rare-event ceiling found in 7.6 keeps the physics engine the '
            'sole decision-maker behind 7.2',
            ha='left', va='center', fontsize=FS_EDGE, color=PURP, zorder=7)
    badge(ax, 0.17, note_y - 0.36, '2', ORANGE)
    ax.text(0.42, note_y - 0.36,
            r'the ablation in 7.9 chooses the published $\alpha,\beta,\gamma$, '
            'which 7.3 then re-checks on a held-out partition',
            ha='left', va='center', fontsize=FS_EDGE, color=ORANGE, zorder=7)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=400, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    shutil.copyfile(OUT, PAPER)
    print(f'Saved {OUT}')
    print(f'Saved {PAPER}')


if __name__ == '__main__':
    main()
