"""Tests for striper_pathgen.mission_planner — ArduPilot waypoint export."""

from __future__ import annotations

import math

import pytest

from striper_pathgen.models import (
    GeoPoint,
    PaintJob,
    PaintPath,
    PaintSegment,
    Point2D,
)
from striper_pathgen.mission_planner import (
    MAV_CMD_DO_CHANGE_SPEED,
    MAV_CMD_DO_SET_RELAY,
    MAV_CMD_NAV_WAYPOINT,
    MAV_FRAME_GLOBAL,
    MAV_FRAME_GLOBAL_RELATIVE_ALT,
    PAINT_RELAY_CHANNEL,
    _interpolate_path,
    export_waypoints,
    save_waypoints,
)
from striper_pathgen.template_generator import generate_standard_space


# ── Helpers ───────────────────────────────────────────────────────────── #


def _make_job(segments: list[PaintSegment] | None = None) -> PaintJob:
    """Create a PaintJob with the given segments (or empty)."""
    return PaintJob(
        job_id="test-mission-001",
        segments=segments or [],
        datum=GeoPoint(lat=30.2672, lon=-97.7431),
    )


def _make_single_segment_job() -> PaintJob:
    """Create a job with one short horizontal paint segment."""
    path = PaintPath(
        waypoints=[Point2D(0.0, 0.0), Point2D(5.0, 0.0)],
        line_width=0.1,
        color="white",
        speed=0.5,
    )
    seg = PaintSegment(path=path, index=0)
    return _make_job([seg])


def _make_multi_segment_job() -> PaintJob:
    """Create a job with three paint segments."""
    paths = [
        PaintPath(
            waypoints=[Point2D(0.0, 0.0), Point2D(0.0, 5.5)],
        ),
        PaintPath(
            waypoints=[Point2D(2.7, 0.0), Point2D(2.7, 5.5)],
        ),
        PaintPath(
            waypoints=[Point2D(5.4, 0.0), Point2D(5.4, 5.5)],
        ),
    ]
    segments = [PaintSegment(path=p, index=i) for i, p in enumerate(paths)]
    return _make_job(segments)


def _parse_waypoint_line(line: str) -> dict:
    """Parse a waypoint line into a dict with named fields."""
    parts = line.split("\t")
    return {
        "seq": int(parts[0]),
        "current": int(parts[1]),
        "frame": int(parts[2]),
        "command": int(parts[3]),
        "p1": float(parts[4]),
        "p2": float(parts[5]),
        "p3": float(parts[6]),
        "p4": float(parts[7]),
        "lat": float(parts[8]),
        "lon": float(parts[9]),
        "alt": float(parts[10]),
        "autocontinue": int(parts[11]),
    }


def _get_waypoint_lines(content: str) -> list[str]:
    """Return all waypoint lines (excluding the header)."""
    lines = content.strip().split("\n")
    assert lines[0] == "QGC WPL 110"
    return lines[1:]


# ══════════════════════════════════════════════════════════════════════════ #
#  Header / Format Tests
# ══════════════════════════════════════════════════════════════════════════ #


