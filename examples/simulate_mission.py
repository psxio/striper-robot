#!/usr/bin/env python3
"""Animated mission simulation for striper robot.

Parses a QGC WPL 110 .waypoints file and produces:
  1. An animated matplotlib visualization of the robot executing the mission
  2. A clean final-frame PNG showing the finished paint job (aerial view)

The simulation uses straight-line interpolation between waypoints —
this matches ArduRover's L1 navigation controller which follows
straight segments between GPS waypoints.

Usage:
    python examples/simulate_mission.py [path/to/file.waypoints] [--speed 5]
"""

import argparse
import math
import os
import sys

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation
from matplotlib.collections import LineCollection
import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PAINT_SPEED = 0.50       # m/s (WP_SPEED from striper.param)
TRANSIT_SPEED = 1.00     # m/s (CRUISE_SPEED from striper.param)
ROBOT_LENGTH = 0.60      # m
ROBOT_WIDTH = 0.45       # m
PAINT_LINE_WIDTH_M = 0.10  # m (~4 inches)
EARTH_RADIUS = 6_378_137.0

CMD_WAYPOINT = 16
CMD_CHANGE_SPEED = 178
CMD_SET_RELAY = 181


# ---------------------------------------------------------------------------
# Waypoint parser
# ---------------------------------------------------------------------------
def parse_waypoints(filepath):
    """Parse QGC WPL 110 file."""
    commands = []
    with open(filepath, "r") as f:
        header = f.readline().strip()
        if not header.startswith("QGC WPL"):
            raise ValueError(f"Not a QGC WPL file: {header}")
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 12:
                continue
            commands.append({
                "seq": int(parts[0]),
                "cmd_id": int(parts[3]),
                "p2": float(parts[5]),
                "lat": float(parts[8]),
                "lon": float(parts[9]),
            })
    return commands


# ---------------------------------------------------------------------------
# Coordinate transform with heading rotation
# ---------------------------------------------------------------------------
class CoordTransform:
    """GPS to local meters with optional heading rotation."""

    def __init__(self, datum_lat, datum_lon, heading_deg=0.0):
        self.datum_lat = datum_lat
        self.datum_lon = datum_lon
        lat_rad = math.radians(datum_lat)
        self.m_per_deg_lat = math.pi / 180.0 * EARTH_RADIUS
        self.m_per_deg_lon = math.pi / 180.0 * EARTH_RADIUS * math.cos(lat_rad)
        h = math.radians(heading_deg)
        self.cos_h = math.cos(h)
        self.sin_h = math.sin(h)

    def to_local(self, lat, lon):
        """Convert GPS to local XY with heading rotation applied."""
        dx = (lon - self.datum_lon) * self.m_per_deg_lon
        dy = (lat - self.datum_lat) * self.m_per_deg_lat
        rx = dx * self.cos_h + dy * self.sin_h
        ry = -dx * self.sin_h + dy * self.cos_h
        return rx, ry


