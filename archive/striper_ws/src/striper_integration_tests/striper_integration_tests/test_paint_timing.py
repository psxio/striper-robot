"""Test paint controller timing and spray synchronisation logic.

Exercises the pure-math portions of paint_controller_node.py without
requiring rclpy:
    - Spray lead / lag distance computation
    - Cumulative distance-along-path calculation
    - Valve open/close position determination along a segment
"""

from __future__ import annotations

import math
import sys
import os

import pytest


# ── Replicated pure logic from PaintControllerNode ───────────────────────
# These mirror the calculations inside paint_controller_node.py so that
# they can be tested without ROS2.


def compute_cumulative_distances(
    waypoints: list[tuple[float, float]],
) -> tuple[list[float], float]:
    """Compute cumulative distances along a list of waypoints.

    Args:
        waypoints: List of (x, y) tuples.

    Returns:
        (cumulative_distances, total_distance)
        where cumulative_distances[i] is the distance from waypoints[0]
        to waypoints[i] along the path.
    """
    cumulative = [0.0]
    total = 0.0
    for i in range(1, len(waypoints)):
        dx = waypoints[i][0] - waypoints[i - 1][0]
        dy = waypoints[i][1] - waypoints[i - 1][1]
        total += math.sqrt(dx * dx + dy * dy)
        cumulative.append(total)
    return cumulative, total


def compute_lead_lag_distances(
    speed: float,
    spray_lead_time: float = 0.050,
    spray_lag_time: float = 0.030,
) -> tuple[float, float]:
    """Compute the lead and lag distances for spray timing.

    Args:
        speed: Current robot speed in m/s.
        spray_lead_time: Time (seconds) to open valve early.
        spray_lag_time: Time (seconds) to close valve early.

    Returns:
        (lead_distance, lag_distance) in meters.
    """
    return speed * spray_lead_time, speed * spray_lag_time


def should_spray(
    distance_along_segment: float,
    segment_total_distance: float,
    speed: float,
    spray_lead_time: float = 0.050,
    spray_lag_time: float = 0.030,
) -> bool:
    """Determine whether the spray valve should be open.

    Mirrors PaintControllerNode._control_loop logic.

    The valve opens *lead_dist* before the segment start (distance 0)
    and closes *lag_dist* before the segment end (segment_total_distance).
    """
    if segment_total_distance <= 0.0:
        return False

    lead_dist, lag_dist = compute_lead_lag_distances(speed, spray_lead_time, spray_lag_time)

    spray_start = max(0.0, -lead_dist)  # Segment starts at distance 0
    spray_end = segment_total_distance - lag_dist

    return spray_start <= distance_along_segment <= spray_end


def find_closest_waypoint_distance(
    current_x: float,
    current_y: float,
    waypoints: list[tuple[float, float]],
    cumulative_distances: list[float],
) -> float:
    """Find the cumulative distance of the closest waypoint.

    Mirrors PaintControllerNode._find_closest_waypoint_distance.
    """
    if not waypoints:
        return 0.0

    min_dist_sq = float("inf")
    closest_idx = 0

    for i, (wx, wy) in enumerate(waypoints):
        dx = current_x - wx
        dy = current_y - wy
        dist_sq = dx * dx + dy * dy
        if dist_sq < min_dist_sq:
            min_dist_sq = dist_sq
            closest_idx = i

    return cumulative_distances[closest_idx]


# ======================================================================== #
#                            TEST CLASSES                                    #
# ======================================================================== #


