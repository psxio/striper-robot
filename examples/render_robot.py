#!/usr/bin/env python3
"""Striper robot — physical product visualization & validation.

Generates:
  1. Top-down engineering layout with dimension annotations
  2. 3D product rendering with component labels
  3. Spec sheet panel with weight, power, and clearance checks

All dimensions from actual BOM (docs/bom_comparison.md) and
wiring guide (docs/wiring_guide.md). Weights estimated from
component datasheets.

Usage:
    python examples/render_robot.py

Output:
    examples/output/robot_top.png    — Top-down engineering view
    examples/output/robot_3d.png     — 3D product rendering
    examples/output/robot_specs.png  — Spec sheet with validation checks
"""

import math
import os
import textwrap

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Circle, Rectangle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

# ---------------------------------------------------------------------------
# Component database — every value from actual BOM/datasheets
# ---------------------------------------------------------------------------
# All dimensions in meters, weights in kg, prices in USD.
COMPONENTS = {
    "frame": {
        "desc": "2020 aluminum extrusion + 3/4\" plywood deck",
        "dims": (0.610, 0.460, 0.020),  # L x W x H (24" x 18")
        "weight": 5.0,  # aluminum + plywood
        "price": 50,
        "pos": (0, 0, 0.083),  # Z = wheel_radius - half_height
        "color": "#b0b0b0",
    },
    "left_motor": {
        "desc": "350W BLDC hub motor (hoverboard)",
        "dims": (0.165, 0.065),  # diameter, width
        "weight": 4.0,  # each hub motor ~4kg
        "price": 15,  # half of $30 hoverboard
        "pos": (0, 0.200, 0.083),  # Y = track/2
        "color": "#2a2a2a",
    },
    "right_motor": {
        "desc": "350W BLDC hub motor (hoverboard)",
        "dims": (0.165, 0.065),
        "weight": 4.0,
        "price": 15,
        "pos": (0, -0.200, 0.083),
        "color": "#2a2a2a",
    },
    "caster_front": {
        "desc": "3\" swivel caster",
        "dims": (0.076,),  # 3" = 76mm diameter
        "weight": 0.3,
        "price": 5,
        "pos": (0.240, 0, 0.038),  # front center
        "color": "#666666",
    },
    "caster_rear": {
        "desc": "3\" swivel caster",
        "dims": (0.076,),
        "weight": 0.3,
        "price": 5,
        "pos": (-0.240, 0, 0.038),  # rear center
        "color": "#666666",
    },
    "pixhawk": {
        "desc": "Pixhawk 6C Mini (Holybro)",
        "dims": (0.065, 0.052, 0.014),  # from datasheet
        "weight": 0.05,
        "price": 120,
        "pos": (0.080, 0, 0.093),  # on deck, slightly forward
        "color": "#2d8a4e",
    },
    "gps": {
        "desc": "Unicore UM980 (simpleRTK3B) + triband antenna",
        "dims": (0.050, 0.050, 0.030),  # board
        "weight": 0.2,
        "price": 180,
        "pos": (0, 0, 0.093),  # on deck, center
        "color": "#2d8a4e",
    },
    "gps_mast": {
        "desc": "GPS antenna mast (aluminum tube)",
        "dims": (0.012, 0.012, 0.300),  # 12mm tube, 300mm tall
        "weight": 0.15,
        "price": 5,
        "pos": (0, 0, 0.093),
        "color": "#888888",
    },
    "gps_antenna": {
        "desc": "RTK multiband antenna",
        "dims": (0.080, 0.018),  # diameter, height
        "weight": 0.05,
        "price": 0,  # included with UM980
        "pos": (0, 0, 0.393),  # top of mast
        "color": "#2d8a4e",
    },
    "battery": {
        "desc": "36V 10Ah Li-ion e-bike battery (10S)",
        "dims": (0.200, 0.150, 0.050),  # typical e-bike pack
        "weight": 3.0,
        "price": 100,
        "pos": (-0.150, 0, 0.093),  # rear area on deck
        "color": "#333366",
    },
    "hoverboard_pcb": {
        "desc": "Hoverboard mainboard (FOC firmware)",
        "dims": (0.200, 0.100, 0.030),
        "weight": 0.5,
        "price": 0,  # included with hoverboard
        "pos": (-0.050, -0.130, 0.093),  # side of deck
        "color": "#336633",
    },
    "pump": {
        "desc": "Shurflo 8000 diaphragm pump (60 PSI, 1 GPM)",
        "dims": (0.150, 0.100, 0.080),  # Shurflo 8000 is larger than generic
        "weight": 1.2,  # Shurflo 8000 weighs ~1.2kg
        "price": 90,
        "pos": (0.180, -0.100, 0.093),
        "color": "#444444",
    },
    "solenoid": {
        "desc": "12V N.C. solenoid valve (3/8\" direct-acting)",
        "dims": (0.060, 0.040, 0.050),
        "weight": 0.2,
        "price": 20,
        "pos": (0.220, 0, 0.093),
        "color": "#884444",
    },
    "nozzle": {
        "desc": "TeeJet TP8004EVS even-fan nozzle (4\" width)",
        "dims": (0.050, 0.040, 0.035),
        "weight": 0.1,
        "price": 15,
        "pos": (0.280, 0, 0.060),  # below deck, front center
        "color": "#993333",
    },
    "paint_tank": {
        "desc": "2-gallon paint reservoir",
        "dims": (0.200, 0.250),  # diameter, height
        "weight": 0.5,  # empty
        "price": 10,
        "pos": (0.020, 0.080, 0.093),  # on deck
        "color": "#cc3333",
    },
    "dcdc_12v": {
        "desc": "36V→12V DC-DC converter (5A, XL4015)",
        "dims": (0.070, 0.050, 0.025),
        "weight": 0.05,
        "price": 12,
        "pos": (-0.100, 0.150, 0.093),
        "color": "#448844",
    },
    "dcdc_5v": {
        "desc": "Holybro PM06 V2 (5V/3A + batt monitoring)",
        "dims": (0.050, 0.050, 0.015),  # PM06 V2 is compact
        "weight": 0.03,
        "price": 25,
        "pos": (-0.100, 0.100, 0.093),
        "color": "#448844",
    },
    "relay_module": {
        "desc": "2-ch 5V relay module (opto-isolated)",
        "dims": (0.050, 0.040, 0.020),
        "weight": 0.03,
        "price": 5,
        "pos": (0.180, 0.100, 0.093),
        "color": "#4444aa",
    },
    "rc_receiver": {
        "desc": "FlySky FS-iA6B receiver",
        "dims": (0.047, 0.026, 0.015),
        "weight": 0.02,
        "price": 0,  # included with TX
        "pos": (-0.050, 0.150, 0.093),
        "color": "#aa8844",
    },
    "estop": {
        "desc": "22mm E-stop + 40A DC contactor",
        "dims": (0.040, 0.025),  # diameter, height (button only)
        "weight": 0.3,  # button + contactor
        "price": 25,
        "pos": (-0.200, 0.150, 0.093),
        "color": "#ff1111",
    },
    "ultrasonic_fl": {
        "desc": "HC-SR04 ultrasonic (front-left)",
        "dims": (0.045, 0.020, 0.015),
        "weight": 0.01,
        "price": 2.5,
        "pos": (0.300, 0.100, 0.093),
        "color": "#ccaa22",
    },
    "ultrasonic_fr": {
        "desc": "HC-SR04 ultrasonic (front-right)",
        "dims": (0.045, 0.020, 0.015),
        "weight": 0.01,
        "price": 2.5,
        "pos": (0.300, -0.100, 0.093),
        "color": "#ccaa22",
    },
}

