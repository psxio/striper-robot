"""Convert between striper_pathgen models and ROS2 message dict formats.

This module is the glue layer between the dashboard / pathgen library and the
ROS2 navigation stack.  It produces plain Python dicts whose structure mirrors
the ``striper_msgs/PaintSegment`` message so that they can be serialised to
JSON for the dashboard or inflated into real ROS2 messages when rclpy is
available.

The dict format for a PaintSegment message is::

    {
        "waypoints": [{"x": float, "y": float, "z": float}, ...],
        "line_width": float,
        "color": str,
        "speed": float,
    }

This matches the fields of ``striper_msgs/msg/PaintSegment.msg``:

    geometry_msgs/Point[] waypoints
    float64 line_width
    string color
    float64 speed
"""

from __future__ import annotations

from typing import Any

from .models import PaintJob, PaintPath, Point2D


# ── Single path conversion ────────────────────────────────────────────────


def paint_path_to_msg(path: PaintPath) -> dict[str, Any]:
    """Convert a PaintPath to a dict matching PaintSegment.msg fields.

    Each waypoint is emitted as ``{"x": ..., "y": ..., "z": 0.0}`` to
    match ``geometry_msgs/Point``.

    Args:
        path: The PaintPath to convert.

    Returns:
        A dict with keys ``waypoints``, ``line_width``, ``color``, ``speed``.
    """
    return {
        "waypoints": [
            {"x": wp.x, "y": wp.y, "z": 0.0}
            for wp in path.waypoints
        ],
        "line_width": path.line_width,
        "color": path.color,
        "speed": path.speed,
    }


# ── Full job conversion ──────────────────────────────────────────────────


def paint_job_to_msgs(job: PaintJob) -> list[dict[str, Any]]:
    """Convert every segment in a PaintJob to PaintSegment msg dicts.

    Args:
        job: A complete PaintJob with ordered segments.

    Returns:
        A list of dicts, one per segment, in execution order.
    """
    return [paint_path_to_msg(seg.path) for seg in job.segments]


# ── Reverse conversion ───────────────────────────────────────────────────


def msg_to_paint_path(msg_dict: dict[str, Any]) -> PaintPath:
    """Convert a PaintSegment msg dict back to a PaintPath model.

    This is the inverse of :func:`paint_path_to_msg`.

    Args:
        msg_dict: A dict with keys ``waypoints``, ``line_width``,
            ``color``, ``speed``.

    Returns:
        A PaintPath instance.
    """
    waypoints = [
        Point2D(x=wp["x"], y=wp["y"])
        for wp in msg_dict["waypoints"]
    ]
    return PaintPath(
        waypoints=waypoints,
        line_width=msg_dict.get("line_width", 0.1),
        color=msg_dict.get("color", "white"),
        speed=msg_dict.get("speed", 0.5),
    )
