"""
generate_scenario_diagram.py
============================
Produces a scenario-level illustration of the lane-change blind-spot problem
that V2V solves: a truck physically occludes the line-of-sight between the
ego sedan and a target sedan in the adjacent lane. The truck blocks radar
and camera, but BSM packets from the target sedan reach the ego because they
propagate around the obstruction via DSRC/C-V2X radio.

Addresses Reviewer 1 (point 1) and Reviewer 3 (point 1).

Output: Outputs/figures/fig0_scenario_diagram.png
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyArrowPatch, Rectangle, FancyBboxPatch
from pathlib import Path

OUT = '../Outputs/figures/fig0_scenario_diagram.png'


def draw_vehicle(ax, x, y, w, h, color, label, label_color='black', label_above=True,
                 hatch=None, edgecolor='black', alpha=1.0, badge=None):
    rect = Rectangle((x - w/2, y - h/2), w, h, facecolor=color, edgecolor=edgecolor,
                     linewidth=1.5, hatch=hatch, zorder=3, alpha=alpha)
    ax.add_patch(rect)
    # Wheels (simple dots)
    for dx in [-w*0.35, w*0.35]:
        for dy in [-h*0.40, h*0.40]:
            ax.plot(x+dx, y+dy, marker='o', markersize=5, color='black',
                    zorder=4, alpha=alpha)
    # Label
    if label:
        ly = y + h/2 + 0.45 if label_above else y - h/2 - 0.55
        ax.text(x, ly, label, ha='center', va='center', fontsize=10,
                color=label_color, fontweight='bold')
    # Numbered sequence badge (white circle, centred on the vehicle body)
    if badge:
        ax.plot(x, y, marker='o', markersize=15, markerfacecolor='white',
                markeredgecolor='black', markeredgewidth=1.3, zorder=5)
        ax.text(x, y, badge, ha='center', va='center', fontsize=10,
                fontweight='bold', color='black', zorder=6)


def draw_speed_arrow(ax, x0, y, length, label, color, label_dy=0.32):
    """Forward driving-direction arrow with a speed label above it."""
    arr = FancyArrowPatch((x0, y), (x0 + length, y),
                          arrowstyle='-|>', mutation_scale=15,
                          color=color, lw=2.0, zorder=4)
    ax.add_patch(arr)
    ax.text(x0 + length/2, y + label_dy, label, ha='center', va='center',
            fontsize=8.5, color=color, fontweight='bold')


def draw_packet(ax, x0, y0, x1, y1, label='', color='#1f77b4', label_y_offset=0.7):
    arrow = FancyArrowPatch((x0, y0), (x1, y1),
                            arrowstyle='-|>', mutation_scale=14,
                            color=color, lw=1.6, linestyle='--',
                            connectionstyle='arc3,rad=-0.35', zorder=2)
    ax.add_patch(arrow)
    if label:
        mx, my = (x0+x1)/2, max(y0, y1) + label_y_offset
        ax.text(mx, my, label, ha='center', va='center', fontsize=9,
                color=color, style='italic', fontweight='bold',
                bbox=dict(facecolor='white', edgecolor=color, boxstyle='round,pad=0.2', alpha=0.95))


def draw_los_blocked(ax, x0, y0, x1, y1, label_xy=None):
    """Dashed red line from ego eye-line to target, with X mark over the truck."""
    ax.plot([x0, x1], [y0, y1], linestyle=':', color='#c0392b', lw=1.4, zorder=1)
    if label_xy is None:
        label_xy = ((x0+x1)/2, (y0+y1)/2)
    ax.text(label_xy[0], label_xy[1], 'LOS BLOCKED', ha='center', va='center',
            fontsize=8, color='#c0392b', fontweight='bold',
            bbox=dict(facecolor='white', edgecolor='#c0392b', boxstyle='round,pad=0.2'))


def main():
    fig, ax = plt.subplots(figsize=(14, 7.0))
    ax.set_xlim(-0.5, 24)
    ax.set_ylim(-0.5, 8.5)
    ax.set_aspect('equal')

    # --- Road surface ---
    road_left, road_right = -0.5, 15.5
    road = Rectangle((road_left, 0.5), road_right - road_left, 4,
                     facecolor='#e0e0e0', edgecolor=None, zorder=0)
    ax.add_patch(road)
    # Lane dividers (dashed white)
    for y in [2.0, 3.0]:
        ax.plot([road_left, road_right], [y, y], linestyle=(0, (8, 6)),
                color='white', lw=1.5, zorder=1)
    # Solid road edges
    ax.plot([road_left, road_right], [0.5, 0.5], color='#555555', lw=1.5)
    ax.plot([road_left, road_right], [4.5, 4.5], color='#555555', lw=1.5)
    # Lane labels OUTSIDE the road area (left edge, vertical alignment with each lane)
    ax.text(road_left - 0.15, 4.00, 'Lane 1', fontsize=10, color='#555555',
            ha='right', va='center', fontweight='bold')
    ax.text(road_left - 0.15, 2.50, 'Lane 2 (ego)', fontsize=10, color='#555555',
            ha='right', va='center', fontweight='bold')
    ax.text(road_left - 0.15, 1.00, 'Lane 3 (adjacent)', fontsize=10, color='#555555',
            ha='right', va='center', fontweight='bold')

    # --- Vehicles ---
    # Layout (left to right): truck (lane 2) ... target (lane 3) ... ego (lane 2)
    truck_x = 4.0
    tgt_x   = 7.5
    ego_x   = 11.5

    # Ghost positions of the target: movement sequence t0 -> t1 -> t2.
    # t0: behind the truck (occluded), t1: overtaking alongside the truck,
    # t2 (solid vehicle below): at the truck's right-front = ego's blind spot.
    draw_vehicle(ax, x=1.3, y=1.4, w=1.8, h=0.8, color='#d62728',
                 label='', alpha=0.30, badge='1')
    draw_vehicle(ax, x=4.4, y=1.4, w=1.8, h=0.8, color='#d62728',
                 label='', alpha=0.55, badge='2')

    draw_vehicle(ax, x=truck_x, y=2.5, w=3.0, h=0.9, color='#7f7f7f',
                 label='Occluding truck', label_above=True, hatch='//')
    draw_vehicle(ax, x=tgt_x, y=1.4, w=1.8, h=0.8, color='#d62728',
                 label='', badge='3')
    # Target label placed clearly below the road edge (no overlap with the
    # road boundary line at y=0.5)
    ax.text(tgt_x, 0.22, 'Target (in ego blind spot)', ha='center', va='center',
            fontsize=10, color='black', fontweight='bold')
    draw_vehicle(ax, x=ego_x, y=2.5, w=1.8, h=0.8, color='#1f77b4',
                 label='Ego (sedan)', label_above=True)

    # Trajectory of the target along the adjacent lane (t0 -> t2)
    traj = FancyArrowPatch((2.3, 1.4), (6.45, 1.4),
                           arrowstyle='-|>', mutation_scale=16,
                           color='#8B0000', lw=2.2, linestyle=(0, (5, 3)),
                           zorder=2)
    ax.add_patch(traj)
    ax.text(3.3, 0.68, 'approaches at 28 m/s (high speed)',
            ha='center', va='center', fontsize=8.5, color='#8B0000',
            style='italic', fontweight='bold')

    # --- Driving-direction arrows with speeds (all traffic moves left-to-right) ---
    draw_speed_arrow(ax, x0=5.65, y=2.5, length=1.25, label='12 m/s', color='#404040')
    draw_speed_arrow(ax, x0=12.55, y=2.5, length=1.25, label='15 m/s', color='#1f77b4')
    # Global direction-of-travel indicator under the road
    dir_arr = FancyArrowPatch((0.0, 0.12), (2.6, 0.12),
                              arrowstyle='-|>', mutation_scale=14,
                              color='#404040', lw=1.6, zorder=2)
    ax.add_patch(dir_arr)
    ax.text(1.3, -0.28, 'direction of travel', ha='center', va='center',
            fontsize=8.5, color='#404040', style='italic')

    # --- Movement-sequence legend (upper-left empty area) ---
    leg = FancyBboxPatch((0.0, 5.30), 7.35, 1.95, boxstyle='round,pad=0.10',
                         facecolor='#f8f9fa', edgecolor='#404040', lw=1.2, zorder=3)
    ax.add_patch(leg)
    leg_lines = [
        (r'Target movement sequence ($t_0 \rightarrow t_1 \rightarrow t_2$):', True),
        ('① $t_0$: hidden behind the truck, occluded from ego sensors', False),
        ('② $t_1$: overtakes at 28 m/s in the adjacent lane', False),
        ('③ $t_2$: reaches truck’s right-front = ego’s blind spot', False),
    ]
    ly = 6.95
    for text, bold in leg_lines:
        ax.text(0.25, ly, text, ha='left', va='center', fontsize=9.5,
                fontweight='bold' if bold else 'normal', zorder=4)
        ly -= 0.47

    # --- LOS blocked indicator (drawn first, low z-order, so vehicles render on top) ---
    # Label sits directly on the dotted line, midway between ego and target.
    draw_los_blocked(ax, x0=ego_x - 1.0, y0=2.5, x1=tgt_x + 1.0, y1=1.4,
                     label_xy=(9.55, 2.08))

    # --- BSM packet (V2V, arcs ABOVE the road to clearly miss the truck) ---
    draw_packet(ax, x0=tgt_x, y0=1.4 + 0.5,
                x1=ego_x, y1=2.5 + 0.5,
                label='', label_y_offset=2.3)
    ax.text(10.3, 5.35, 'BSM {x, y, v, a, d}  @ 10 Hz',
            ha='center', va='center', fontsize=9, color='#1f77b4',
            style='italic', fontweight='bold',
            bbox=dict(facecolor='white', edgecolor='#1f77b4',
                      boxstyle='round,pad=0.2', alpha=0.95))

    # --- Ego sensor failure note (compact, in the empty Lane 1 strip above
    #     truck, with a connector arrow down to the occluding truck) ---
    ax.text(truck_x, 4.12, 'Onboard radar / camera blocked',
            ha='center', va='center', fontsize=9, color='#c0392b',
            fontweight='bold',
            bbox=dict(facecolor='white', edgecolor='#c0392b',
                      boxstyle='round,pad=0.2', alpha=0.95))
    conn = FancyArrowPatch((truck_x, 3.92), (truck_x, 3.05),
                           arrowstyle='-|>', mutation_scale=12,
                           color='#c0392b', lw=1.2, zorder=2)
    ax.add_patch(conn)

    # --- Lane-change intent arrow on ego (placed on the FAR side of the ego,
    #     to the right, so it does not overlap the LOS line or the LOS label). ---
    arr_x = ego_x + 1.3
    arr = FancyArrowPatch((arr_x, 2.5 - 0.20), (arr_x, 1.4 + 0.30),
                          arrowstyle='-|>', mutation_scale=18,
                          color='#1f77b4', lw=1.8, zorder=4)
    ax.add_patch(arr)
    ax.text(arr_x + 0.25, 1.95, 'lane-change\nintent', fontsize=9, color='#1f77b4',
            ha='left', va='center', style='italic', fontweight='bold')

    # --- Processing pipeline boxes on the right ---
    box_x = 16.5
    box_w = 6.8
    box_h = 1.10
    gap   = 0.40

    boxes = [
        ('1. BSM received\nover DSRC / C-V2X', '#d4eaf7'),
        ('2. CRI engine\nseverity-gated computation', '#fff3cd'),
        ('3. Alert: WARNING\n(right blind spot)', '#f5cba7'),
    ]
    centres = []
    yb = 6.8
    for label, col in boxes:
        bbox = FancyBboxPatch((box_x, yb - box_h/2), box_w, box_h,
                              boxstyle='round,pad=0.05',
                              facecolor=col, edgecolor='black', lw=1.4, zorder=3)
        ax.add_patch(bbox)
        ax.text(box_x + box_w/2, yb, label, ha='center', va='center', fontsize=11,
                fontweight='bold')
        centres.append((box_x + box_w/2, yb))
        yb -= box_h + gap

    # Connecting arrows between pipeline boxes
    for i in range(len(centres) - 1):
        cx, cy = centres[i]
        nx, ny = centres[i+1]
        arr = FancyArrowPatch((cx, cy - box_h/2), (nx, ny + box_h/2),
                              arrowstyle='-|>', mutation_scale=16,
                              color='black', lw=1.3, zorder=4)
        ax.add_patch(arr)

    # Arrow from BSM packet endpoint into pipeline
    arr = FancyArrowPatch((ego_x + 1.0, 2.5 + 0.5), (box_x - 0.1, 6.8),
                          arrowstyle='-|>', mutation_scale=16,
                          color='#1f77b4', lw=1.5, linestyle='--', zorder=2)
    ax.add_patch(arr)

    # --- CRI score readout under the pipeline ---
    cri_y = centres[-1][1] - box_h - 0.8
    ax.text(box_x + box_w/2, cri_y, r'CRI $\geq$ 0.60  $\Rightarrow$  WARNING',
            ha='center', fontsize=12, color='#a04000', fontweight='bold',
            bbox=dict(facecolor='#fdf2e9', edgecolor='#a04000',
                      boxstyle='round,pad=0.4'))
    ax.text(box_x + box_w/2, cri_y - 0.9,
            r'$\alpha R_{\mathrm{decel}} + \beta R_{\mathrm{TTC}}$  with severity gate',
            ha='center', fontsize=9.5, color='#555555', style='italic')

    # No in-image title: the LaTeX \caption carries the full description, and a
    # duplicated title inside the bitmap competes with it in the typeset paper.

    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    Path(os.path.dirname(OUT)).mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=300, bbox_inches='tight')
    print(f'Saved scenario diagram: {OUT}')
    plt.close(fig)


if __name__ == '__main__':
    main()