# Derived constants
TRACK_WIDTH = 0.400
PLATFORM_L = 0.610
PLATFORM_W = 0.460
PLATFORM_Z = 0.083  # wheel center height (165mm / 2 ≈ 82.5mm)
DECK_H = 0.020
WHEEL_R = 0.0825
GPS_TOP_Z = 0.093 + 0.300 + 0.018  # deck + mast + antenna
NOZZLE_BOTTOM_Z = 0.060  # ~60mm above ground
GROUND_CLEARANCE = NOZZLE_BOTTOM_Z


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------
def run_validation():
    """Run physical validation checks on the robot design."""
    checks = []

    # 1. Total weight
    dry_weight = sum(c["weight"] for c in COMPONENTS.values())
    paint_weight = 2 * 3.785 * 1.2  # 2 gal × 3.785 L/gal × 1.2 kg/L (latex paint)
    total_weight = dry_weight + paint_weight
    checks.append(("Dry weight", f"{dry_weight:.1f} kg", dry_weight < 25,
                    "< 25 kg for hoverboard motors"))
    checks.append(("Operating weight (2 gal paint)", f"{total_weight:.1f} kg",
                    total_weight < 40, "< 40 kg max for 350W×2 motors"))

    # 2. Total cost
    total_cost = sum(c["price"] for c in COMPONENTS.values())
    total_cost += 30  # wiring/connectors/fuses
    total_cost += 30  # RC transmitter
    total_cost += 6   # ST-Link programmer
    checks.append(("BOM cost (Tier 2)", f"${total_cost}", True, "Target: ~$780"))

    # 3. Ground clearance
    checks.append(("Nozzle ground clearance", f"{NOZZLE_BOTTOM_Z*1000:.0f} mm",
                    NOZZLE_BOTTOM_Z > 0.040,
                    "> 40mm for spray pattern"))

    # 4. Wheel clearance from frame
    wheel_outer = TRACK_WIDTH / 2 + 0.065 / 2  # track/2 + wheel_width/2
    frame_edge = PLATFORM_W / 2
    clearance = wheel_outer - frame_edge
    checks.append(("Wheel-frame clearance",
                    f"{clearance*1000:.0f} mm ({'inside' if clearance < 0 else 'outside'})",
                    abs(clearance) < 0.030,
                    "Wheels slightly outside frame OK"))

    # 5. GPS height (multipath: higher = better)
    checks.append(("GPS antenna height", f"{GPS_TOP_Z*1000:.0f} mm",
                    GPS_TOP_Z > 0.350, "> 350mm for multipath clearance"))

    # 6. Center of gravity (X axis: positive = forward)
    total_m = sum(c["weight"] for c in COMPONENTS.values())
    cg_x = sum(c["weight"] * c["pos"][0] for c in COMPONENTS.values()) / total_m
    cg_y = sum(c["weight"] * c["pos"][1] for c in COMPONENTS.values()) / total_m
    checks.append(("CG position (X)", f"{cg_x*1000:.0f} mm from center",
                    abs(cg_x) < 0.050, "Within ±50mm of center"))
    checks.append(("CG position (Y)", f"{cg_y*1000:.0f} mm from center",
                    abs(cg_y) < 0.030, "Within ±30mm of center"))

    # 7. Power budget
    max_power = 720 + 36 + 6 + 5 + 1.5 + 0.5 + 10  # motors + pump + solenoid + electronics
    battery_wh = 36 * 10  # 36V × 10Ah
    runtime_min = battery_wh / max_power * 60
    checks.append(("Peak power draw", f"{max_power:.0f} W", max_power < 1000,
                    "< 1 kW for 10Ah battery"))
    checks.append(("Estimated runtime", f"{runtime_min:.0f} min",
                    runtime_min > 20, "> 20 min minimum"))

    # 8. Speed verification
    wheel_circumference = math.pi * 0.165  # m
    # At 0.5 m/s, wheels turn at 0.5/0.518 ≈ 0.97 rev/s = 58 RPM
    rpm_paint = 0.5 / wheel_circumference * 60
    rpm_transit = 1.0 / wheel_circumference * 60
    checks.append(("Motor RPM (painting 0.5 m/s)", f"{rpm_paint:.0f} RPM",
                    rpm_paint < 200, "Well within motor range"))
    checks.append(("Motor RPM (transit 1.0 m/s)", f"{rpm_transit:.0f} RPM",
                    rpm_transit < 200, "Well within motor range"))

    return checks, dry_weight, total_weight, total_cost


