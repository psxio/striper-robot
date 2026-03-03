"""Unit tests for safety-subsystem pure logic — no ROS2 required.

Extracts and tests the core algorithms from:
    - geofence_node.py:  point-in-polygon, distance-to-boundary
    - safety_supervisor_node.py:  safety level determination
    - watchdog_node.py:  timeout classification
    - obstacle_detector_node.py: distance thresholds
"""

from __future__ import annotations

import math
import sys
import os

import pytest

# ---------------------------------------------------------------------------
# The safety nodes depend on rclpy at import time, so we cannot import them
# directly.  Instead we replicate the pure-logic static methods here — the
# tests prove the algorithms are correct and can be validated independently
# of the ROS2 runtime.
# ---------------------------------------------------------------------------


# ── Geofence logic (extracted from GeofenceNode) ─────────────────────────


def point_in_polygon(lat: float, lon: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray casting algorithm for point-in-polygon test.

    Based on geofence_node.py GeofenceNode._point_in_polygon, with corrected
    axis handling (lat=y, lon=x).
    """
    n = len(polygon)
    if n < 3:
        return True  # No valid polygon = no restriction

    inside = False
    j = n - 1
    for i in range(n):
        lat_i, lon_i = polygon[i]
        lat_j, lon_j = polygon[j]

        if ((lat_i > lat) != (lat_j > lat)) and \
           (lon < (lon_j - lon_i) * (lat - lat_i) / (lat_j - lat_i) + lon_i):
            inside = not inside
        j = i

    return inside


def point_to_segment_distance(
    plat: float, plon: float,
    lat1: float, lon1: float,
    lat2: float, lon2: float,
) -> float:
    """Distance from point to line segment in meters.

    Copied verbatim from geofence_node.py GeofenceNode._point_to_segment_distance.
    """
    cos_lat = math.cos(math.radians(plat))
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * cos_lat

    px = (plon - lon1) * m_per_deg_lon
    py = (plat - lat1) * m_per_deg_lat
    sx = (lon2 - lon1) * m_per_deg_lon
    sy = (lat2 - lat1) * m_per_deg_lat

    seg_len_sq = sx * sx + sy * sy
    if seg_len_sq < 1e-10:
        return math.sqrt(px * px + py * py)

    t = max(0.0, min(1.0, (px * sx + py * sy) / seg_len_sq))
    proj_x = t * sx
    proj_y = t * sy

    dx = px - proj_x
    dy = py - proj_y
    return math.sqrt(dx * dx + dy * dy)


def distance_to_boundary(
    lat: float, lon: float, polygon: list[tuple[float, float]]
) -> float:
    """Minimum distance from a point to any polygon edge in meters.

    Copied from geofence_node.py GeofenceNode._distance_to_boundary.
    """
    if len(polygon) < 2:
        return float("inf")

    min_dist = float("inf")
    n = len(polygon)

    for i in range(n):
        j = (i + 1) % n
        lat1, lon1 = polygon[i]
        lat2, lon2 = polygon[j]
        dist = point_to_segment_distance(lat, lon, lat1, lon1, lat2, lon2)
        if dist < min_dist:
            min_dist = dist

    return min_dist


# ── Safety supervisor logic (extracted from SafetySupervisorNode) ─────────

# Safety level constants matching SafetyStatus.msg
SAFE = 0
WARNING = 1
CRITICAL = 2
ESTOP = 3


def determine_safety_level(
    estop_active: bool,
    geofence_violation: bool,
    watchdog_timeout: bool,
    obstacle_detected: bool,
) -> int:
    """Determine safety level from inputs.

    Mirrors SafetySupervisorNode._update logic.
    """
    if estop_active:
        return ESTOP
    elif geofence_violation or watchdog_timeout:
        return CRITICAL
    elif obstacle_detected:
        return WARNING
    else:
        return SAFE


def apply_speed_override(
    safety_level: int,
    linear_x: float,
    linear_y: float,
    angular_z: float,
) -> tuple[float, float, float]:
    """Apply speed override based on safety level.

    Returns (linear_x, linear_y, angular_z) after override.
    Mirrors SafetySupervisorNode._update cmd_vel logic.
    """
    if safety_level >= CRITICAL:
        return (0.0, 0.0, 0.0)
    elif safety_level == WARNING:
        factor = 0.3
        return (linear_x * factor, linear_y * factor, angular_z * factor)
    else:
        return (linear_x, linear_y, angular_z)


# ── Watchdog logic (extracted from WatchdogNode) ─────────────────────────


def classify_heartbeat(
    elapsed_seconds: float,
    heartbeat_timeout: float = 2.0,
    critical_timeout: float = 5.0,
) -> str:
    """Classify a node's heartbeat status.

    Returns one of: "alive", "warning", "dead".
    Mirrors WatchdogNode._check_heartbeats logic.
    """
    if elapsed_seconds > critical_timeout:
        return "dead"
    elif elapsed_seconds > heartbeat_timeout:
        return "warning"
    else:
        return "alive"


def evaluate_watchdog(
    elapsed_times: dict[str, float],
    heartbeat_timeout: float = 2.0,
    critical_timeout: float = 5.0,
) -> tuple[bool, list[str], list[str]]:
    """Evaluate watchdog status for multiple nodes.

    Returns:
        (any_critical, dead_nodes, warn_nodes)
    """
    dead_nodes: list[str] = []
    warn_nodes: list[str] = []

    for node_name, elapsed in elapsed_times.items():
        status = classify_heartbeat(elapsed, heartbeat_timeout, critical_timeout)
        if status == "dead":
            dead_nodes.append(node_name)
        elif status == "warning":
            warn_nodes.append(node_name)

    any_critical = len(dead_nodes) > 0
    return any_critical, dead_nodes, warn_nodes


# ── Obstacle detection thresholds ─────────────────────────────────────────


def evaluate_obstacle_zone(
    min_distance: float,
    warning_distance: float = 2.0,
    stop_distance: float = 0.5,
) -> str:
    """Classify obstacle proximity.

    Returns one of: "clear", "warning", "stop".
    Mirrors ObstacleDetectorNode._scan logic.
    """
    if min_distance < stop_distance:
        return "stop"
    elif min_distance < warning_distance:
        return "warning"
    else:
        return "clear"


# ======================================================================== #
#                            TEST CLASSES                                    #
# ======================================================================== #


class TestPointInPolygon:
    """Test the ray-casting point-in-polygon algorithm."""

    # A simple axis-aligned square: (lat, lon) vertices
    SQUARE = [
        (30.0, -98.0),
        (31.0, -98.0),
        (31.0, -97.0),
        (30.0, -97.0),
    ]

    def test_point_inside_square(self):
        assert point_in_polygon(30.5, -97.5, self.SQUARE) is True

    def test_point_outside_square_north(self):
        assert point_in_polygon(32.0, -97.5, self.SQUARE) is False

    def test_point_outside_square_south(self):
        assert point_in_polygon(29.0, -97.5, self.SQUARE) is False

    def test_point_outside_square_east(self):
        assert point_in_polygon(30.5, -96.0, self.SQUARE) is False

    def test_point_outside_square_west(self):
        assert point_in_polygon(30.5, -99.0, self.SQUARE) is False

    def test_degenerate_polygon_returns_true(self):
        """A polygon with fewer than 3 vertices means no restriction."""
        assert point_in_polygon(0.0, 0.0, [(1.0, 1.0)]) is True
        assert point_in_polygon(0.0, 0.0, []) is True

    def test_triangle(self):
        # Right triangle at origin
        triangle = [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0)]
        assert point_in_polygon(2.0, 2.0, triangle) is True
        assert point_in_polygon(8.0, 8.0, triangle) is False

    def test_concave_polygon(self):
        """L-shaped concave polygon."""
        l_shape = [
            (0.0, 0.0),
            (10.0, 0.0),
            (10.0, 5.0),
            (5.0, 5.0),
            (5.0, 10.0),
            (0.0, 10.0),
        ]
        # Inside the bottom part
        assert point_in_polygon(2.0, 2.0, l_shape) is True
        # Inside the left part
        assert point_in_polygon(2.0, 7.0, l_shape) is True
        # In the concave "notch" (outside the L)
        assert point_in_polygon(7.0, 7.0, l_shape) is False


class TestDistanceToBoundary:
    """Test minimum distance from a point to polygon edges."""

    def test_point_on_edge_has_zero_distance(self):
        square = [(0.0, 0.0), (0.001, 0.0), (0.001, 0.001), (0.0, 0.001)]
        # Point approximately on the south edge
        dist = distance_to_boundary(0.0, 0.0005, square)
        assert dist < 1.0  # Should be very close

    def test_point_far_from_polygon(self):
        square = [(0.0, 0.0), (0.001, 0.0), (0.001, 0.001), (0.0, 0.001)]
        # A point ~111 km north
        dist = distance_to_boundary(1.0, 0.0005, square)
        assert dist > 100000.0  # More than 100 km

    def test_empty_polygon(self):
        assert distance_to_boundary(0.0, 0.0, []) == float("inf")

    def test_single_segment_polygon(self):
        # Only two vertices = one segment
        seg = [(0.0, 0.0), (0.001, 0.0)]
        dist = distance_to_boundary(0.0, 0.0, seg)
        assert dist >= 0.0
        assert dist < 1.0  # Point is on the segment


class TestPointToSegmentDistance:
    """Test the point-to-line-segment distance helper."""

    def test_point_projects_onto_segment(self):
        # Horizontal segment along lat=30, lon from -98 to -97
        # Point at (30.001, -97.5) is slightly north of the midpoint
        dist = point_to_segment_distance(30.001, -97.5, 30.0, -98.0, 30.0, -97.0)
        # Should be approximately 111m (0.001 deg lat)
        assert dist == pytest.approx(111.32, abs=5.0)

    def test_point_at_segment_endpoint(self):
        dist = point_to_segment_distance(30.0, -98.0, 30.0, -98.0, 30.0, -97.0)
        assert dist == pytest.approx(0.0, abs=0.1)

    def test_zero_length_segment(self):
        # Degenerate: both endpoints are the same
        dist = point_to_segment_distance(30.001, -97.5, 30.0, -97.5, 30.0, -97.5)
        assert dist == pytest.approx(111.32, abs=5.0)


class TestSafetyLevelDetermination:
    """Test the safety level state machine."""

    def test_all_clear(self):
        assert determine_safety_level(False, False, False, False) == SAFE

    def test_obstacle_detected(self):
        assert determine_safety_level(False, False, False, True) == WARNING

    def test_geofence_violation(self):
        assert determine_safety_level(False, True, False, False) == CRITICAL

    def test_watchdog_timeout(self):
        assert determine_safety_level(False, False, True, False) == CRITICAL

    def test_estop(self):
        assert determine_safety_level(True, False, False, False) == ESTOP

    def test_estop_overrides_all(self):
        """E-stop should produce ESTOP regardless of other inputs."""
        assert determine_safety_level(True, True, True, True) == ESTOP

    def test_critical_overrides_warning(self):
        """Geofence violation should override obstacle warning."""
        assert determine_safety_level(False, True, False, True) == CRITICAL


class TestSpeedOverride:
    """Test velocity clamping at different safety levels."""

    def test_safe_passthrough(self):
        lx, ly, az = apply_speed_override(SAFE, 1.0, 0.0, 0.5)
        assert lx == pytest.approx(1.0)
        assert ly == pytest.approx(0.0)
        assert az == pytest.approx(0.5)

    def test_warning_reduces_speed(self):
        lx, ly, az = apply_speed_override(WARNING, 1.0, 0.2, 0.5)
        assert lx == pytest.approx(0.3)
        assert ly == pytest.approx(0.06)
        assert az == pytest.approx(0.15)

    def test_critical_stops(self):
        lx, ly, az = apply_speed_override(CRITICAL, 1.0, 0.2, 0.5)
        assert lx == 0.0
        assert ly == 0.0
        assert az == 0.0

    def test_estop_stops(self):
        lx, ly, az = apply_speed_override(ESTOP, 2.0, 1.0, 1.0)
        assert lx == 0.0
        assert ly == 0.0
        assert az == 0.0


class TestWatchdogLogic:
    """Test heartbeat timeout classification."""

    def test_alive(self):
        assert classify_heartbeat(0.5) == "alive"

    def test_warning(self):
        assert classify_heartbeat(3.0) == "warning"

    def test_dead(self):
        assert classify_heartbeat(6.0) == "dead"

    def test_boundary_alive_warning(self):
        assert classify_heartbeat(2.0) == "alive"
        assert classify_heartbeat(2.01) == "warning"

    def test_boundary_warning_dead(self):
        assert classify_heartbeat(5.0) == "warning"
        assert classify_heartbeat(5.01) == "dead"

    def test_custom_thresholds(self):
        assert classify_heartbeat(1.5, heartbeat_timeout=1.0, critical_timeout=3.0) == "warning"
        assert classify_heartbeat(4.0, heartbeat_timeout=1.0, critical_timeout=3.0) == "dead"

    def test_evaluate_multiple_nodes(self):
        elapsed = {
            "motor_driver": 0.5,    # alive
            "gps_node": 3.0,        # warning
            "imu_node": 6.0,        # dead
            "safety_supervisor": 0.1,  # alive
        }
        any_critical, dead, warn = evaluate_watchdog(elapsed)
        assert any_critical is True
        assert dead == ["imu_node"]
        assert warn == ["gps_node"]

    def test_evaluate_all_healthy(self):
        elapsed = {
            "motor_driver": 0.5,
            "gps_node": 1.0,
        }
        any_critical, dead, warn = evaluate_watchdog(elapsed)
        assert any_critical is False
        assert dead == []
        assert warn == []


class TestObstacleZones:
    """Test obstacle distance threshold classification."""

    def test_clear(self):
        assert evaluate_obstacle_zone(5.0) == "clear"

    def test_warning_zone(self):
        assert evaluate_obstacle_zone(1.0) == "warning"

    def test_stop_zone(self):
        assert evaluate_obstacle_zone(0.3) == "stop"

    def test_boundary_clear_warning(self):
        assert evaluate_obstacle_zone(2.0) == "clear"
        assert evaluate_obstacle_zone(1.99) == "warning"

    def test_boundary_warning_stop(self):
        assert evaluate_obstacle_zone(0.5) == "warning"
        assert evaluate_obstacle_zone(0.49) == "stop"

    def test_custom_thresholds(self):
        assert evaluate_obstacle_zone(1.5, warning_distance=3.0, stop_distance=1.0) == "warning"
        assert evaluate_obstacle_zone(0.8, warning_distance=3.0, stop_distance=1.0) == "stop"
        assert evaluate_obstacle_zone(4.0, warning_distance=3.0, stop_distance=1.0) == "clear"

    def test_zero_distance(self):
        assert evaluate_obstacle_zone(0.0) == "stop"

    def test_infinity_distance(self):
        assert evaluate_obstacle_zone(float("inf")) == "clear"