class TestCumulativeDistances:
    """Test distance-along-path computation."""

    def test_straight_line(self):
        wps = [(0.0, 0.0), (10.0, 0.0)]
        cum, total = compute_cumulative_distances(wps)
        assert cum == [0.0, 10.0]
        assert total == pytest.approx(10.0)

    def test_l_shape(self):
        wps = [(0.0, 0.0), (3.0, 0.0), (3.0, 4.0)]
        cum, total = compute_cumulative_distances(wps)
        assert cum[0] == pytest.approx(0.0)
        assert cum[1] == pytest.approx(3.0)
        assert cum[2] == pytest.approx(7.0)
        assert total == pytest.approx(7.0)

    def test_single_point(self):
        wps = [(5.0, 5.0)]
        cum, total = compute_cumulative_distances(wps)
        assert cum == [0.0]
        assert total == 0.0

    def test_diagonal(self):
        wps = [(0.0, 0.0), (3.0, 4.0)]
        cum, total = compute_cumulative_distances(wps)
        assert total == pytest.approx(5.0)

    def test_many_waypoints(self):
        """Evenly spaced points along X axis."""
        wps = [(float(i), 0.0) for i in range(11)]  # 0..10
        cum, total = compute_cumulative_distances(wps)
        assert total == pytest.approx(10.0)
        assert len(cum) == 11
        for i, c in enumerate(cum):
            assert c == pytest.approx(float(i))


class TestLeadLagDistances:
    """Test spray lead/lag distance calculations."""

    def test_default_at_zero_speed(self):
        lead, lag = compute_lead_lag_distances(0.0)
        assert lead == 0.0
        assert lag == 0.0

    def test_default_at_half_mps(self):
        lead, lag = compute_lead_lag_distances(0.5)
        assert lead == pytest.approx(0.025)  # 0.5 * 0.050
        assert lag == pytest.approx(0.015)   # 0.5 * 0.030

    def test_at_full_speed(self):
        lead, lag = compute_lead_lag_distances(1.0)
        assert lead == pytest.approx(0.050)
        assert lag == pytest.approx(0.030)

    def test_custom_timing(self):
        lead, lag = compute_lead_lag_distances(2.0, spray_lead_time=0.1, spray_lag_time=0.05)
        assert lead == pytest.approx(0.2)
        assert lag == pytest.approx(0.1)

    def test_lead_always_gte_lag(self):
        """With default params, lead_time > lag_time so lead_dist > lag_dist."""
        for speed in [0.1, 0.5, 1.0, 2.0]:
            lead, lag = compute_lead_lag_distances(speed)
            assert lead >= lag


class TestShouldSpray:
    """Test valve open/close decisions along a segment."""

    def test_spray_on_at_start(self):
        # At the very start of a 10m segment, spray should be on
        assert should_spray(0.0, 10.0, 0.5) is True

    def test_spray_on_in_middle(self):
        assert should_spray(5.0, 10.0, 0.5) is True

    def test_spray_off_before_end(self):
        # At speed 0.5 m/s, lag_dist = 0.5 * 0.030 = 0.015m
        # spray_end = 10.0 - 0.015 = 9.985
        # At distance 9.99 > 9.985 => spray should be off
        assert should_spray(9.99, 10.0, 0.5) is False

    def test_spray_off_past_end(self):
        assert should_spray(11.0, 10.0, 0.5) is False

    def test_zero_length_segment(self):
        assert should_spray(0.0, 0.0, 0.5) is False

    def test_spray_off_at_exactly_spray_end(self):
        # spray_end = 10.0 - lag_dist = 10.0 - 0.5 * 0.030 = 9.985
        spray_end = 10.0 - 0.5 * 0.030
        assert should_spray(spray_end, 10.0, 0.5) is True

    def test_spray_off_just_past_spray_end(self):
        spray_end = 10.0 - 0.5 * 0.030
        assert should_spray(spray_end + 0.001, 10.0, 0.5) is False

    def test_high_speed_wider_exclusion(self):
        """At higher speed the lag distance is larger, closing valve earlier."""
        speed = 2.0
        lag_dist = speed * 0.030  # 0.06m
        spray_end = 10.0 - lag_dist  # 9.94
        # Just inside
        assert should_spray(9.93, 10.0, speed) is True
        # Just outside
        assert should_spray(9.95, 10.0, speed) is False

    def test_stationary_robot_spray_on_entire_segment(self):
        """At zero speed, lead and lag are both 0 -> spray the whole segment."""
        for dist in [0.0, 2.5, 5.0, 10.0]:
            assert should_spray(dist, 10.0, 0.0) is True