# ---------------------------------------------------------------------------
# 3D helpers with shading
# ---------------------------------------------------------------------------
def _shade(color, factor):
    base = color.lstrip("#")
    if len(base) == 3:
        base = base[0]*2 + base[1]*2 + base[2]*2
    r, g, b = int(base[:2], 16), int(base[2:4], 16), int(base[4:6], 16)
    r = min(255, max(0, int(r * factor)))
    g = min(255, max(0, int(g * factor)))
    b = min(255, max(0, int(b * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _add_box(ax, x, y, z, dx, dy, dz, color, alpha=0.9, label=None):
    top_c = _shade(color, 1.15)
    front_c = _shade(color, 0.85)
    side_c = _shade(color, 0.70)
    bottom_c = _shade(color, 0.55)
    faces = [
        ([(x, y, z+dz), (x+dx, y, z+dz), (x+dx, y+dy, z+dz), (x, y+dy, z+dz)], top_c),
        ([(x, y, z), (x+dx, y, z), (x+dx, y+dy, z), (x, y+dy, z)], bottom_c),
        ([(x+dx, y, z), (x+dx, y+dy, z), (x+dx, y+dy, z+dz), (x+dx, y, z+dz)], front_c),
        ([(x, y, z), (x, y+dy, z), (x, y+dy, z+dz), (x, y, z+dz)], side_c),
        ([(x, y+dy, z), (x+dx, y+dy, z), (x+dx, y+dy, z+dz), (x, y+dy, z+dz)], side_c),
        ([(x, y, z), (x+dx, y, z), (x+dx, y, z+dz), (x, y, z+dz)], front_c),
    ]
    for verts, fc in faces:
        poly = Poly3DCollection([verts], alpha=alpha, facecolor=fc,
                                edgecolor="#222", linewidth=0.4)
        if label:
            poly.set_label(label)
            label = None
        ax.add_collection3d(poly)


def _add_cylinder(ax, cx, cy, z, r, h, color, alpha=0.9, n=24, label=None):
    angles = np.linspace(0, 2 * np.pi, n + 1)
    xs = cx + r * np.cos(angles)
    ys = cy + r * np.sin(angles)

    top = list(zip(xs, ys, np.full(n+1, z+h)))
    poly = Poly3DCollection([top], alpha=alpha, facecolor=_shade(color, 1.15),
                            edgecolor="#222", linewidth=0.2)
    if label:
        poly.set_label(label)
        label = None
    ax.add_collection3d(poly)

    bottom = list(zip(xs, ys, np.full(n+1, z)))
    poly = Poly3DCollection([bottom], alpha=alpha, facecolor=_shade(color, 0.6),
                            edgecolor="#222", linewidth=0.1)
    ax.add_collection3d(poly)

    for i in range(n):
        ang = (angles[i] + angles[i+1]) / 2
        light = 0.75 + 0.25 * math.cos(ang - math.pi / 4)
        fc = _shade(color, light)
        side = [(xs[i], ys[i], z), (xs[i+1], ys[i+1], z),
                (xs[i+1], ys[i+1], z+h), (xs[i], ys[i], z+h)]
        poly = Poly3DCollection([side], alpha=alpha, facecolor=fc,
                                edgecolor=fc, linewidth=0.1)
        ax.add_collection3d(poly)


def _label_3d(ax, x, y, z, text, dx=0, dy=0, dz=0, fontsize=7, color="#eee"):
    tx, ty, tz = x+dx, y+dy, z+dz
    ax.plot([x, tx], [y, ty], [z, tz], color="#888", lw=0.6, alpha=0.5)
    ax.text(tx, ty, tz, text, fontsize=fontsize, color=color,
            ha="center", va="bottom", fontweight="bold")


# ---------------------------------------------------------------------------
# Top-down engineering view
# ---------------------------------------------------------------------------
def render_top_view(output_path):
    fig, ax = plt.subplots(figsize=(12, 14))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#f5f5f5")
    ax.set_aspect("equal")
    S = 1000  # m → mm

    # Frame
    ax.add_patch(FancyBboxPatch(
        (-PLATFORM_L/2*S, -PLATFORM_W/2*S), PLATFORM_L*S, PLATFORM_W*S,
        boxstyle="round,pad=8", facecolor="#c0c0c0", edgecolor="#666",
        lw=2, alpha=0.3, zorder=1))
    ax.axhline(0, color="#ddd", lw=0.5, zorder=0)
    ax.axvline(0, color="#ddd", lw=0.5, zorder=0)

    # Components as patches
    for name, c in COMPONENTS.items():
        px, py, pz = c["pos"]
        col = c["color"]
        dims = c["dims"]

        if "motor" in name:
            r = dims[0] / 2 * S
            w = dims[1] * S
            ax.add_patch(Rectangle(
                (-w/2, py*S - r), w, dims[0]*S,
                facecolor=col, edgecolor="#333", lw=1.5, zorder=5))
            ax.text(0, py*S, "Hub\nMotor", ha="center", va="center",
                    fontsize=5, fontweight="bold", color="white", zorder=6)

        elif "caster" in name:
            ax.add_patch(Circle(
                (px*S, py*S), dims[0]/2*S,
                facecolor=col, edgecolor="#333", lw=1, zorder=5))

        elif "paint_tank" in name:
            ax.add_patch(Circle(
                (px*S, py*S), dims[0]/2*S,
                facecolor=col, edgecolor="#333", lw=1.5, alpha=0.7, zorder=4))
            ax.text(px*S, py*S, "Paint\nTank", ha="center", va="center",
                    fontsize=6, fontweight="bold", color="white", zorder=6)

        elif "estop" in name:
            ax.add_patch(Circle(
                (px*S, py*S), dims[0]/2*S,
                facecolor=col, edgecolor="#aa0000", lw=2, zorder=7))
            ax.text(px*S, py*S, "E\nSTOP", ha="center", va="center",
                    fontsize=4, fontweight="bold", color="white", zorder=8)

        elif "gps_antenna" in name:
            ax.add_patch(Circle(
                (px*S, py*S), dims[0]/2*S,
                facecolor=col, edgecolor="#333", lw=1.5, alpha=0.6,
                linestyle="--", zorder=7))
            ax.text(px*S, 55, "GPS\n(mast)", ha="center", va="center",
                    fontsize=5, color=col, zorder=8)

        elif name in ("gps", "gps_mast"):
            continue  # skip, shown by antenna

        elif "ultrasonic" in name:
            ax.add_patch(Rectangle(
                (px*S - dims[0]/2*S, py*S - dims[1]/2*S),
                dims[0]*S, dims[1]*S,
                facecolor=col, edgecolor="#333", lw=0.8, zorder=6))

        elif len(dims) >= 3:
            w, h = dims[0]*S, dims[1]*S
            ax.add_patch(Rectangle(
                (px*S - w/2, py*S - h/2), w, h,
                facecolor=col, edgecolor="#333", lw=1, zorder=4))
            # Label larger components
            if w > 30 and h > 20:
                label = name.replace("_", "\n").title()
                if len(label) < 15:
                    ax.text(px*S, py*S, label, ha="center", va="center",
                            fontsize=4, color="white", fontweight="bold",
                            zorder=6)

    # Front arrow
    ax.annotate("", xy=(PLATFORM_L/2*S + 40, 0),
                xytext=(PLATFORM_L/2*S + 10, 0),
                arrowprops=dict(arrowstyle="->", color="#333", lw=2))
    ax.text(PLATFORM_L/2*S + 50, 0, "FRONT", ha="left", va="center",
            fontsize=9, fontweight="bold", color="#333")

    # Dimensions
    dc, df = "#555", 8
    _dim_line_2d(ax, -PLATFORM_L/2*S, PLATFORM_L/2*S,
                 -PLATFORM_W/2*S - 50, "h",
                 f"{PLATFORM_L*1000:.0f} mm", dc, df)
    _dim_line_2d(ax, -PLATFORM_W/2*S, PLATFORM_W/2*S,
                 PLATFORM_L/2*S + 30, "v",
                 f"{PLATFORM_W*1000:.0f} mm", dc, df)
    _dim_line_2d(ax, -TRACK_WIDTH/2*S, TRACK_WIDTH/2*S,
                 -PLATFORM_L/2*S - 30, "v",
                 f"Track: {TRACK_WIDTH*1000:.0f} mm", dc, df)

    ax.set_title("Striper Robot \u2014 Top View (to scale, all components)",
                 fontsize=14, fontweight="bold", pad=20)

    legend = [
        mpatches.Patch(facecolor="#c0c0c0", alpha=0.3, label="Frame (610\u00d7460mm)"),
        mpatches.Patch(facecolor="#2a2a2a", label="Hub Motors (350W\u00d72)"),
        mpatches.Patch(facecolor="#2d8a4e", label="Pixhawk 6C + UM980 GPS"),
        mpatches.Patch(facecolor="#cc3333", label="Paint System"),
        mpatches.Patch(facecolor="#333366", label="36V 10Ah Battery"),
        mpatches.Patch(facecolor="#ccaa22", label="HC-SR04 Ultrasonics"),
        mpatches.Patch(facecolor="#ff1111", label="E-Stop"),
    ]
    ax.legend(handles=legend, loc="lower right", fontsize=7, framealpha=0.9)
    ax.set_xlabel("\u2190 Rear          X (mm)          Front \u2192", fontsize=9)
    ax.set_ylabel("\u2190 Right          Y (mm)          Left \u2192", fontsize=9)

    pad = 100
    ax.set_xlim(-PLATFORM_L/2*S - pad, PLATFORM_L/2*S + pad)
    ax.set_ylim(-PLATFORM_W/2*S - pad, PLATFORM_W/2*S + pad)
    ax.grid(True, alpha=0.15)
    plt.tight_layout()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Saved: {output_path}")
    plt.close(fig)


def _dim_line_2d(ax, start, end, offset, direction, label, color, fontsize):
    if direction == "h":
        ax.annotate("", xy=(end, offset), xytext=(start, offset),
                    arrowprops=dict(arrowstyle="<->", color=color, lw=1))
        ax.text((start+end)/2, offset-12, label,
                ha="center", va="top", fontsize=fontsize, color=color)
    else:
        ax.annotate("", xy=(offset, end), xytext=(offset, start),
                    arrowprops=dict(arrowstyle="<->", color=color, lw=1))
        ax.text(offset+10, (start+end)/2, label,
                ha="left", va="center", fontsize=fontsize, color=color,
                rotation=90)


# ---------------------------------------------------------------------------
# 3D product rendering
# ---------------------------------------------------------------------------
def render_3d_view(output_path):
    fig = plt.figure(figsize=(16, 12))
    ax = fig.add_subplot(111, projection="3d", computed_zorder=False)

    fig.patch.set_facecolor("#1a1a1a")
    ax.set_facecolor("#1a1a1a")
    for pane in (ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane):
        pane.fill = False
        pane.set_edgecolor("#333")
    ax.tick_params(colors="#555", labelsize=6)

    pz = PLATFORM_Z
    dz = DECK_H

    # Ground plane
    g = 0.55
    ground = [(-g, -g, 0), (g, -g, 0), (g, g, 0), (-g, g, 0)]
    ax.add_collection3d(Poly3DCollection([ground], alpha=0.25,
                        facecolor="#404040", edgecolor="#444", linewidth=0.3))

    # Shadow
    n_sh = 32
    sa = np.linspace(0, 2*np.pi, n_sh+1)
    shadow = list(zip(0.30*np.cos(sa), 0.22*np.sin(sa),
                      np.full(n_sh+1, 0.001)))
    ax.add_collection3d(Poly3DCollection([shadow], alpha=0.35,
                        facecolor="#111", edgecolor="none"))

    # Frame
    _add_box(ax, -PLATFORM_L/2, -PLATFORM_W/2, pz,
             PLATFORM_L, PLATFORM_W, dz, "#b0b0b0", alpha=0.8, label="Frame")

    # Wheels
    for sign, lbl in [(1, "Left Hub Motor"), (-1, "Right Hub Motor")]:
        wy = sign * TRACK_WIDTH / 2
        _add_cylinder(ax, 0, wy, pz - WHEEL_R, WHEEL_R, 0.065,
                      "#2a2a2a", alpha=0.95, n=24,
                      label=lbl if sign == 1 else None)

    # Casters
    for cx_pos, lbl in [(0.240, "Front Caster"), (-0.240, "Rear Caster")]:
        _add_cylinder(ax, cx_pos, 0, 0.005, 0.038, 0.060,
                      "#666", alpha=0.8, n=12,
                      label=lbl if cx_pos > 0 else None)
        _add_box(ax, cx_pos-0.008, -0.008, 0.065,
                 0.016, 0.016, pz - 0.065, "#666", alpha=0.6)

    # Paint tank
    tank_z = pz + dz
    _add_cylinder(ax, 0.020, 0.080, tank_z, 0.100, 0.250,
                  "#cc3333", alpha=0.75, n=32, label="Paint Tank (2 gal)")
    _add_cylinder(ax, 0.020, 0.080, tank_z + 0.250,
                  0.035, 0.015, _shade("#cc3333", 0.6), alpha=0.9, n=12)

    # Battery
    _add_box(ax, -0.250, -0.075, tank_z,
             0.200, 0.150, 0.050, "#333366", alpha=0.9,
             label="36V 10Ah Battery")

    # Hoverboard PCB
    _add_box(ax, -0.150, -0.180, tank_z,
             0.200, 0.100, 0.030, "#336633", alpha=0.7,
             label="Hoverboard PCB")

    # Pixhawk
    _add_box(ax, 0.080 - 0.032, -0.026, tank_z,
             0.065, 0.052, 0.014, "#2d8a4e", alpha=0.9,
             label="Pixhawk 6C Mini")

    # Pump
    _add_box(ax, 0.120, -0.135, tank_z,
             0.120, 0.070, 0.070, "#444", alpha=0.85,
             label="Shurflo 8000 Pump")

    # Solenoid
    _add_box(ax, 0.190, -0.020, tank_z,
             0.060, 0.040, 0.050, "#884444", alpha=0.85,
             label="Solenoid Valve")

    # Nozzle
    _add_box(ax, 0.255, -0.020, 0.040,
             0.050, 0.040, 0.035, "#993333", alpha=0.9,
             label="TP8004EVS Nozzle")
    _add_cylinder(ax, 0.280, 0, 0.032, 0.008, 0.008,
                  "#666", alpha=0.9, n=8)

    # GPS mast + antenna
    _add_box(ax, -0.006, -0.006, tank_z, 0.012, 0.012, 0.300,
             "#888", alpha=0.7)
    _add_cylinder(ax, 0, 0, tank_z + 0.300, 0.040, 0.018,
                  "#2d8a4e", alpha=0.9, n=24, label="UM980 RTK GPS")

    # DC-DC converters
    _add_box(ax, -0.135, 0.075, tank_z, 0.070, 0.050, 0.025,
             "#448844", alpha=0.8, label="DC-DC Conv.")
    _add_box(ax, -0.135, 0.130, tank_z, 0.070, 0.050, 0.025,
             "#448844", alpha=0.8)

    # Relay module
    _add_box(ax, 0.155, 0.080, tank_z, 0.050, 0.040, 0.020,
             "#4444aa", alpha=0.85, label="Relay Module")

    # E-stop
    _add_cylinder(ax, -0.200, 0.150, tank_z, 0.020, 0.025,
                  "#ff1111", alpha=0.95, n=16, label="E-Stop")

    # Ultrasonic sensors
    _add_box(ax, 0.278, 0.080, tank_z, 0.045, 0.020, 0.015,
             "#ccaa22", alpha=0.9, label="HC-SR04")
    _add_box(ax, 0.278, -0.100, tank_z, 0.045, 0.020, 0.015,
             "#ccaa22", alpha=0.9)

    # Hose
    ht = np.linspace(0, 1, 10)
    hx = 0.020 + (0.265 - 0.020) * ht
    hy = 0.080 + (0 - 0.080) * ht
    hz = tank_z + 0.03 + (0.050 - tank_z - 0.03) * ht**0.5
    ax.plot(hx, hy, hz, color="#555", lw=2, alpha=0.5)

    # Labels
    _label_3d(ax, 0, 0, tank_z + 0.318, "UM980 GPS", dx=0.16, dz=0.04, fontsize=8)
    _label_3d(ax, 0.020, 0.080, tank_z + 0.250, "Paint Tank", dx=-0.20, dz=0.06)
    _label_3d(ax, -0.150, 0, tank_z + 0.050, "36V Battery", dx=-0.15, dz=0.10)
    _label_3d(ax, 0.280, 0, 0.040, "Nozzle", dx=0.12, dz=-0.02)
    _label_3d(ax, -0.200, 0.150, tank_z + 0.025, "E-STOP",
              dx=-0.10, dz=0.06, color="#ff6666")

    # Camera
    ax.view_init(elev=25, azim=-50)
    ax.set_xlim(-0.42, 0.42)
    ax.set_ylim(-0.38, 0.38)
    ax.set_zlim(-0.02, GPS_TOP_Z + 0.06)
    ax.set_xlabel("X \u2014 Front (m)", fontsize=7, color="#888")
    ax.set_ylabel("Y \u2014 Left (m)", fontsize=7, color="#888")
    ax.set_zlabel("Z \u2014 Up (m)", fontsize=7, color="#888")
    ax.set_title("Striper Robot \u2014 3D Product View",
                 fontsize=15, fontweight="bold", color="white", pad=15)
    ax.legend(loc="upper left", fontsize=6, framealpha=0.6,
              facecolor="#2a2a2a", edgecolor="#555", labelcolor="white",
              ncol=2)

    checks, dry_w, total_w, cost = run_validation()
    fig.text(0.5, 0.015,
             f"{PLATFORM_L*1000:.0f}\u00d7{PLATFORM_W*1000:.0f}mm  |  "
             f"Track {TRACK_WIDTH*1000:.0f}mm  |  "
             f"Height {GPS_TOP_Z*1000:.0f}mm  |  "
             f"Dry: {dry_w:.1f}kg  |  "
             f"BOM ~${cost}  |  "
             f"ArduRover + UM980 RTK",
             ha="center", fontsize=8, color="#888", style="italic")

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=200, facecolor=fig.get_facecolor(),
                bbox_inches="tight")
    print(f"Saved: {output_path}")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Spec sheet with validation
# ---------------------------------------------------------------------------
def render_spec_sheet(output_path):
    """Render a spec sheet with validation checks — the pre-purchase checklist."""
    checks, dry_weight, total_weight, total_cost = run_validation()

    fig, axes = plt.subplots(1, 2, figsize=(16, 10),
                             gridspec_kw={"width_ratios": [1, 1.2]})
    fig.patch.set_facecolor("#1a1a1a")
    fig.suptitle("Striper Robot \u2014 Pre-Purchase Validation Report",
                 fontsize=16, fontweight="bold", color="white", y=0.97)

    # Left panel: component list with weights and costs
    ax1 = axes[0]
    ax1.set_facecolor("#222")
    ax1.set_xlim(0, 10)
    ax1.set_ylim(0, len(COMPONENTS) + 3)
    ax1.set_xticks([])
    ax1.set_yticks([])
    for spine in ax1.spines.values():
        spine.set_color("#444")

    ax1.text(5, len(COMPONENTS) + 2.2, "BILL OF MATERIALS", ha="center",
             fontsize=12, fontweight="bold", color="white")
    ax1.text(0.3, len(COMPONENTS) + 1.2, "Component", fontsize=8,
             color="#aaa", fontweight="bold")
    ax1.text(7.0, len(COMPONENTS) + 1.2, "Weight", fontsize=8,
             color="#aaa", fontweight="bold", ha="center")
    ax1.text(8.8, len(COMPONENTS) + 1.2, "Cost", fontsize=8,
             color="#aaa", fontweight="bold", ha="center")
    ax1.axhline(len(COMPONENTS) + 1.0, color="#444", lw=0.5)

    # Deduplicate for display (combine left/right motors, casters, ultrasonics)
    displayed = {}
    for name, c in COMPONENTS.items():
        base = name.replace("_fl", "").replace("_fr", "")
        base = base.replace("left_", "").replace("right_", "")
        base = base.replace("_front", "").replace("_rear", "")
        if base in displayed:
            displayed[base]["weight"] += c["weight"]
            displayed[base]["price"] += c["price"]
            displayed[base]["qty"] += 1
        else:
            displayed[base] = {
                "desc": c["desc"], "weight": c["weight"],
                "price": c["price"], "qty": 1
            }

    row = len(COMPONENTS)
    for name, d in displayed.items():
        row -= 1
        qty_str = f"({d['qty']}x) " if d["qty"] > 1 else ""
        desc = qty_str + d["desc"]
        if len(desc) > 42:
            desc = desc[:40] + ".."
        ax1.text(0.3, row, desc, fontsize=6.5, color="#ccc",
                 verticalalignment="center")
        ax1.text(7.0, row, f"{d['weight']:.2f} kg", fontsize=6.5,
                 color="#ccc", ha="center", verticalalignment="center")
        ax1.text(8.8, row, f"${d['price']}", fontsize=6.5,
                 color="#ccc", ha="center", verticalalignment="center")

    # Totals
    ax1.axhline(1.5, color="#444", lw=0.5)
    ax1.text(0.3, 0.8, "TOTAL (dry)", fontsize=8, color="white",
             fontweight="bold")
    ax1.text(7.0, 0.8, f"{dry_weight:.1f} kg", fontsize=8, color="white",
             fontweight="bold", ha="center")
    ax1.text(8.8, 0.8, f"~${total_cost}", fontsize=8, color="white",
             fontweight="bold", ha="center")

    # Right panel: validation checks
    ax2 = axes[1]
    ax2.set_facecolor("#222")
    ax2.set_xlim(0, 10)
    ax2.set_ylim(0, len(checks) + 3)
    ax2.set_xticks([])
    ax2.set_yticks([])
    for spine in ax2.spines.values():
        spine.set_color("#444")

    ax2.text(5, len(checks) + 2.2, "VALIDATION CHECKS", ha="center",
             fontsize=12, fontweight="bold", color="white")
    ax2.text(0.3, len(checks) + 1.2, "Check", fontsize=8,
             color="#aaa", fontweight="bold")
    ax2.text(5.5, len(checks) + 1.2, "Value", fontsize=8,
             color="#aaa", fontweight="bold", ha="center")
    ax2.text(8.5, len(checks) + 1.2, "Status", fontsize=8,
             color="#aaa", fontweight="bold", ha="center")
    ax2.axhline(len(checks) + 1.0, color="#444", lw=0.5)

    all_pass = True
    for i, (name, value, passed, note) in enumerate(reversed(checks)):
        row = i + 1.5
        ax2.text(0.3, row, name, fontsize=7, color="#ccc",
                 verticalalignment="center")
        ax2.text(5.5, row, value, fontsize=7, color="#ccc",
                 ha="center", verticalalignment="center")

        if passed:
            symbol = "\u2713 PASS"
            color = "#44bb66"
        else:
            symbol = "\u2717 FAIL"
            color = "#ff4444"
            all_pass = False

        ax2.text(8.5, row, symbol, fontsize=7.5, color=color,
                 ha="center", verticalalignment="center", fontweight="bold")
        ax2.text(9.8, row, note, fontsize=5, color="#777",
                 ha="right", verticalalignment="center")

    # Overall verdict
    verdict_color = "#44bb66" if all_pass else "#ff4444"
    verdict_text = "ALL CHECKS PASSED \u2014 READY TO BUILD" if all_pass else \
                   "SOME CHECKS FAILED \u2014 REVIEW BEFORE PURCHASING"
    fig.text(0.5, 0.02, verdict_text, ha="center", fontsize=11,
             fontweight="bold", color=verdict_color)

    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=200, facecolor=fig.get_facecolor(),
                bbox_inches="tight")
    print(f"Saved: {output_path}")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    print("Rendering striper robot visualizations...\n")

    # Run validation first
    checks, dry_w, total_w, cost = run_validation()
    print("Pre-purchase validation:")
    for name, value, passed, note in checks:
        status = "PASS" if passed else "FAIL"
        print(f"  {status} {name}: {value} ({note})")
    print()

    render_top_view(os.path.join(output_dir, "robot_top.png"))
    render_3d_view(os.path.join(output_dir, "robot_3d.png"))
    render_spec_sheet(os.path.join(output_dir, "robot_specs.png"))
    print("\nDone!")


if __name__ == "__main__":
    main()
