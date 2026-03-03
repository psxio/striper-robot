"""Generate standard parking lot marking templates as PaintPath lists."""

from __future__ import annotations

import json
import math
import os
from typing import Any

from .models import PaintPath, Point2D


# ── Geometry helpers ──────────────────────────────────────────────────────── #

def _rotate(point: Point2D, angle_rad: float, origin: Point2D) -> Point2D:
    """Rotate *point* around *origin* by *angle_rad* (CCW positive)."""
    dx = point.x - origin.x
    dy = point.y - origin.y
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return Point2D(
        origin.x + dx * cos_a - dy * sin_a,
        origin.y + dx * sin_a + dy * cos_a,
    )


def _transform_points(
    points: list[Point2D], origin: Point2D, angle_rad: float
) -> list[Point2D]:
    """Translate then rotate a list of points."""
    return [
        _rotate(Point2D(p.x + origin.x, p.y + origin.y), angle_rad, origin)
        for p in points
    ]


def _make_line(
    p1: Point2D,
    p2: Point2D,
    origin: Point2D,
    angle_rad: float,
    line_width: float = 0.1,
    color: str = "white",
    speed: float = 0.5,
) -> PaintPath:
    """Create a single-segment PaintPath from two points, transformed."""
    pts = _transform_points([p1, p2], origin, angle_rad)
    return PaintPath(waypoints=pts, line_width=line_width, color=color, speed=speed)


# ── Standard parking space ────────────────────────────────────────────────── #

def generate_standard_space(
    origin: Point2D,
    angle: float,
    width: float = 2.7,
    length: float = 5.5,
    line_width: float = 0.1,
    color: str = "white",
) -> list[PaintPath]:
    """Generate two parallel lines defining a standard parking space.

    The space is drawn with the opening at the bottom (y=0) and lines
    extending in the +Y direction.

    Args:
        origin: Reference point (bottom-left corner of the space).
        angle: Rotation in degrees (CCW from +X axis).
        width: Space width in metres (default 2.7 m / ~9 ft).
        length: Space depth in metres (default 5.5 m / ~18 ft).
    """
    angle_rad = math.radians(angle)
    # Left line
    left = _make_line(
        Point2D(0, 0), Point2D(0, length), origin, angle_rad,
        line_width=line_width, color=color,
    )
    # Right line
    right = _make_line(
        Point2D(width, 0), Point2D(width, length), origin, angle_rad,
        line_width=line_width, color=color,
    )
    return [left, right]


# ── Handicap space ────────────────────────────────────────────────────────── #

def generate_handicap_space(
    origin: Point2D,
    angle: float,
    width: float = 3.6,
    length: float = 5.5,
    line_width: float = 0.1,
    color: str = "blue",
) -> list[PaintPath]:
    """Generate a handicap-accessible parking space.

    Includes wider boundary lines, an access aisle with cross-hatching,
    and a simplified wheelchair symbol outline.

    Args:
        origin: Bottom-left corner.
        angle: Rotation in degrees.
        width: Total width including access aisle (default 3.6 m / ~12 ft).
        length: Space depth (default 5.5 m / ~18 ft).
    """
    angle_rad = math.radians(angle)
    paths: list[PaintPath] = []

    # Boundary lines (left, right)
    paths.append(
        _make_line(Point2D(0, 0), Point2D(0, length), origin, angle_rad,
                   line_width=line_width, color=color)
    )
    paths.append(
        _make_line(Point2D(width, 0), Point2D(width, length), origin, angle_rad,
                   line_width=line_width, color=color)
    )

    # Access aisle boundary (drawn at ~60 % of width)
    aisle_x = width * 0.6
    paths.append(
        _make_line(Point2D(aisle_x, 0), Point2D(aisle_x, length), origin, angle_rad,
                   line_width=line_width, color=color)
    )

    # Cross-hatching in the access aisle
    hatch_spacing = 0.6
    y = hatch_spacing
    while y < length:
        paths.append(
            _make_line(
                Point2D(aisle_x, y), Point2D(width, y),
                origin, angle_rad, line_width=line_width, color=color,
            )
        )
        y += hatch_spacing

    # Simplified wheelchair symbol (circle + outline) centred in the space
    cx = aisle_x / 2
    cy = length * 0.45
    r = 0.35
    num_pts = 24
    circle_pts = [
        Point2D(cx + r * math.cos(2 * math.pi * i / num_pts),
                cy + r * math.sin(2 * math.pi * i / num_pts))
        for i in range(num_pts + 1)
    ]
    transformed = _transform_points(circle_pts, origin, angle_rad)
    paths.append(PaintPath(waypoints=transformed, line_width=line_width, color=color))

    return paths


# ── Parking row ───────────────────────────────────────────────────────────── #

def generate_parking_row(
    origin: Point2D,
    angle: float,
    count: int,
    spacing: float = 2.7,
    handicap_indices: list[int] | None = None,
    length: float = 5.5,
    line_width: float = 0.1,
    color: str = "white",
    handicap_color: str = "blue",
) -> list[PaintPath]:
    """Generate a row of adjacent parking spaces.

    Args:
        origin: Bottom-left corner of the first space.
        angle: Rotation angle in degrees.
        count: Number of spaces.
        spacing: Centre-to-centre distance between spaces.
        handicap_indices: Indices (0-based) of spaces that are handicap.
        length: Depth of each space.
    """
    handicap_set = set(handicap_indices or [])
    paths: list[PaintPath] = []
    angle_rad = math.radians(angle)

    for i in range(count):
        offset_x = i * spacing
        space_origin = _rotate(
            Point2D(origin.x + offset_x, origin.y), angle_rad, origin
        )
        if i in handicap_set:
            paths.extend(
                generate_handicap_space(
                    space_origin, angle, width=spacing, length=length,
                    line_width=line_width, color=handicap_color,
                )
            )
        else:
            paths.extend(
                generate_standard_space(
                    space_origin, angle, width=spacing, length=length,
                    line_width=line_width, color=color,
                )
            )

    # Add the closing right-side line for the last space (standard spaces
    # already include it, but this ensures consistent visual closure).
    return paths