class TestWaypointFileFormat:
    """Verify the overall .waypoints file structure."""

    def test_starts_with_header(self):
        job = _make_single_segment_job()
        content = export_waypoints(job, 30.2672, -97.7431)
        lines = content.strip().split("\n")
        assert lines[0] == "QGC WPL 110"

    def test_home_is_first_waypoint(self):
        job = _make_single_segment_job()
        content = export_waypoints(job, 30.2672, -97.7431)
        wp_lines = _get_waypoint_lines(content)
        home = _parse_waypoint_line(wp_lines[0])
        assert home["seq"] == 0
        assert home["current"] == 1
        assert home["frame"] == MAV_FRAME_GLOBAL
        assert home["command"] == MAV_CMD_NAV_WAYPOINT

    def test_home_position_matches_datum(self):
        job = _make_single_segment_job()
        lat, lon = 30.2672, -97.7431
        content = export_waypoints(job, lat, lon)
        wp_lines = _get_waypoint_lines(content)
        home = _parse_waypoint_line(wp_lines[0])
        assert math.isclose(home["lat"], lat, abs_tol=1e-6)
        assert math.isclose(home["lon"], lon, abs_tol=1e-6)

    def test_sequential_sequence_numbers(self):
        job = _make_multi_segment_job()
        content = export_waypoints(job, 30.2672, -97.7431)
        wp_lines = _get_waypoint_lines(content)
        for i, line in enumerate(wp_lines):
            wp = _parse_waypoint_line(line)
            assert wp["seq"] == i

    def test_only_home_has_current_1(self):
        job = _make_multi_segment_job()
        content = export_waypoints(job, 30.2672, -97.7431)
        wp_lines = _get_waypoint_lines(content)
        for line in wp_lines:
            wp = _parse_waypoint_line(line)
            if wp["seq"] == 0:
                assert wp["current"] == 1
            else:
                assert wp["current"] == 0

    def test_tab_separated_fields(self):
        job = _make_single_segment_job()
        content = export_waypoints(job, 30.2672, -97.7431)
        for line in content.strip().split("\n")[1:]:
            parts = line.split("\t")
            assert len(parts) == 12, f"Expected 12 tab-separated fields, got {len(parts)}"


# ══════════════════════════════════════════════════════════════════════════ #
#  Empty Job
# ══════════════════════════════════════════════════════════════════════════ #


class TestEmptyJob:
    """Verify behaviour with an empty PaintJob."""

    def test_empty_job_has_header_and_home(self):
        job = _make_job()
        content = export_waypoints(job, 30.2672, -97.7431)
        lines = content.strip().split("\n")
        assert lines[0] == "QGC WPL 110"
        assert len(lines) == 2  # header + home only

    def test_empty_job_home_waypoint(self):
        job = _make_job()
        content = export_waypoints(job, 30.2672, -97.7431)
        wp_lines = _get_waypoint_lines(content)
        assert len(wp_lines) == 1
        home = _parse_waypoint_line(wp_lines[0])
        assert home["seq"] == 0
        assert home["current"] == 1


# ══════════════════════════════════════════════════════════════════════════ #
#  Relay Sequencing
# ══════════════════════════════════════════════════════════════════════════ #


class TestRelaySequencing:
    """Verify DO_SET_RELAY commands bracket each paint segment."""

    def test_single_segment_relay_on_off(self):
        job = _make_single_segment_job()
        content = export_waypoints(job, 30.2672, -97.7431)
        wp_lines = _get_waypoint_lines(content)

        relay_cmds = [
            _parse_waypoint_line(line) for line in wp_lines
            if _parse_waypoint_line(line)["command"] == MAV_CMD_DO_SET_RELAY
        ]
        assert len(relay_cmds) == 2
        assert relay_cmds[0]["p1"] == PAINT_RELAY_CHANNEL
        assert relay_cmds[0]["p2"] == 1  # ON
        assert relay_cmds[1]["p1"] == PAINT_RELAY_CHANNEL
        assert relay_cmds[1]["p2"] == 0  # OFF

    def test_multi_segment_relay_on_off_pairs(self):
        job = _make_multi_segment_job()
        content = export_waypoints(job, 30.2672, -97.7431)
        wp_lines = _get_waypoint_lines(content)

        relay_cmds = [
            _parse_waypoint_line(line) for line in wp_lines
            if _parse_waypoint_line(line)["command"] == MAV_CMD_DO_SET_RELAY
        ]
        # 3 segments -> 3 ON + 3 OFF = 6 relay commands
        assert len(relay_cmds) == 6

        # Verify alternating ON/OFF pattern
        for i, cmd in enumerate(relay_cmds):
            if i % 2 == 0:
                assert cmd["p2"] == 1, f"Relay command {i} should be ON"
            else:
                assert cmd["p2"] == 0, f"Relay command {i} should be OFF"

    def test_relay_off_is_last_per_segment(self):
        """The relay OFF command should come after all NAV waypoints for each segment."""
        job = _make_single_segment_job()
        content = export_waypoints(job, 30.2672, -97.7431)
        wp_lines = _get_waypoint_lines(content)

        wps = [_parse_waypoint_line(line) for line in wp_lines]

        # Find the relay ON and OFF positions
        relay_on_seq = None
        relay_off_seq = None
        last_nav_seq = None
        for wp in wps:
            if wp["command"] == MAV_CMD_DO_SET_RELAY and wp["p2"] == 1:
                relay_on_seq = wp["seq"]
            if wp["command"] == MAV_CMD_DO_SET_RELAY and wp["p2"] == 0:
                relay_off_seq = wp["seq"]
            if wp["command"] == MAV_CMD_NAV_WAYPOINT and wp["seq"] > 0:
                last_nav_seq = wp["seq"]

        assert relay_on_seq is not None
        assert relay_off_seq is not None
        assert last_nav_seq is not None
        # Relay ON should come before nav waypoints during painting
        assert relay_on_seq < last_nav_seq
        # Relay OFF should come after all nav waypoints
        assert relay_off_seq > last_nav_seq


