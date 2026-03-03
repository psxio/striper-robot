"""Export PaintJob data to ArduPilot/Mission Planner waypoint format.

Generates .waypoints files compatible with Mission Planner and QGroundControl.
The waypoint file uses MAVLink commands to navigate the robot along paint paths,
controlling the paint relay for each segment.

The output format is the QGC WPL 110 tab-separated text format:
  QGC WPL 110
  seq  current  frame  command  p1  p2  p3  p4  lat  lon  alt  autocontinue

All functions operate on the pure-Python pathgen models and have no ROS2
dependency.
"""

from __future__ import annotations

import math
from typing import TextIO

from .coordinate_transform import CoordinateTransformer
from .models import GeoPoint, PaintJob, PaintPath, Point2D


# ── MAVLink command constants ──────────────────────────────────────────── #

MAV_CMD_NAV_WAYPOINT = 16
MAV_CMD_DO_JUMP = 177
MAV_CMD_DO_CHANGE_SPEED = 178
MAV_CMD_DO_SET_RELAY = 181

MAV_FRAME_GLOBAL = 0
MAV_FRAME_GLOBAL_RELATIVE_ALT = 3

# Relay channel used for the paint solenoid
PAINT_RELAY_CHANNEL = 0

# Default waypoint altitude (relative, metres)
DEFAULT_ALT = 0.0


# ── Internal helpers ───────────────────────────────────────────────────── #


def _format_waypoint(
    seq: int,
    current: int,
    frame: int,
    command: int,
    p1: float,
    p2: float,
    p3: float,
    p4: float,
    lat: float,
    lon: float,
    alt: float,
    autocontinue: int = 1,
) -> str:
    """Format a single waypoint line in QGC WPL 110 format."""
    return (
        f"{seq}\t{current}\t{frame}\t{command}\t"
        f"{p1}\t{p2}\t{p3}\t{p4}\t"
        f"{lat:.8f}\t{lon:.8f}\t{alt:.6f}\t{autocontinue}"
    )


def _interpolate_path(path: PaintPath, spacing: float = 0.5) -> list[Point2D]:
    """Add intermediate waypoints along a PaintPath for smooth tracking.

    Walks each segment of the path and inserts evenly-spaced points so that
    no two consecutive waypoints are more than *spacing* metres apart.  The
    original waypoints are always preserved.

    Args:
        path: The paint path to interpolate.
        spacing: Maximum distance between consecutive waypoints in metres.

    Returns:
        A list of Point2D with intermediate points inserted.
    """
    if len(path.waypoints) < 2:
        return list(path.waypoints)

    result: list[Point2D] = [path.waypoints[0]]

    for i in range(len(path.waypoints) - 1):
        p_start = path.waypoints[i]
        p_end = path.waypoints[i + 1]

        seg_len = p_start.distance_to(p_end)
        if seg_len < 1e-9:
            continue

        # Number of intermediate points to insert
        n_intervals = max(1, math.ceil(seg_len / spacing))

        for j in range(1, n_intervals):
            t = j / n_intervals
            interp = Point2D(
                x=p_start.x + t * (p_end.x - p_start.x),
                y=p_start.y + t * (p_end.y - p_start.y),
            )
            result.append(interp)

        result.append(p_end)

    return result


# ── Public API ─────────────────────────────────────────────────────────── #


