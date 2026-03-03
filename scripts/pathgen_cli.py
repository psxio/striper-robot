#!/usr/bin/env python3
"""pathgen_cli.py — Command-line tool for Striper path generation.

A standalone script (no ROS 2 needed) that provides subcommands for generating
paint paths from templates, importing DXF/SVG files, optimising path ordering,
and previewing the result.

Usage examples:

  # Generate a row of 10 standard parking spaces
  python scripts/pathgen_cli.py template \\
      --type standard_space --count 10 \\
      --lat 40.758 --lon -73.985 --angle 0 \\
      --output job.json

  # Generate a handicap space
  python scripts/pathgen_cli.py template \\
      --type handicap_space --count 1 \\
      --lat 40.758 --lon -73.985 --angle 45 \\
      --output handicap_job.json

  # Import a DXF file
  python scripts/pathgen_cli.py import-dxf \\
      --file layout.dxf --scale 0.3048 \\
      --lat 40.758 --lon -73.985 \\
      --output dxf_job.json

  # Import an SVG file
  python scripts/pathgen_cli.py import-svg \\
      --file markings.svg --scale 0.01 \\
      --lat 40.758 --lon -73.985 \\
      --output svg_job.json

  # Optimise path ordering in an existing job
  python scripts/pathgen_cli.py optimize \\
      --input job.json --output job_optimised.json

  # Preview paths from a job file
  python scripts/pathgen_cli.py preview --input job.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Allow running from the project root or the scripts directory by adding
# the pathgen package to sys.path.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_PATHGEN_PKG = os.path.join(_PROJECT_ROOT, "striper_ws", "src", "striper_pathgen")

if _PATHGEN_PKG not in sys.path:
    sys.path.insert(0, _PATHGEN_PKG)


# ---------------------------------------------------------------------------
# Lazy imports — we defer heavy imports so --help stays fast.
# ---------------------------------------------------------------------------

def _import_pathgen():
    """Import and return the striper_pathgen package."""
    try:
        import striper_pathgen
        return striper_pathgen
    except ImportError as exc:
        print(
            f"Error: could not import striper_pathgen ({exc}).\n"
            "Make sure you are running from the project root or that the\n"
            "package is installed (pip install -e striper_ws/src/striper_pathgen).",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_paint_job(paths, datum_lat: float, datum_lon: float, metadata: dict | None = None):
    """Wrap a list of PaintPath objects into a PaintJob dict."""
    pg = _import_pathgen()
    segments = [
        pg.PaintSegment(path=p, index=i)
        for i, p in enumerate(paths)
    ]
    job = pg.PaintJob.create(
        segments=segments,
        datum=pg.GeoPoint(lat=datum_lat, lon=datum_lon),
        metadata=metadata or {},
    )
    return job


def _write_job(job, output_path: str):
    """Serialise a PaintJob to a JSON file."""
    data = job.to_dict()
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {len(job.segments)} segment(s) to {output_path}")


def _load_job(input_path: str):
    """Load a PaintJob from a JSON file."""
    pg = _import_pathgen()
    with open(input_path) as f:
        data = json.load(f)
    return pg.PaintJob.from_dict(data)


# ---------------------------------------------------------------------------
# Subcommand: template
# ---------------------------------------------------------------------------

def cmd_template(args):
    """Generate paint paths from a built-in template."""
    pg = _import_pathgen()

    origin = pg.Point2D(0.0, 0.0)
    angle = args.angle

    template_type = args.type

    # Generators that support a "count" parameter (parking rows)
    row_types = {"standard_space", "handicap_space", "compact"}
    # Single-instance generators
    single_types = {"arrow", "crosswalk"}

    all_paths: list = []

    if template_type in row_types:
        gen_map = {
            "standard_space": pg.generate_standard_space,
            "handicap_space": pg.generate_handicap_space,
        }
        gen_func = gen_map.get(template_type)
        if gen_func is None:
            # Fall back to standard space for "compact" with smaller dimensions
            gen_func = pg.generate_standard_space

        spacing = args.spacing if args.spacing else 2.7
        if template_type == "handicap_space":
            spacing = args.spacing if args.spacing else 3.6

        for i in range(args.count):
            space_origin = pg.Point2D(origin.x + i * spacing, origin.y)
            paths = gen_func(origin=space_origin, angle=angle)
            all_paths.extend(paths)

    elif template_type in single_types:
        if template_type == "arrow":
            for i in range(args.count):
                arr_origin = pg.Point2D(origin.x + i * 3.0, origin.y)
                paths = pg.generate_arrow(origin=arr_origin, angle=angle)
                all_paths.extend(paths)
        elif template_type == "crosswalk":
            for i in range(args.count):
                cw_origin = pg.Point2D(origin.x + i * 8.0, origin.y)
                paths = pg.generate_crosswalk(origin=cw_origin, angle=angle)
                all_paths.extend(paths)
    else:
        # Try the JSON template loader
        try:
            paths = pg.generate_from_template(template_type, origin, angle)
            all_paths.extend(paths)
        except (ValueError, FileNotFoundError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            print(
                "Available template types: standard_space, handicap_space, "
                "arrow, crosswalk",
                file=sys.stderr,
            )
            sys.exit(1)

    if not all_paths:
        print("No paths generated.", file=sys.stderr)
        sys.exit(1)

    job = _build_paint_job(
        all_paths,
        datum_lat=args.lat,
        datum_lon=args.lon,
        metadata={"source": "template", "template_type": template_type, "count": args.count},
    )
    _write_job(job, args.output)


# ---------------------------------------------------------------------------
# Subcommand: import-dxf
# ---------------------------------------------------------------------------

def cmd_import_dxf(args):
    """Import paint paths from a DXF file."""
    try:
        from striper_pathgen.dxf_importer import import_dxf
    except ImportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Install ezdxf: pip install ezdxf", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(args.file):
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    paths = import_dxf(args.file, scale=args.scale)
    if not paths:
        print("Warning: no paths extracted from the DXF file.", file=sys.stderr)

    job = _build_paint_job(
        paths,
        datum_lat=args.lat,
        datum_lon=args.lon,
        metadata={"source": "dxf", "file": os.path.basename(args.file), "scale": args.scale},
    )
    _write_job(job, args.output)


# ---------------------------------------------------------------------------
# Subcommand: import-svg
# ---------------------------------------------------------------------------

def cmd_import_svg(args):
    """Import paint paths from an SVG file."""
    try:
        from striper_pathgen.svg_importer import import_svg
    except ImportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Install svgpathtools: pip install svgpathtools", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(args.file):
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    paths = import_svg(args.file, scale=args.scale)
    if not paths:
        print("Warning: no paths extracted from the SVG file.", file=sys.stderr)

    job = _build_paint_job(
        paths,
        datum_lat=args.lat,
        datum_lon=args.lon,
        metadata={"source": "svg", "file": os.path.basename(args.file), "scale": args.scale},
    )
    _write_job(job, args.output)


# ---------------------------------------------------------------------------
# Subcommand: optimize
# ---------------------------------------------------------------------------

def cmd_optimize(args):
    """Optimise the ordering of paint paths in an existing job file."""
    pg = _import_pathgen()

    job = _load_job(args.input)
    print(f"Loaded job {job.job_id} with {len(job.segments)} segment(s)")

    # Extract raw PaintPaths
    raw_paths = [seg.path for seg in job.segments]

    # Compute before distance
    dist_before = pg.calculate_total_transit_distance(raw_paths)
    print(f"Transit distance before: {dist_before:.2f} m")

    # Optimise
    optimised = pg.optimize_path_order(raw_paths)

    # Compute after distance
    dist_after = pg.calculate_total_transit_distance(optimised)
    print(f"Transit distance after:  {dist_after:.2f} m")

    if dist_before > 0:
        savings = (1.0 - dist_after / dist_before) * 100
        print(f"Savings: {savings:.1f}%")

    # Rebuild segments with new ordering
    new_segments = [
        pg.PaintSegment(path=p, index=i)
        for i, p in enumerate(optimised)
    ]
    job.segments = new_segments
    job.metadata["optimised"] = True
    job.metadata["transit_distance_m"] = round(dist_after, 3)

    output = args.output or args.input
    _write_job(job, output)


# ---------------------------------------------------------------------------
# Subcommand: preview
# ---------------------------------------------------------------------------

def cmd_preview(args):
    """Generate a visualisation of paths from a job file."""
    job = _load_job(args.input)
    print(f"Job {job.job_id}: {len(job.segments)} segment(s)")
    print(f"Datum: lat={job.datum.lat}, lon={job.datum.lon}")

    # Gather all waypoints to determine bounds
    all_x: list[float] = []
    all_y: list[float] = []
    for seg in job.segments:
        for wp in seg.path.waypoints:
            all_x.append(wp.x)
            all_y.append(wp.y)

    if not all_x:
        print("No waypoints to visualise.")
        return

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)

    # Try matplotlib first
    if not args.ascii:
        try:
            _preview_matplotlib(job, args)
            return
        except ImportError:
            print("matplotlib not available, falling back to ASCII preview.\n")

    # ASCII fallback
    _preview_ascii(job, min_x, max_x, min_y, max_y)


def _preview_matplotlib(job, args):
    """Render paths using matplotlib."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 1, figsize=(12, 8))
    ax.set_aspect("equal")
    ax.set_title(f"Striper Job: {job.job_id[:12]}... ({len(job.segments)} segments)")
    ax.set_xlabel("X (metres)")
    ax.set_ylabel("Y (metres)")

    color_map = {
        "white": "#333333",  # dark on white background
        "yellow": "#DAA520",
        "blue": "#1E90FF",
        "red": "#DC143C",
    }

    for i, seg in enumerate(job.segments):
        xs = [wp.x for wp in seg.path.waypoints]
        ys = [wp.y for wp in seg.path.waypoints]
        c = color_map.get(seg.path.color, "#333333")
        ax.plot(xs, ys, color=c, linewidth=max(1, seg.path.line_width * 20), solid_capstyle="round")

        # Draw transit lines between segments
        if i > 0:
            prev_end = job.segments[i - 1].path.end
            cur_start = seg.path.start
            ax.plot(
                [prev_end.x, cur_start.x],
                [prev_end.y, cur_start.y],
                color="#AAAAAA", linewidth=0.5, linestyle="--", alpha=0.5,
            )

    ax.grid(True, alpha=0.3)

    if args.output_image:
        fig.savefig(args.output_image, dpi=150, bbox_inches="tight")
        print(f"Saved preview to {args.output_image}")
    else:
        plt.show()