# ── Directional arrow ─────────────────────────────────────────────────────── #

_ARROW_TEMPLATES: dict[str, list[list[tuple[float, float]]]] = {
    "straight": [
        # Shaft
        [(0, 0), (0, 2.0)],
        # Left barb
        [(-0.4, 1.4), (0, 2.0)],
        # Right barb
        [(0.4, 1.4), (0, 2.0)],
    ],
    "left": [
        [(0, 0), (0, 1.2), (-0.8, 1.2)],
        [(-0.4, 0.8), (-0.8, 1.2)],
        [(-0.4, 1.6), (-0.8, 1.2)],
    ],
    "right": [
        [(0, 0), (0, 1.2), (0.8, 1.2)],
        [(0.4, 0.8), (0.8, 1.2)],
        [(0.4, 1.6), (0.8, 1.2)],
    ],
    "u_turn": [
        [(0, 0), (0, 1.5)],
        [(0, 1.5), (0.3, 1.8), (0.6, 1.5)],
        [(0.6, 1.5), (0.6, 0.6)],
        [(0.2, 1.0), (0.6, 0.6)],
        [(1.0, 1.0), (0.6, 0.6)],
    ],
}


def generate_arrow(
    origin: Point2D,
    angle: float,
    arrow_type: str = "straight",
    line_width: float = 0.1,
    color: str = "white",
) -> list[PaintPath]:
    """Generate directional arrow PaintPaths.

    Args:
        origin: Base-centre point of the arrow.
        angle: Rotation in degrees.
        arrow_type: One of "straight", "left", "right", "u_turn".
    """
    template = _ARROW_TEMPLATES.get(arrow_type)
    if template is None:
        raise ValueError(
            f"Unknown arrow_type {arrow_type!r}. "
            f"Choose from {list(_ARROW_TEMPLATES.keys())}"
        )

    angle_rad = math.radians(angle)
    paths: list[PaintPath] = []
    for polyline in template:
        raw = [Point2D(x, y) for x, y in polyline]
        transformed = _transform_points(raw, origin, angle_rad)
        paths.append(PaintPath(waypoints=transformed, line_width=line_width, color=color))
    return paths


# ── Crosswalk ─────────────────────────────────────────────────────────────── #

def generate_crosswalk(
    origin: Point2D,
    angle: float,
    width: float = 3.0,
    length: float = 6.0,
    stripe_width: float = 0.3,
    gap: float = 0.3,
    line_width: float = 0.1,
    color: str = "white",
) -> list[PaintPath]:
    """Generate continental (ladder) crosswalk stripes.

    The stripes run parallel to the direction of pedestrian travel and are
    spaced across the width of the crosswalk.

    Args:
        origin: Bottom-left corner of the crosswalk bounding box.
        angle: Rotation in degrees.
        width: Cross-traffic dimension (perpendicular to pedestrian travel).
        length: Along-traffic dimension (parallel to pedestrian travel).
        stripe_width: Width of each painted stripe.
        gap: Gap between stripes.
    """
    angle_rad = math.radians(angle)
    paths: list[PaintPath] = []

    x = 0.0
    while x + stripe_width <= width + 1e-9:
        # Each stripe is a filled rectangle; we approximate it as a single
        # wide painted line down the centre of the stripe.
        cx = x + stripe_width / 2
        p1 = Point2D(cx, 0)
        p2 = Point2D(cx, length)
        pts = _transform_points([p1, p2], origin, angle_rad)
        paths.append(
            PaintPath(waypoints=pts, line_width=stripe_width, color=color)
        )
        x += stripe_width + gap

    return paths


# ── JSON template I/O ─────────────────────────────────────────────────────── #

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")


def load_template(name: str) -> dict[str, Any]:
    """Load a JSON template by name (without .json extension)."""
    path = os.path.join(_TEMPLATES_DIR, f"{name}.json")
    with open(path) as f:
        return json.load(f)


def save_template(name: str, data: dict[str, Any]) -> str:
    """Save a template dict to JSON and return the file path."""
    os.makedirs(_TEMPLATES_DIR, exist_ok=True)
    path = os.path.join(_TEMPLATES_DIR, f"{name}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def generate_from_template(
    template_name: str,
    origin: Point2D,
    angle: float = 0.0,
) -> list[PaintPath]:
    """Load a named template and generate PaintPaths from it.

    The template JSON must contain a "type" field matching one of the
    generator functions, plus any keyword arguments for that generator.
    """
    tmpl = load_template(template_name)
    tmpl_type = tmpl.get("type", template_name)
    kwargs = {k: v for k, v in tmpl.items() if k != "type"}

    generators = {
        "standard_space": generate_standard_space,
        "handicap_space": generate_handicap_space,
        "arrow": generate_arrow,
        "crosswalk": generate_crosswalk,
    }

    gen = generators.get(tmpl_type)
    if gen is None:
        raise ValueError(f"Unknown template type {tmpl_type!r}")

    return gen(origin=origin, angle=angle, **kwargs)