# ══════════════════════════════════════════════════════════════════════════ #
#  Speed Commands
# ══════════════════════════════════════════════════════════════════════════ #


class TestSpeedCommands:
    """Verify DO_CHANGE_SPEED commands set correct speeds."""

    def test_transit_and_paint_speeds(self):
        job = _make_single_segment_job()
        content = export_waypoints(
            job, 30.2672, -97.7431,
            paint_speed=0.4, transit_speed=1.2,
        )
        wp_lines = _get_waypoint_lines(content)
        speed_cmds = [
            _parse_waypoint_line(line) for line in wp_lines
            if _parse_waypoint_line(line)["command"] == MAV_CMD_DO_CHANGE_SPEED
        ]

        # First speed command is transit, second is paint
        assert len(speed_cmds) >= 2
        assert math.isclose(speed_cmds[0]["p2"], 1.2)  # transit
        assert math.isclose(speed_cmds[1]["p2"], 0.4)  # paint

    def test_speed_commands_per_segment(self):
        job = _make_multi_segment_job()
        content = export_waypoints(job, 30.2672, -97.7431)
        wp_lines = _get_waypoint_lines(content)
        speed_cmds = [
            _parse_waypoint_line(line) for line in wp_lines
            if _parse_waypoint_line(line)["command"] == MAV_CMD_DO_CHANGE_SPEED
        ]
        # 3 segments * 2 speed commands each = 6
        assert len(speed_cmds) == 6

    def test_default_speeds(self):
        job = _make_single_segment_job()
        content = export_waypoints(job, 30.2672, -97.7431)
        wp_lines = _get_waypoint_lines(content)
        speed_cmds = [
            _parse_waypoint_line(line) for line in wp_lines
            if _parse_waypoint_line(line)["command"] == MAV_CMD_DO_CHANGE_SPEED
        ]
        assert math.isclose(speed_cmds[0]["p2"], 1.0)  # default transit
        assert math.isclose(speed_cmds[1]["p2"], 0.5)  # default paint

    def test_speed_type_is_ground_speed(self):
        job = _make_single_segment_job()
        content = export_waypoints(job, 30.2672, -97.7431)
        wp_lines = _get_waypoint_lines(content)
        speed_cmds = [
            _parse_waypoint_line(line) for line in wp_lines
            if _parse_waypoint_line(line)["command"] == MAV_CMD_DO_CHANGE_SPEED
        ]
        for cmd in speed_cmds:
            assert cmd["p1"] == 0  # ground speed type


# ══════════════════════════════════════════════════════════════════════════ #
#  GPS Coordinates
# ══════════════════════════════════════════════════════════════════════════ #