def detect_heading(commands):
    """Auto-detect lot heading from waypoint data using PCA.

    Returns the heading in degrees that aligns the lot with the axes.
    """
    # Collect all nav waypoint positions
    pts = []
    datum_lat = datum_lon = None
    for c in commands:
        if c["cmd_id"] == CMD_WAYPOINT and (c["lat"] != 0 or c["lon"] != 0):
            if datum_lat is None:
                datum_lat, datum_lon = c["lat"], c["lon"]
            lat_rad = math.radians(datum_lat)
            m_lat = math.pi / 180.0 * EARTH_RADIUS
            m_lon = math.pi / 180.0 * EARTH_RADIUS * math.cos(lat_rad)
            x = (c["lon"] - datum_lon) * m_lon
            y = (c["lat"] - datum_lat) * m_lat
            pts.append((x, y))

    if len(pts) < 3:
        return 0.0

    pts = np.array(pts)
    pts -= pts.mean(axis=0)

    # PCA: find principal axis
    cov = np.cov(pts.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # Principal axis = eigenvector with largest eigenvalue
    principal = eigenvectors[:, np.argmax(eigenvalues)]
    angle = math.degrees(math.atan2(principal[1], principal[0]))

    # Snap to nearest 45° to match common lot headings
    snapped = round(angle / 45.0) * 45.0
    return snapped


# ---------------------------------------------------------------------------
# Build paint and transit segments from commands
# ---------------------------------------------------------------------------
def build_segments(commands, transform):
    """Extract paint and transit path segments.

    Returns paint_segs, transit_segs (each: list of [(x,y), ...]),
    and stats dict.
    """
    paint_segs = []
    transit_segs = []
    current_seg = []
    paint_on = False
    total_paint_dist = 0.0
    total_transit_dist = 0.0
    last_pt = None

    for c in commands:
        if c["cmd_id"] == CMD_SET_RELAY:
            new_state = int(c["p2"]) == 1
            if new_state != paint_on:
                if len(current_seg) > 1:
                    # Compute segment length
                    seg_len = sum(
                        math.hypot(current_seg[j+1][0] - current_seg[j][0],
                                   current_seg[j+1][1] - current_seg[j][1])
                        for j in range(len(current_seg) - 1))
                    # Skip zero-length segments
                    if seg_len > 0.01:
                        if paint_on:
                            paint_segs.append(current_seg)
                        else:
                            transit_segs.append(current_seg)
                current_seg = [last_pt] if last_pt else []
                paint_on = new_state

        elif c["cmd_id"] == CMD_WAYPOINT:
            if c["lat"] == 0 and c["lon"] == 0:
                continue
            pt = transform.to_local(c["lat"], c["lon"])
            current_seg.append(pt)
            if last_pt:
                d = math.hypot(pt[0] - last_pt[0], pt[1] - last_pt[1])
                if paint_on:
                    total_paint_dist += d
                else:
                    total_transit_dist += d
            last_pt = pt

    # Flush final segment
    if len(current_seg) > 1:
        seg_len = sum(
            math.hypot(current_seg[j+1][0] - current_seg[j][0],
                       current_seg[j+1][1] - current_seg[j][1])
            for j in range(len(current_seg) - 1))
        if seg_len > 0.01:
            if paint_on:
                paint_segs.append(current_seg)
            else:
                transit_segs.append(current_seg)

    return paint_segs, transit_segs, {
        "paint_dist": total_paint_dist,
        "transit_dist": total_transit_dist,
        "n_paint_segs": len(paint_segs),
        "n_transit_segs": len(transit_segs),
    }


# ---------------------------------------------------------------------------
# Build animation timeline
# ---------------------------------------------------------------------------
def build_timeline(commands, transform):
    """Build ordered (x, y, heading, paint_on, speed, t) frames."""
    path_points = []
    paint_on = False
    speed = PAINT_SPEED

    for c in commands:
        if c["cmd_id"] == CMD_SET_RELAY:
            paint_on = int(c["p2"]) == 1
            speed = PAINT_SPEED if paint_on else TRANSIT_SPEED
        elif c["cmd_id"] == CMD_CHANGE_SPEED:
            if c["p2"] > 0:
                speed = c["p2"]
        elif c["cmd_id"] == CMD_WAYPOINT:
            if c["lat"] == 0 and c["lon"] == 0:
                continue
            x, y = transform.to_local(c["lat"], c["lon"])
            path_points.append((x, y, paint_on, speed))

    if len(path_points) < 2:
        return []

    sample_dt = 0.08  # seconds between frame samples
    frames = []
    t = 0.0
    paint_dist = 0.0
    transit_dist = 0.0
    seg_count = 0
    prev_paint = False

    for i in range(1, len(path_points)):
        x0, y0, _, _ = path_points[i - 1]
        x1, y1, p1, s1 = path_points[i]

        if not p1 and prev_paint:
            seg_count += 1
        prev_paint = p1

        dx, dy = x1 - x0, y1 - y0
        seg_len = math.hypot(dx, dy)
        if seg_len < 1e-6:
            continue

        heading = math.atan2(dy, dx)
        spd = max(s1, 0.1)
        seg_time = seg_len / spd
        n_samples = max(1, int(seg_time / sample_dt))

        for k in range(n_samples + 1):
            frac = k / max(n_samples, 1)
            fx = x0 + dx * frac
            fy = y0 + dy * frac
            d_inc = (seg_len / max(n_samples, 1)) if k > 0 else 0

            if p1:
                paint_dist += d_inc
            else:
                transit_dist += d_inc

            frames.append({
                "x": fx, "y": fy, "heading": heading,
                "speed": spd, "paint_on": p1, "t": t + seg_time * frac,
                "paint_dist": paint_dist, "transit_dist": transit_dist,
                "seg_count": seg_count,
                "wp_idx": i, "total_wps": len(path_points),
            })

        t += seg_time

    if prev_paint:
        seg_count += 1
    total_segs = seg_count
    for f in frames:
        f["total_segs"] = total_segs

    return frames


# ---------------------------------------------------------------------------
# Robot polygon
# ---------------------------------------------------------------------------
def robot_polygon(x, y, heading):
    cos_h, sin_h = math.cos(heading), math.sin(heading)
    hl, hw = ROBOT_LENGTH / 2, ROBOT_WIDTH / 2
    corners = [(hl, hw), (hl, -hw), (-hl, -hw), (-hl, hw)]
    return [(x + cx * cos_h - cy * sin_h,
             y + cx * sin_h + cy * cos_h) for cx, cy in corners]


# ---------------------------------------------------------------------------
# Compute plot bounds from paint segments
# ---------------------------------------------------------------------------
def compute_bounds(paint_segs, transit_segs, margin=2.0):
    all_pts = []
    for seg in paint_segs + transit_segs:
        all_pts.extend(seg)
    if not all_pts:
        return -10, 10, -10, 10
    xs, ys = zip(*all_pts)
    return (min(xs) - margin, max(xs) + margin,
            min(ys) - margin, max(ys) + margin)


# ---------------------------------------------------------------------------
# Render clean final image (aerial photo style)
# ---------------------------------------------------------------------------
def render_final_image(paint_segs, stats, output_path):
    """Render the finished paint job — realistic aerial view."""
    xmin, xmax, ymin, ymax = compute_bounds(paint_segs, [], margin=2.5)
    dx = xmax - xmin
    dy = ymax - ymin
    fig_w = 14
    fig_h = min(16, max(9, fig_w * dy / max(dx, 0.1)))

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    # Dark asphalt background
    fig.patch.set_facecolor("#1a1a1a")
    ax.set_facecolor("#3d3d3d")
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")

    # Subtle asphalt texture (random noise)
    np.random.seed(42)
    noise_n = 300
    noise_x = np.random.uniform(xmin, xmax, noise_n)
    noise_y = np.random.uniform(ymin, ymax, noise_n)
    noise_s = np.random.uniform(0.5, 3.0, noise_n)
    ax.scatter(noise_x, noise_y, s=noise_s, c="#4a4a4a", alpha=0.3,
               marker=".", zorder=1, edgecolors="none")

    # Hide axes for clean aerial look
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Paint line width: 4 inches = 0.1m, scaled to figure
    data_per_inch = dx / fig_w
    lw_points = PAINT_LINE_WIDTH_M / data_per_inch * 72
    lw_points = max(2.0, min(lw_points, 10))

    # Draw paint lines with round caps so corner joints look clean
    for seg in paint_segs:
        if len(seg) < 2:
            continue
        xs, ys = zip(*seg)
        # Main white line
        ax.plot(xs, ys, color="#f0f0f0", lw=lw_points,
                solid_capstyle="round", solid_joinstyle="round",
                zorder=5, alpha=0.97)

    # Subtle paint glow (wider faint line underneath for realism)
    for seg in paint_segs:
        if len(seg) < 2:
            continue
        xs, ys = zip(*seg)
        ax.plot(xs, ys, color="#ffffff", lw=lw_points + 1.5,
                solid_capstyle="round", solid_joinstyle="round",
                zorder=4, alpha=0.08)

    # Scale bar (bottom right)
    bar_len = 5.0
    bx = xmax - 2.0 - bar_len
    by = ymin + 1.2
    ax.plot([bx, bx + bar_len], [by, by], color="white", lw=2.5,
            zorder=10, solid_capstyle="butt")
    ax.plot([bx, bx], [by - 0.2, by + 0.2], color="white", lw=2, zorder=10)
    ax.plot([bx + bar_len, bx + bar_len], [by - 0.2, by + 0.2],
            color="white", lw=2, zorder=10)
    ax.text(bx + bar_len / 2, by + 0.5, "5 m",
            ha="center", va="bottom", fontsize=10, color="white",
            fontweight="bold")

    # Title
    ax.set_title("Striper Robot \u2014 Finished Paint Job  (aerial view)",
                 fontsize=14, fontweight="bold", color="white", pad=15)

    # Stats bar
    est_min = stats["paint_dist"] / PAINT_SPEED / 60
    est_gal = (stats["paint_dist"] * 3.281) / 350  # ~350 ft/gal
    fig.text(0.5, 0.015,
             f"{stats['n_paint_segs']} paint segments  \u2502  "
             f"{stats['paint_dist']:.0f} m ({stats['paint_dist']*3.281:.0f} ft) paint  \u2502  "
             f"{stats['transit_dist']:.0f} m transit  \u2502  "
             f"~{est_min:.0f} min  \u2502  "
             f"~{est_gal:.1f} gal paint",
             ha="center", fontsize=9, color="#999")

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fig.savefig(output_path, dpi=250, facecolor=fig.get_facecolor(),
                bbox_inches="tight")
    print(f"Saved: {output_path}")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Animated mission visualization
# ---------------------------------------------------------------------------
def animate_mission(frames, paint_segs, transit_segs, speed_mult,
                    output_path, show=True):
    """Animate the robot executing the mission."""
    if not frames:
        print("No frames.")
        return

    xmin, xmax, ymin, ymax = compute_bounds(paint_segs, transit_segs)
    dx = xmax - xmin
    dy = ymax - ymin
    fig_w = 13
    fig_h = min(15, max(8, fig_w * dy / max(dx, 0.1)))

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor("#1e1e1e")
    ax.set_facecolor("#333333")
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_xlabel("X (m)", color="#888", fontsize=9)
    ax.set_ylabel("Y (m)", color="#888", fontsize=9)
    ax.set_title("Striper Robot \u2014 Mission Simulation", color="white",
                 fontsize=13, fontweight="bold")
    ax.tick_params(colors="#666", labelsize=7)
    for spine in ax.spines.values():
        spine.set_color("#444")

    # Faint grid
    ax.grid(True, color="#3a3a3a", lw=0.3, alpha=0.3)

    # Data-scaled line width
    data_per_inch = dx / fig_w
    lw_paint = max(1.5, min(6, PAINT_LINE_WIDTH_M / data_per_inch * 72))

    # Pre-plot paint segments (hidden, revealed progressively)
    paint_line_objs = []
    for seg in paint_segs:
        if len(seg) < 2:
            paint_line_objs.append(None)
            continue
        xs, ys = zip(*seg)
        ln, = ax.plot(xs, ys, color="white", lw=lw_paint,
                      solid_capstyle="butt", zorder=5, visible=False)
        paint_line_objs.append(ln)

    # Active paint line (currently being drawn)
    active_line, = ax.plot([], [], color="#ffffcc", lw=lw_paint + 0.5,
                           solid_capstyle="round", zorder=6)

    # Robot body
    robot_patch = plt.Polygon(robot_polygon(0, 0, 0), closed=True,
                              fc="#e8a820", ec="white", lw=1.2, zorder=10)
    ax.add_patch(robot_patch)

    # Heading arrow
    arrow_line, = ax.plot([], [], color="white", lw=1.5, zorder=11)

    # Nozzle indicator
    nozzle_dot, = ax.plot([], [], "o", ms=5, zorder=11)

    # Stats panel
    stats_text = ax.text(
        0.02, 0.98, "", transform=ax.transAxes, fontsize=9,
        fontfamily="monospace", color="white", verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#1e1e1e",
                  edgecolor="#555", alpha=0.85),
        zorder=20)

    # Legend
    legend_handles = [
        mpatches.Patch(facecolor="white", edgecolor="#999", label="Paint"),
        mpatches.Patch(facecolor="#e8a820", edgecolor="white", label="Robot"),
    ]
    ax.legend(handles=legend_handles, loc="upper right", fontsize=8,
              facecolor="#1e1e1e", edgecolor="#555", labelcolor="white")

    # Map frames to paint segment index for progressive reveal
    cur_paint_seg_idx = -1
    prev_paint = False
    frame_paint_seg = []
    for f in frames:
        if f["paint_on"] and not prev_paint:
            cur_paint_seg_idx += 1
        frame_paint_seg.append(cur_paint_seg_idx if f["paint_on"] else -1)
        prev_paint = f["paint_on"]

    # Subsample frames (cap ~1000 for smooth playback)
    indices = list(range(len(frames)))
    if len(indices) > 1000:
        step = len(indices) // 1000
        indices = list(range(0, len(frames), step))
        if indices[-1] != len(frames) - 1:
            indices.append(len(frames) - 1)

    def update(fi):
        frame = frames[fi]
        cur_pseg = frame_paint_seg[fi]

        # Reveal completed paint segments
        reveal_up_to = (cur_pseg - 1) if frame["paint_on"] else cur_pseg
        for i, ln in enumerate(paint_line_objs):
            if ln is not None:
                ln.set_visible(i <= reveal_up_to)

        # Active paint line (partial segment being drawn)
        if frame["paint_on"] and 0 <= cur_pseg < len(paint_segs):
            seg = paint_segs[cur_pseg]
            # Find closest point in segment to robot position
            best_k = 0
            best_d = 1e9
            for k, (sx, sy) in enumerate(seg):
                d = (sx - frame["x"])**2 + (sy - frame["y"])**2
                if d < best_d:
                    best_d = d
                    best_k = k
            partial = seg[:best_k + 1]
            if len(partial) > 1:
                px, py = zip(*partial)
                active_line.set_data(px, py)
            else:
                active_line.set_data([], [])
        else:
            active_line.set_data([], [])

        # Robot
        robot_patch.set_xy(robot_polygon(frame["x"], frame["y"],
                                         frame["heading"]))
        hx = frame["x"] + 0.35 * math.cos(frame["heading"])
        hy = frame["y"] + 0.35 * math.sin(frame["heading"])
        arrow_line.set_data([frame["x"], hx], [frame["y"], hy])

        # Nozzle
        nx = frame["x"] + 0.28 * math.cos(frame["heading"])
        ny = frame["y"] + 0.28 * math.sin(frame["heading"])
        nozzle_dot.set_data([nx], [ny])
        nozzle_dot.set_color("#44ff44" if frame["paint_on"] else "#ff4444")
        nozzle_dot.set_markersize(6 if frame["paint_on"] else 3)

        # Stats
        progress = frame["wp_idx"] / max(frame["total_wps"], 1) * 100
        stats = (
            f"Progress:  {progress:5.1f}%\n"
            f"Speed:     {frame['speed']:.2f} m/s\n"
            f"Paint:     {'ON ' if frame['paint_on'] else 'OFF'}\n"
            f"Paint dist:{frame['paint_dist']:7.1f} m\n"
            f"Segments:  {frame['seg_count']}/{frame['total_segs']}\n"
            f"Time:      {frame['t']:6.1f} s"
        )
        stats_text.set_text(stats)
        return []

    interval_ms = max(1, int(80 / speed_mult))
    print(f"Animating {len(indices)} frames at {speed_mult}x "
          f"({interval_ms}ms interval)...")

    anim = FuncAnimation(fig, update, frames=indices,
                         interval=interval_ms, blit=False, repeat=False)
    plt.tight_layout()

    if show:
        plt.show()
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Simulate a striper robot mission from a .waypoints file"
    )
    parser.add_argument("waypoints", nargs="?",
                        default=os.path.join(os.path.dirname(__file__),
                                             "output",
                                             "sample_lot.waypoints"),
                        help="Path to .waypoints file (QGC WPL 110)")
    parser.add_argument("--speed", type=float, default=5.0,
                        help="Animation speed multiplier (default: 5)")
    parser.add_argument("--heading", type=float, default=None,
                        help="Lot heading in degrees (auto-detected if omitted)")
    parser.add_argument("--no-show", action="store_true",
                        help="Save PNG only, don't open animation window")
    args = parser.parse_args()

    if not os.path.isfile(args.waypoints):
        print(f"Error: File not found: {args.waypoints}")
        sys.exit(1)

    print(f"Loading: {args.waypoints}")
    commands = parse_waypoints(args.waypoints)
    print(f"  {len(commands)} commands")

    # Detect or use specified heading
    heading = args.heading
    if heading is None:
        heading = detect_heading(commands)
        print(f"  Auto-detected heading: {heading:.0f}\u00b0")
    else:
        print(f"  Using heading: {heading:.0f}\u00b0")

    # Find datum
    datum_lat = datum_lon = None
    for c in commands:
        if c["cmd_id"] == CMD_WAYPOINT and (c["lat"] != 0 or c["lon"] != 0):
            datum_lat, datum_lon = c["lat"], c["lon"]
            break

    transform = CoordTransform(datum_lat, datum_lon, heading)

    # Build segments
    paint_segs, transit_segs, stats = build_segments(commands, transform)
    print(f"  {stats['n_paint_segs']} paint segments, "
          f"{stats['n_transit_segs']} transit segments")
    print(f"  Paint: {stats['paint_dist']:.1f} m, "
          f"Transit: {stats['transit_dist']:.1f} m")

    # Render clean final image
    output_dir = os.path.dirname(args.waypoints)
    final_path = os.path.join(output_dir, "mission_sim.png")
    render_final_image(paint_segs, stats, final_path)

    # Animate
    if not args.no_show:
        frames = build_timeline(commands, transform)
        print(f"  {len(frames)} animation frames, "
              f"{frames[-1]['t']:.0f}s sim time")
        animate_mission(frames, paint_segs, transit_segs, args.speed,
                        final_path, show=True)


if __name__ == "__main__":
    main()