def _preview_ascii(job, min_x: float, max_x: float, min_y: float, max_y: float):
    """Render a simple ASCII art preview of the paths."""
    WIDTH = 80
    HEIGHT = 40

    range_x = max_x - min_x
    range_y = max_y - min_y

    if range_x < 1e-9:
        range_x = 1.0
    if range_y < 1e-9:
        range_y = 1.0

    # Create grid
    grid = [[" " for _ in range(WIDTH)] for _ in range(HEIGHT)]

    segment_chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

    for seg_idx, seg in enumerate(job.segments):
        char = segment_chars[seg_idx % len(segment_chars)]
        for wp in seg.path.waypoints:
            col = int((wp.x - min_x) / range_x * (WIDTH - 1))
            row = int((max_y - wp.y) / range_y * (HEIGHT - 1))  # flip Y
            col = max(0, min(WIDTH - 1, col))
            row = max(0, min(HEIGHT - 1, row))
            grid[row][col] = char

    # Print grid
    border = "+" + "-" * WIDTH + "+"
    print(border)
    for row in grid:
        print("|" + "".join(row) + "|")
    print(border)

    print(f"\nBounds: X=[{min_x:.2f}, {max_x:.2f}] m  Y=[{min_y:.2f}, {max_y:.2f}] m")
    print(f"Segments: {len(job.segments)}  (each character = one segment)")

    # Print legend for first few segments
    total_paint = 0.0
    total_transit = 0.0
    pg = _import_pathgen()
    raw_paths = [seg.path for seg in job.segments]
    total_transit = pg.calculate_total_transit_distance(raw_paths)
    for seg in job.segments:
        total_paint += seg.path.length
    print(f"Total paint distance:   {total_paint:.2f} m")
    print(f"Total transit distance: {total_transit:.2f} m")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pathgen_cli",
        description="Striper path generation CLI — generate, import, optimise, and preview paint paths.",
        epilog=(
            "Examples:\n"
            "  %(prog)s template --type standard_space --count 10 --lat 40.758 --lon -73.985 -o job.json\n"
            "  %(prog)s import-dxf --file layout.dxf --scale 0.3048 --lat 40.758 --lon -73.985 -o dxf_job.json\n"
            "  %(prog)s import-svg --file marks.svg --scale 0.01 --lat 40.758 --lon -73.985 -o svg_job.json\n"
            "  %(prog)s optimize --input job.json -o job_opt.json\n"
            "  %(prog)s preview --input job.json\n"
            "  %(prog)s preview --input job.json --ascii\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # ── template ───────────────────────────────────────────────────────────
    p_tmpl = subparsers.add_parser(
        "template",
        help="Generate paths from a built-in template",
        description=(
            "Generate paint paths from a built-in template type.\n"
            "Available types: standard_space, handicap_space, arrow, crosswalk"
        ),
    )
    p_tmpl.add_argument(
        "--type", required=True,
        help="Template type (standard_space, handicap_space, arrow, crosswalk)",
    )
    p_tmpl.add_argument("--lat", type=float, required=True, help="Datum latitude")
    p_tmpl.add_argument("--lon", type=float, required=True, help="Datum longitude")
    p_tmpl.add_argument("--angle", type=float, default=0.0, help="Rotation angle in degrees (default: 0)")
    p_tmpl.add_argument("--count", type=int, default=1, help="Number of instances to generate (default: 1)")
    p_tmpl.add_argument("--spacing", type=float, default=None, help="Spacing between instances in metres")
    p_tmpl.add_argument("-o", "--output", required=True, help="Output JSON file path")
    p_tmpl.set_defaults(func=cmd_template)

    # ── import-dxf ─────────────────────────────────────────────────────────
    p_dxf = subparsers.add_parser(
        "import-dxf",
        help="Import paths from a DXF file",
        description="Parse a DXF file and convert supported entities to paint paths.",
    )
    p_dxf.add_argument("--file", required=True, help="Path to the .dxf file")
    p_dxf.add_argument("--scale", type=float, default=1.0, help="Scale factor (default: 1.0)")
    p_dxf.add_argument("--lat", type=float, required=True, help="Datum latitude")
    p_dxf.add_argument("--lon", type=float, required=True, help="Datum longitude")
    p_dxf.add_argument("-o", "--output", required=True, help="Output JSON file path")
    p_dxf.set_defaults(func=cmd_import_dxf)

    # ── import-svg ─────────────────────────────────────────────────────────
    p_svg = subparsers.add_parser(
        "import-svg",
        help="Import paths from an SVG file",
        description="Parse an SVG file and convert paths to paint paths.",
    )
    p_svg.add_argument("--file", required=True, help="Path to the .svg file")
    p_svg.add_argument("--scale", type=float, default=1.0, help="Scale factor (default: 1.0)")
    p_svg.add_argument("--lat", type=float, required=True, help="Datum latitude")
    p_svg.add_argument("--lon", type=float, required=True, help="Datum longitude")
    p_svg.add_argument("-o", "--output", required=True, help="Output JSON file path")
    p_svg.set_defaults(func=cmd_import_svg)

    # ── optimize ───────────────────────────────────────────────────────────
    p_opt = subparsers.add_parser(
        "optimize",
        help="Optimise path ordering in a job file",
        description=(
            "Reorder paint segments to minimise non-painting transit distance.\n"
            "Uses nearest-neighbour + 2-opt local search."
        ),
    )
    p_opt.add_argument("--input", required=True, help="Input JSON job file")
    p_opt.add_argument("-o", "--output", default=None, help="Output JSON file (default: overwrite input)")
    p_opt.set_defaults(func=cmd_optimize)

    # ── preview ────────────────────────────────────────────────────────────
    p_prev = subparsers.add_parser(
        "preview",
        help="Visualise paths from a job file",
        description=(
            "Generate a preview of paint paths. Uses matplotlib if available,\n"
            "otherwise falls back to an ASCII visualisation."
        ),
    )
    p_prev.add_argument("--input", required=True, help="Input JSON job file")
    p_prev.add_argument("--ascii", action="store_true", help="Force ASCII output (skip matplotlib)")
    p_prev.add_argument("--output-image", default=None, help="Save preview to an image file (PNG, PDF, etc.)")
    p_prev.set_defaults(func=cmd_preview)

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