class TestGPSCoordinates:
    """Verify that waypoint coordinates are valid GPS (not local)."""

    def test_waypoints_have_valid_gps(self):
        job = _make_single_segment_job()
        content = export_waypoints(job, 30.2672, -97.7431)
        wp_lines = _get_waypoint_lines(content)

        for line in wp_lines:
            wp = _parse_waypoint_line(line)
            if wp["command"] == MAV_CMD_NAV_WAYPOINT:
                # GPS coordinates should be in reasonable range
                assert -90 <= wp["lat"] <= 90, f"Invalid latitude: {wp['lat']}"
                assert -180 <= wp["lon"] <= 180, f"Invalid longitude: {wp['lon']}"
                # Should not be exactly 0,0 (which would mean local coords leaked)
                if wp["seq"] > 0:
                    # Non-home waypoints should be near the datum
                    assert abs(wp["lat"] - 30.2672) < 0.01
                    assert abs(wp["lon"] - (-97.7431)) < 0.01

    def test_non_nav_commands_have_zero_coords(self):
        """DO commands (speed, relay) should have 0,0 coordinates."""
        job = _make_single_segment_job()
        content = export_waypoints(job, 30.2672, -97.7431)
        wp_lines = _get_waypoint_lines(content)

        for line in wp_lines:
            wp = _parse_waypoint_line(line)
            if wp["command"] in (MAV_CMD_DO_CHANGE_SPEED, MAV_CMD_DO_SET_RELAY):
                assert wp["lat"] == 0.0
                assert wp["lon"] == 0.0

    def test_heading_rotation_affects_coordinates(self):
        job = _make_single_segment_job()
        content_0 = export_waypoints(job, 30.2672, -97.7431, datum_heading=0.0)
        content_45 = export_waypoints(job, 30.2672, -97.7431, datum_heading=45.0)

        nav_0 = [
            _parse_waypoint_line(line) for line in _get_waypoint_lines(content_0)
            if _parse_waypoint_line(line)["command"] == MAV_CMD_NAV_WAYPOINT
            and _parse_waypoint_line(line)["seq"] > 0
        ]
        nav_45 = [
            _parse_waypoint_line(line) for line in _get_waypoint_lines(content_45)
            if _parse_waypoint_line(line)["command"] == MAV_CMD_NAV_WAYPOINT
            and _parse_waypoint_line(line)["seq"] > 0
        ]

        # With heading=45, the end waypoint should be at a different GPS
        # location than with heading=0
        assert not math.isclose(nav_0[-1]["lat"], nav_45[-1]["lat"], abs_tol=1e-7)


# ══════════════════════════════════════════════════════════════════════════ #
#  Path Interpolation
# ══════════════════════════════════════════════════════════════════════════ #


class TestInterpolatePath:
    """Verify that _interpolate_path creates intermediate points correctly."""

    def test_short_path_no_interpolation(self):
        """A path shorter than spacing should not add extra points."""
        path = PaintPath(waypoints=[Point2D(0, 0), Point2D(0.3, 0)])
        result = _interpolate_path(path, spacing=0.5)
        assert len(result) == 2

    def test_exact_spacing(self):
        """A 1.0m path with 0.5m spacing should have 3 points (start, mid, end)."""
        path = PaintPath(waypoints=[Point2D(0, 0), Point2D(1.0, 0)])
        result = _interpolate_path(path, spacing=0.5)
        assert len(result) == 3
        assert math.isclose(result[1].x, 0.5, abs_tol=1e-9)

    def test_spacing_preserved(self):
        """All consecutive points should be at most spacing apart."""
        path = PaintPath(waypoints=[Point2D(0, 0), Point2D(3.7, 0)])
        result = _interpolate_path(path, spacing=0.5)
        for i in range(len(result) - 1):
            dist = result[i].distance_to(result[i + 1])
            assert dist <= 0.5 + 1e-9, f"Gap {dist:.3f}m between points {i} and {i+1}"

    def test_original_endpoints_preserved(self):
        """The first and last waypoints must be the originals."""
        path = PaintPath(waypoints=[Point2D(1.0, 2.0), Point2D(5.0, 6.0)])
        result = _interpolate_path(path, spacing=0.5)
        assert result[0].x == 1.0 and result[0].y == 2.0
        assert result[-1].x == 5.0 and result[-1].y == 6.0

    def test_multi_segment_path(self):
        """An L-shaped path should interpolate both legs."""
        path = PaintPath(
            waypoints=[Point2D(0, 0), Point2D(2.0, 0), Point2D(2.0, 2.0)]
        )
        result = _interpolate_path(path, spacing=0.5)
        # 2.0m per leg / 0.5m spacing = 4 intervals per leg = 5 points per leg
        # Shared corner point, so total = 5 + 4 = 9
        assert len(result) == 9
        # Corner point should be preserved
        assert any(
            math.isclose(p.x, 2.0, abs_tol=1e-9) and math.isclose(p.y, 0.0, abs_tol=1e-9)
            for p in result
        )

    def test_single_point_path(self):
        """A path with one waypoint should return that point."""
        path = PaintPath(waypoints=[Point2D(3.0, 4.0)])
        result = _interpolate_path(path, spacing=0.5)
        assert len(result) == 1
        assert result[0].x == 3.0

    def test_large_spacing_no_interpolation(self):
        """If spacing > segment length, only original points are returned."""
        path = PaintPath(waypoints=[Point2D(0, 0), Point2D(1.0, 0)])
        result = _interpolate_path(path, spacing=5.0)
        assert len(result) == 2

    def test_points_are_collinear(self):
        """Interpolated points on a straight segment should be collinear."""
        path = PaintPath(waypoints=[Point2D(0, 0), Point2D(10.0, 0)])
        result = _interpolate_path(path, spacing=0.5)
        for pt in result:
            assert math.isclose(pt.y, 0.0, abs_tol=1e-9)


