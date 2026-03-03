"""Import PaintPaths from DXF files using the ezdxf library."""

from __future__ import annotations

import math
from typing import Any

from .models import PaintPath, Point2D

# Default layer-to-style mapping used when no explicit map is given.
_DEFAULT_LAYER_MAP: dict[str, dict[str, Any]] = {
    "WHITE": {"color": "white", "line_width": 0.1},
    "YELLOW": {"color": "yellow", "line_width": 0.1},
    "BLUE": {"color": "blue", "line_width": 0.1},
    "RED": {"color": "red", "line_width": 0.1},
}


def _arc_to_points(
    center_x: float,
    center_y: float,
    radius: float,
    start_angle_deg: float,
    end_angle_deg: float,
    num_segments: int = 36,
) -> list[Point2D]:
    """Approximate a circular arc with line segments."""
    # Normalise so that end > start
    while end_angle_deg < start_angle_deg:
        end_angle_deg += 360.0

    points: list[Point2D] = []
    for i in range(num_segments + 1):
        t = i / num_segments
        angle_rad = math.radians(start_angle_deg + t * (end_angle_deg - start_angle_deg))
        points.append(Point2D(
            center_x + radius * math.cos(angle_rad),
            center_y + radius * math.sin(angle_rad),
        ))
    return points


def _style_for_layer(
    layer_name: str,
    layer_map: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    """Resolve colour and line_width for a DXF layer."""
    lmap = layer_map if layer_map is not None else _DEFAULT_LAYER_MAP
    upper = layer_name.upper()
    if upper in lmap:
        return dict(lmap[upper])
    # Try case-insensitive prefix match.
    for key, style in lmap.items():
        if upper.startswith(key.upper()):
            return dict(style)
    return {"color": "white", "line_width": 0.1}


def import_dxf(
    file_path: str,
    scale: float = 1.0,
    layer_map: dict[str, dict[str, Any]] | None = None,
) -> list[PaintPath]:
    """Parse a DXF file and convert supported entities to PaintPaths.

    Supported entity types:
        * LINE — straight line between two points
        * LWPOLYLINE — lightweight polyline (2D)
        * ARC — circular arc
        * CIRCLE — full circle

    Args:
        file_path: Path to the .dxf file.
        scale: Uniform scale factor applied to all coordinates (default 1.0).
        layer_map: Optional mapping of layer names to ``{"color": ...,
            "line_width": ...}`` dicts.  Layer names are matched
            case-insensitively.

    Returns:
        A list of PaintPath objects, one per entity.
    """
    try:
        import ezdxf
    except ImportError as exc:
        raise ImportError(
            "The 'ezdxf' package is required for DXF import. "
            "Install it with: pip install ezdxf"
        ) from exc

    doc = ezdxf.readfile(file_path)
    msp = doc.modelspace()
    paths: list[PaintPath] = []

    for entity in msp:
        layer = entity.dxf.layer if entity.dxf.hasattr("layer") else "0"
        style = _style_for_layer(layer, layer_map)

        if entity.dxftype() == "LINE":
            start = entity.dxf.start
            end = entity.dxf.end
            waypoints = [
                Point2D(start.x * scale, start.y * scale),
                Point2D(end.x * scale, end.y * scale),
            ]
            paths.append(PaintPath(
                waypoints=waypoints,
                line_width=style.get("line_width", 0.1),
                color=style.get("color", "white"),
            ))

        elif entity.dxftype() == "LWPOLYLINE":
            # LWPOLYLINE stores vertices as (x, y [, start_width, end_width, bulge])
            raw_points = list(entity.get_points(format="xy"))
            if len(raw_points) < 2:
                continue
            waypoints = [Point2D(x * scale, y * scale) for x, y in raw_points]
            # Close the polyline if flagged as closed.
            if entity.closed and waypoints[0].distance_to(waypoints[-1]) > 1e-9:
                waypoints.append(Point2D(waypoints[0].x, waypoints[0].y))
            paths.append(PaintPath(
                waypoints=waypoints,
                line_width=style.get("line_width", 0.1),
                color=style.get("color", "white"),
            ))

        elif entity.dxftype() == "ARC":
            cx = entity.dxf.center.x * scale
            cy = entity.dxf.center.y * scale
            radius = entity.dxf.radius * scale
            start_angle = entity.dxf.start_angle
            end_angle = entity.dxf.end_angle
            waypoints = _arc_to_points(cx, cy, radius, start_angle, end_angle)
            paths.append(PaintPath(
                waypoints=waypoints,
                line_width=style.get("line_width", 0.1),
                color=style.get("color", "white"),
            ))

        elif entity.dxftype() == "CIRCLE":
            cx = entity.dxf.center.x * scale
            cy = entity.dxf.center.y * scale
            radius = entity.dxf.radius * scale
            waypoints = _arc_to_points(cx, cy, radius, 0, 360)
            paths.append(PaintPath(
                waypoints=waypoints,
                line_width=style.get("line_width", 0.1),
                color=style.get("color", "white"),
            ))

    return paths