def export_waypoints(
    job: PaintJob,
    datum_lat: float,
    datum_lon: float,
    datum_heading: float = 0.0,
    paint_speed: float = 0.5,
    transit_speed: float = 1.0,
    waypoint_spacing: float = 0.5,
    accept_radius: float = 0.05,
) -> str:
    """Export a PaintJob to ArduPilot/Mission Planner waypoint file content.

    For each paint segment the function emits:
      1. DO_CHANGE_SPEED to transit speed
      2. NAV_WAYPOINT to the segment start point
      3. DO_CHANGE_SPEED to paint speed
      4. DO_SET_RELAY on  (paint relay energised)
      5. NAV_WAYPOINT for each interpolated point along the segment
      6. DO_SET_RELAY off (paint relay released)

    Args:
        job: The PaintJob containing paint segments in local coordinates.
        datum_lat: Latitude of the local coordinate origin (degrees).
        datum_lon: Longitude of the local coordinate origin (degrees).
        datum_heading: Heading rotation of the local frame in degrees
            clockwise from North (default 0).
        paint_speed: Ground speed while painting in m/s (default 0.5).
        transit_speed: Ground speed while transiting in m/s (default 1.0).
        waypoint_spacing: Maximum distance between waypoints along paint
            paths in metres (default 0.5).
        accept_radius: Waypoint acceptance radius in metres (default 0.05).

    Returns:
        The complete .waypoints file content as a string.
    """
    xf = CoordinateTransformer(datum_lat, datum_lon, datum_heading)

    lines: list[str] = ["QGC WPL 110"]
    seq = 0

    # ── Home position (seq 0) ──────────────────────────────────────────
    # The home waypoint is always seq 0, current=1, frame=0 (GLOBAL).
    lines.append(
        _format_waypoint(
            seq=seq,
            current=1,
            frame=MAV_FRAME_GLOBAL,
            command=MAV_CMD_NAV_WAYPOINT,
            p1=0, p2=0, p3=0, p4=0,
            lat=datum_lat,
            lon=datum_lon,
            alt=DEFAULT_ALT,
        )
    )
    seq += 1

    # ── Process each paint segment ─────────────────────────────────────
    for seg in job.segments:
        path = seg.path
        interpolated = _interpolate_path(path, spacing=waypoint_spacing)
        if not interpolated:
            continue

        # 1. Set transit speed
        lines.append(
            _format_waypoint(
                seq=seq, current=0, frame=MAV_FRAME_GLOBAL_RELATIVE_ALT,
                command=MAV_CMD_DO_CHANGE_SPEED,
                p1=0,  # speed type: ground speed
                p2=transit_speed,
                p3=-1,  # throttle: no change
                p4=0,
                lat=0, lon=0, alt=0,
            )
        )
        seq += 1

        # 2. Navigate to segment start
        start_geo = xf.local_to_geo(interpolated[0].x, interpolated[0].y)
        lines.append(
            _format_waypoint(
                seq=seq, current=0, frame=MAV_FRAME_GLOBAL_RELATIVE_ALT,
                command=MAV_CMD_NAV_WAYPOINT,
                p1=0,  # hold time
                p2=accept_radius,
                p3=0,  # pass radius
                p4=0,  # yaw
                lat=start_geo.lat,
                lon=start_geo.lon,
                alt=DEFAULT_ALT,
            )
        )
        seq += 1

        # 3. Set paint speed
        lines.append(
            _format_waypoint(
                seq=seq, current=0, frame=MAV_FRAME_GLOBAL_RELATIVE_ALT,
                command=MAV_CMD_DO_CHANGE_SPEED,
                p1=0,
                p2=paint_speed,
                p3=-1,
                p4=0,
                lat=0, lon=0, alt=0,
            )
        )
        seq += 1

        # 4. Turn paint relay ON
        lines.append(
            _format_waypoint(
                seq=seq, current=0, frame=MAV_FRAME_GLOBAL_RELATIVE_ALT,
                command=MAV_CMD_DO_SET_RELAY,
                p1=PAINT_RELAY_CHANNEL,
                p2=1,  # ON
                p3=0, p4=0,
                lat=0, lon=0, alt=0,
            )
        )
        seq += 1

        # 5. Navigate along interpolated waypoints (skip the first since
        #    we already navigated to the start)
        for pt in interpolated[1:]:
            geo = xf.local_to_geo(pt.x, pt.y)
            lines.append(
                _format_waypoint(
                    seq=seq, current=0, frame=MAV_FRAME_GLOBAL_RELATIVE_ALT,
                    command=MAV_CMD_NAV_WAYPOINT,
                    p1=0,
                    p2=accept_radius,
                    p3=0,
                    p4=0,
                    lat=geo.lat,
                    lon=geo.lon,
                    alt=DEFAULT_ALT,
                )
            )
            seq += 1

        # 6. Turn paint relay OFF
        lines.append(
            _format_waypoint(
                seq=seq, current=0, frame=MAV_FRAME_GLOBAL_RELATIVE_ALT,
                command=MAV_CMD_DO_SET_RELAY,
                p1=PAINT_RELAY_CHANNEL,
                p2=0,  # OFF
                p3=0, p4=0,
                lat=0, lon=0, alt=0,
            )
        )
        seq += 1

    return "\n".join(lines) + "\n"


def save_waypoints(
    job: PaintJob,
    filepath: str,
    datum_lat: float,
    datum_lon: float,
    datum_heading: float = 0.0,
    paint_speed: float = 0.5,
    transit_speed: float = 1.0,
    waypoint_spacing: float = 0.5,
    accept_radius: float = 0.05,
) -> None:
    """Export a PaintJob and write it to a .waypoints file.

    This is a convenience wrapper around :func:`export_waypoints` that writes
    the result directly to disk.

    Args:
        job: The PaintJob to export.
        filepath: Destination file path (typically ending in ``.waypoints``).
        datum_lat: Latitude of the local coordinate origin.
        datum_lon: Longitude of the local coordinate origin.
        datum_heading: Heading rotation of the local frame in degrees.
        paint_speed: Ground speed while painting in m/s.
        transit_speed: Ground speed while transiting in m/s.
        waypoint_spacing: Maximum distance between waypoints in metres.
        accept_radius: Waypoint acceptance radius in metres.
    """
    content = export_waypoints(
        job=job,
        datum_lat=datum_lat,
        datum_lon=datum_lon,
        datum_heading=datum_heading,
        paint_speed=paint_speed,
        transit_speed=transit_speed,
        waypoint_spacing=waypoint_spacing,
        accept_radius=accept_radius,
    )
    with open(filepath, "w", newline="\n") as f:
        f.write(content)