# ══════════════════════════════════════════════════════════════════════════ #
#  Waypoint Count
# ══════════════════════════════════════════════════════════════════════════ #


class TestWaypointCount:
    """Verify expected waypoint counts for known inputs."""

    def test_single_short_segment_count(self):
        """A 2m path with 0.5m spacing: 5 nav points (start + 3 interp + end),
        plus 1 home + 1 transit_speed + 1 paint_speed + 1 relay_on + 1 relay_off = 10 total."""
        path = PaintPath(waypoints=[Point2D(0, 0), Point2D(2.0, 0)])
        seg = PaintSegment(path=path, index=0)
        job = _make_job([seg])
        content = export_waypoints(job, 30.0, -97.0, waypoint_spacing=0.5)
        wp_lines = _get_waypoint_lines(content)

        # home(1) + transit_speed(1) + nav_start(1) + paint_speed(1)
        # + relay_on(1) + nav_interp(3) + nav_end(1) ... wait, let's re-check.
        # Interpolation of 2m at 0.5m spacing: ceil(2/0.5) = 4 intervals -> 5 points
        # start navigated to separately, then 4 more points in the paint loop
        # Total: home + transit_speed + nav_start + paint_speed + relay_on
        #        + 4 nav_paint + relay_off = 10
        assert len(wp_lines) == 10


# ══════════════════════════════════════════════════════════════════════════ #
#  Round-Trip: Template -> Export -> Verify
# ══════════════════════════════════════════════════════════════════════════ #


class TestRoundTrip:
    """Generate from template, export to waypoints, verify structure."""

    def test_standard_space_round_trip(self):
        """Generate a standard parking space and export to waypoints."""
        paths = generate_standard_space(
            origin=Point2D(0.0, 0.0), angle=0.0,
        )
        segments = [PaintSegment(path=p, index=i) for i, p in enumerate(paths)]
        job = PaintJob(
            job_id="round-trip-test",
            segments=segments,
            datum=GeoPoint(lat=30.2672, lon=-97.7431),
        )

        content = export_waypoints(job, 30.2672, -97.7431)
        lines = content.strip().split("\n")

        # Header present
        assert lines[0] == "QGC WPL 110"

        # At least home + some waypoints
        assert len(lines) > 2

        # Parse all lines to verify valid format
        for line in lines[1:]:
            wp = _parse_waypoint_line(line)
            assert wp["autocontinue"] == 1

        # Verify relay pairs for 2 segments
        wp_lines = _get_waypoint_lines(content)
        relay_cmds = [
            _parse_waypoint_line(line) for line in wp_lines
            if _parse_waypoint_line(line)["command"] == MAV_CMD_DO_SET_RELAY
        ]
        assert len(relay_cmds) == 4  # 2 segments * 2 (on + off)

    def test_multi_space_round_trip(self):
        """Generate multiple spaces, export, verify segment count."""
        all_paths = []
        for i in range(5):
            space_paths = generate_standard_space(
                origin=Point2D(i * 2.7, 0.0), angle=0.0,
            )
            all_paths.extend(space_paths)

        segments = [PaintSegment(path=p, index=i) for i, p in enumerate(all_paths)]
        job = PaintJob(
            job_id="multi-space-test",
            segments=segments,
            datum=GeoPoint(lat=40.758, lon=-73.985),
        )

        content = export_waypoints(job, 40.758, -73.985)
        wp_lines = _get_waypoint_lines(content)

        # 5 spaces * 2 lines = 10 segments -> 10 relay ON + 10 relay OFF
        relay_cmds = [
            _parse_waypoint_line(line) for line in wp_lines
            if _parse_waypoint_line(line)["command"] == MAV_CMD_DO_SET_RELAY
        ]
        assert len(relay_cmds) == 20


