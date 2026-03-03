"""Import PaintPaths from SVG files using the svgpathtools library."""

from __future__ import annotations

from .models import PaintPath, Point2D


def _flatten_path(path, resolution: float) -> list[Point2D]:
    """Convert an svgpathtools Path to a list of Point2D waypoints.

    Curves are flattened to line segments such that the maximum chord
    length is approximately *resolution* (in SVG user units).
    """
    points: list[Point2D] = []
    for segment in path:
        seg_length = segment.length()
        if seg_length < 1e-9:
            continue
        num_steps = max(1, int(seg_length / resolution))
        for i in range(num_steps + 1):
            t = i / num_steps
            pt = segment.point(t)
            p = Point2D(pt.real, pt.imag)
            # Avoid duplicates at segment boundaries.
            if not points or (abs(p.x - points[-1].x) > 1e-9 or abs(p.y - points[-1].y) > 1e-9):
                points.append(p)
    return points


def _parse_color(attr: dict[str, str] | None) -> str:
    """Extract a colour name from SVG path attributes."""
    if attr is None:
        return "white"
    # Try stroke, then fill.
    for key in ("stroke", "fill"):
        val = attr.get(key, "").strip().lower()
        if val and val != "none":
            return val
    return "white"


def _parse_stroke_width(attr: dict[str, str] | None) -> float:
    """Extract stroke-width from SVG attributes (in user units)."""
    if attr is None:
        return 0.1
    raw = attr.get("stroke-width", "").strip()
    if not raw:
        return 0.1
    # Strip common unit suffixes.
    for suffix in ("px", "pt", "mm", "cm", "in"):
        raw = raw.replace(suffix, "")
    try:
        return float(raw)
    except ValueError:
        return 0.1


def import_svg(
    file_path: str,
    scale: float = 1.0,
    resolution: float = 0.01,
    default_color: str = "white",
    default_line_width: float = 0.1,
) -> list[PaintPath]:
    """Parse an SVG file and convert paths to PaintPaths.

    All cubic/quadratic Bezier curves and arcs are flattened to polylines
    with a chord length of approximately *resolution* (SVG user-units,
    scaled by *scale*).

    Args:
        file_path: Path to the .svg file.
        scale: Uniform scale factor applied to all coordinates.
        resolution: Maximum chord length when flattening curves (in SVG units
            before scaling).
        default_color: Fallback paint colour if the SVG path has no stroke.
        default_line_width: Fallback line width in metres.

    Returns:
        A list of PaintPath objects.
    """
    try:
        import svgpathtools
    except ImportError as exc:
        raise ImportError(
            "The 'svgpathtools' package is required for SVG import. "
            "Install it with: pip install svgpathtools"
        ) from exc

    svg_paths, attributes, svg_attributes = svgpathtools.svg2paths2(file_path)

    paint_paths: list[PaintPath] = []
    for svg_path, attr in zip(svg_paths, attributes):
        if not svg_path:
            continue
        waypoints = _flatten_path(svg_path, resolution)
        if len(waypoints) < 2:
            continue

        # Apply scale.
        if scale != 1.0:
            waypoints = [Point2D(p.x * scale, p.y * scale) for p in waypoints]

        color = _parse_color(attr) if attr else default_color
        line_width = _parse_stroke_width(attr) if attr else default_line_width
        # Scale the stroke width as well.
        line_width *= scale

        paint_paths.append(PaintPath(
            waypoints=waypoints,
            line_width=line_width,
            color=color,
        ))

    return paint_paths
