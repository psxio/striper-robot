"""Validate ArduPilot .waypoints files for common errors.

Checks a QGC WPL 110 waypoint file for issues that would cause problems
when loaded into Mission Planner or executed on a real ArduRover robot.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Result of validating a waypoints file."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, int | float] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


# MAVLink command IDs
_CMD_NAV_WAYPOINT = 16
_CMD_DO_CHANGE_SPEED = 178
_CMD_DO_SET_RELAY = 181


def validate_waypoints(content: str) -> ValidationResult:
    """Validate a .waypoints file string.

    Args:
        content: The full text content of a .waypoints file.

    Returns:
        A ValidationResult with any errors, warnings, and statistics.
    """
    result = ValidationResult()
    lines = [line for line in content.strip().split("\n") if line.strip()]

    if not lines:
        result.errors.append("File is empty")
        return result

    # Check header
    if lines[0].strip() != "QGC WPL 110":
        result.errors.append(f"Missing or invalid header: expected 'QGC WPL 110', got '{lines[0].strip()}'")
        return result

    # Parse waypoint lines
    waypoints = []
    for i, line in enumerate(lines[1:], start=2):
        fields = line.split("\t")
        if len(fields) < 12:
            result.errors.append(f"Line {i}: expected 12 tab-separated fields, got {len(fields)}")
            continue
        try:
            wp = {
                "seq": int(fields[0]),
                "current": int(fields[1]),
                "frame": int(fields[2]),
                "command": int(fields[3]),
                "p1": float(fields[4]),
                "p2": float(fields[5]),
                "p3": float(fields[6]),
                "p4": float(fields[7]),
                "lat": float(fields[8]),
                "lon": float(fields[9]),
                "alt": float(fields[10]),
                "autocontinue": int(fields[11]),
                "line": i,
            }
            waypoints.append(wp)
        except (ValueError, IndexError) as e:
            result.errors.append(f"Line {i}: parse error: {e}")

    if not waypoints:
        result.errors.append("No valid waypoints found after header")
        return result

    # Check sequence numbers are sequential
    for i, wp in enumerate(waypoints):
        if wp["seq"] != i:
            result.errors.append(
                f"Line {wp['line']}: sequence number {wp['seq']} expected {i}"
            )

    # Check home waypoint (seq 0)
    home = waypoints[0]
    if home["current"] != 1:
        result.warnings.append("Home waypoint (seq 0) should have current=1")
    if home["command"] != _CMD_NAV_WAYPOINT:
        result.warnings.append(f"Home waypoint (seq 0) command should be 16 (NAV_WAYPOINT), got {home['command']}")

    # Validate GPS coordinates
    nav_wps = [wp for wp in waypoints if wp["command"] == _CMD_NAV_WAYPOINT]
    for wp in nav_wps:
        if wp["lat"] == 0.0 and wp["lon"] == 0.0:
            continue  # Some DO_ commands use 0,0
        if not (-90 <= wp["lat"] <= 90):
            result.errors.append(f"Line {wp['line']}: latitude {wp['lat']} out of range [-90, 90]")
        if not (-180 <= wp["lon"] <= 180):
            result.errors.append(f"Line {wp['line']}: longitude {wp['lon']} out of range [-180, 180]")

    # Check that relay commands are balanced (on/off pairs)
    relay_cmds = [wp for wp in waypoints if wp["command"] == _CMD_DO_SET_RELAY]
    relay_on_count = sum(1 for wp in relay_cmds if wp["p2"] == 1)
    relay_off_count = sum(1 for wp in relay_cmds if wp["p2"] == 0)
    if relay_on_count != relay_off_count:
        result.errors.append(
            f"Unbalanced relay commands: {relay_on_count} ON vs {relay_off_count} OFF "
            f"(paint will be left {'on' if relay_on_count > relay_off_count else 'off'})"
        )

    # Check relay on/off alternation
    relay_state = None
    for wp in relay_cmds:
        new_state = "on" if wp["p2"] == 1 else "off"
        if relay_state == new_state:
            result.warnings.append(
                f"Line {wp['line']}: duplicate relay {new_state} (relay already {relay_state})"
            )
        relay_state = new_state

    # Check speed commands
    speed_cmds = [wp for wp in waypoints if wp["command"] == _CMD_DO_CHANGE_SPEED]
    for wp in speed_cmds:
        speed = wp["p2"]
        if speed <= 0:
            result.errors.append(f"Line {wp['line']}: speed must be positive, got {speed}")
        elif speed > 5.0:
            result.warnings.append(f"Line {wp['line']}: speed {speed} m/s seems high for a paint robot")

    # Check waypoint distances
    prev_nav = None
    max_gap = 0.0
    total_distance = 0.0
    for wp in nav_wps:
        if wp["lat"] == 0.0 and wp["lon"] == 0.0:
            continue
        if prev_nav is not None:
            dist = _haversine(prev_nav["lat"], prev_nav["lon"], wp["lat"], wp["lon"])
            total_distance += dist
            if dist > max_gap:
                max_gap = dist
            if dist > 100:
                result.warnings.append(
                    f"Line {wp['line']}: large gap ({dist:.0f}m) from previous waypoint"
                )
        prev_nav = wp

    # ArduPilot mission size limit
    if len(waypoints) > 725:
        result.warnings.append(
            f"Mission has {len(waypoints)} commands (ArduPilot typical limit ~725)"
        )

    # Compute stats
    result.stats = {
        "total_commands": len(waypoints),
        "nav_waypoints": len(nav_wps),
        "relay_commands": len(relay_cmds),
        "speed_commands": len(speed_cmds),
        "paint_segments": relay_on_count,
        "total_distance_m": round(total_distance, 1),
        "max_waypoint_gap_m": round(max_gap, 2),
    }

    return result


def validate_waypoints_file(filepath: str) -> ValidationResult:
    """Validate a .waypoints file from disk."""
    with open(filepath) as f:
        return validate_waypoints(f.read())


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate distance between two GPS coordinates in metres."""
    R = 6371000  # Earth radius in metres
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