# ══════════════════════════════════════════════════════════════════════════ #
#  File I/O
# ══════════════════════════════════════════════════════════════════════════ #


class TestSaveWaypoints:
    """Test file writing via save_waypoints."""

    def test_save_and_read_back(self, tmp_path):
        job = _make_single_segment_job()
        filepath = str(tmp_path / "test_mission.waypoints")

        save_waypoints(
            job, filepath,
            datum_lat=30.2672, datum_lon=-97.7431,
        )

        with open(filepath) as f:
            content = f.read()

        assert content.startswith("QGC WPL 110")
        lines = content.strip().split("\n")
        assert len(lines) > 2

    def test_saved_matches_export(self, tmp_path):
        job = _make_single_segment_job()
        filepath = str(tmp_path / "test_match.waypoints")

        expected = export_waypoints(job, 30.2672, -97.7431)
        save_waypoints(job, filepath, datum_lat=30.2672, datum_lon=-97.7431)

        with open(filepath) as f:
            saved = f.read()

        assert saved == expected


# ══════════════════════════════════════════════════════════════════════════ #
#  Command Ordering Within a Segment
# ══════════════════════════════════════════════════════════════════════════ #


class TestCommandOrdering:
    """Verify the command sequence within each paint segment."""

    def test_single_segment_command_order(self):
        """For a single segment, verify the exact command sequence."""
        job = _make_single_segment_job()
        content = export_waypoints(job, 30.2672, -97.7431)
        wp_lines = _get_waypoint_lines(content)
        wps = [_parse_waypoint_line(line) for line in wp_lines]

        # Expected order after home:
        # [0] home (NAV_WAYPOINT)
        # [1] DO_CHANGE_SPEED (transit)
        # [2] NAV_WAYPOINT (start)
        # [3] DO_CHANGE_SPEED (paint)
        # [4] DO_SET_RELAY (on)
        # [5..N-1] NAV_WAYPOINT (paint path)
        # [N] DO_SET_RELAY (off)

        assert wps[0]["command"] == MAV_CMD_NAV_WAYPOINT      # home
        assert wps[1]["command"] == MAV_CMD_DO_CHANGE_SPEED    # transit speed
        assert wps[2]["command"] == MAV_CMD_NAV_WAYPOINT       # move to start
        assert wps[3]["command"] == MAV_CMD_DO_CHANGE_SPEED    # paint speed
        assert wps[4]["command"] == MAV_CMD_DO_SET_RELAY       # relay on
        assert wps[4]["p2"] == 1
        assert wps[-1]["command"] == MAV_CMD_DO_SET_RELAY      # relay off
        assert wps[-1]["p2"] == 0

        # Everything between relay on and relay off should be NAV_WAYPOINT
        for wp in wps[5:-1]:
            assert wp["command"] == MAV_CMD_NAV_WAYPOINT

    def test_frame_is_relative_alt_for_mission_commands(self):
        """All non-home commands should use MAV_FRAME_GLOBAL_RELATIVE_ALT."""
        job = _make_single_segment_job()
        content = export_waypoints(job, 30.2672, -97.7431)
        wp_lines = _get_waypoint_lines(content)

        for line in wp_lines:
            wp = _parse_waypoint_line(line)
            if wp["seq"] == 0:
                assert wp["frame"] == MAV_FRAME_GLOBAL
            else:
                assert wp["frame"] == MAV_FRAME_GLOBAL_RELATIVE_ALT