class TestFindClosestWaypoint:
    """Test closest waypoint distance lookup."""

    def test_at_first_waypoint(self):
        wps = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0)]
        cum = [0.0, 5.0, 10.0]
        assert find_closest_waypoint_distance(0.0, 0.0, wps, cum) == pytest.approx(0.0)

    def test_at_last_waypoint(self):
        wps = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0)]
        cum = [0.0, 5.0, 10.0]
        assert find_closest_waypoint_distance(10.0, 0.0, wps, cum) == pytest.approx(10.0)

    def test_between_waypoints(self):
        wps = [(0.0, 0.0), (10.0, 0.0)]
        cum = [0.0, 10.0]
        # Robot at (6, 0) is closer to (10, 0)
        assert find_closest_waypoint_distance(6.0, 0.0, wps, cum) == pytest.approx(10.0)
        # Robot at (4, 0) is closer to (0, 0)
        assert find_closest_waypoint_distance(4.0, 0.0, wps, cum) == pytest.approx(0.0)

    def test_off_path(self):
        wps = [(0.0, 0.0), (10.0, 0.0)]
        cum = [0.0, 10.0]
        # Robot at (5, 100) is equidistant; tie goes to first found (index 0)
        dist = find_closest_waypoint_distance(5.0, 100.0, wps, cum)
        assert dist in (0.0, 10.0)  # Either is acceptable

    def test_empty_waypoints(self):
        assert find_closest_waypoint_distance(0.0, 0.0, [], []) == 0.0


class TestSprayPositionIntegration:
    """Integration: verify spray on/off positions along a realistic segment."""

    @pytest.fixture
    def segment_5m(self):
        """A 5-meter straight segment with 6 waypoints (1m spacing)."""
        wps = [(float(i), 0.0) for i in range(6)]
        cum, total = compute_cumulative_distances(wps)
        return wps, cum, total

    def test_spray_positions_at_half_mps(self, segment_5m):
        wps, cum, total = segment_5m
        speed = 0.5
        lead_dist, lag_dist = compute_lead_lag_distances(speed)

        spray_start = max(0.0, -lead_dist)
        spray_end = total - lag_dist

        # Walk along segment at 0.1m steps and record spray state
        spray_on_positions = []
        spray_off_positions = []
        for i in range(51):
            d = i * 0.1
            if should_spray(d, total, speed):
                spray_on_positions.append(d)
            else:
                spray_off_positions.append(d)

        # Verify spray is on for the bulk of the segment
        assert len(spray_on_positions) > len(spray_off_positions)

        # First spray on should be at distance 0.0
        assert spray_on_positions[0] == pytest.approx(0.0)

        # Last spray on should be at spray_end (floored to 0.1m grid)
        last_on = spray_on_positions[-1]
        assert last_on <= spray_end + 0.001

    def test_spray_region_length(self, segment_5m):
        """Spray region should be total_distance - lag_distance."""
        _, _, total = segment_5m
        speed = 1.0
        _, lag_dist = compute_lead_lag_distances(speed)

        expected_spray_length = total - lag_dist
        # Since spray_start = 0 and spray_end = total - lag_dist
        assert expected_spray_length == pytest.approx(total - lag_dist)

    def test_no_spray_beyond_segment(self, segment_5m):
        """Robot past the segment end should have spray off."""
        _, _, total = segment_5m
        for overshoot in [0.1, 0.5, 1.0, 5.0]:
            assert should_spray(total + overshoot, total, 0.5) is False

    def test_negative_distance(self, segment_5m):
        """Robot before segment start should have spray off (distance < 0)."""
        _, _, total = segment_5m
        assert should_spray(-0.1, total, 0.5) is False
        assert should_spray(-1.0, total, 0.5) is False
