"""Tests for the waypoint validator."""

import pytest

from striper_pathgen.waypoint_validator import validate_waypoints, ValidationResult


# ── Helpers ─────────────────────────────────────────────────────────── #

def _make_valid_mission() -> str:
    """Return a minimal valid 2-segment mission."""
    lines = [
        "QGC WPL 110",
        "0\t1\t0\t16\t0\t0\t0\t0\t30.26720000\t-97.74310000\t0.000000\t1",
        # Segment 1: transit speed, navigate, paint speed, relay on, waypoint, relay off
        "1\t0\t3\t178\t0\t1.0\t-1\t0\t0.00000000\t0.00000000\t0.000000\t1",
        "2\t0\t3\t16\t0\t0.05\t0\t0\t30.26720100\t-97.74310100\t0.000000\t1",
        "3\t0\t3\t178\t0\t0.5\t-1\t0\t0.00000000\t0.00000000\t0.000000\t1",
        "4\t0\t3\t181\t0\t1\t0\t0\t0.00000000\t0.00000000\t0.000000\t1",
        "5\t0\t3\t16\t0\t0.05\t0\t0\t30.26720500\t-97.74310500\t0.000000\t1",
        "6\t0\t3\t181\t0\t0\t0\t0\t0.00000000\t0.00000000\t0.000000\t1",
    ]
    return "\n".join(lines)


# ── Tests ───────────────────────────────────────────────────────────── #

class TestValidMission:
    def test_valid_mission_passes(self):
        result = validate_waypoints(_make_valid_mission())
        assert result.ok
        assert len(result.errors) == 0

    def test_stats_populated(self):
        result = validate_waypoints(_make_valid_mission())
        assert result.stats["total_commands"] == 7
        assert result.stats["nav_waypoints"] == 3
        assert result.stats["paint_segments"] == 1
        assert result.stats["relay_commands"] == 2
        assert result.stats["speed_commands"] == 2


class TestHeaderValidation:
    def test_empty_file(self):
        result = validate_waypoints("")
        assert not result.ok
        assert any("empty" in e.lower() for e in result.errors)

    def test_wrong_header(self):
        result = validate_waypoints("NOT A WAYPOINT FILE\n")
        assert not result.ok
        assert any("header" in e.lower() for e in result.errors)

    def test_header_only(self):
        result = validate_waypoints("QGC WPL 110\n")
        assert not result.ok
        assert any("no valid waypoints" in e.lower() for e in result.errors)


class TestSequenceNumbers:
    def test_wrong_sequence(self):
        lines = _make_valid_mission().split("\n")
        # Change seq 2 to seq 5
        fields = lines[3].split("\t")
        fields[0] = "5"
        lines[3] = "\t".join(fields)
        result = validate_waypoints("\n".join(lines))
        assert any("sequence" in e.lower() for e in result.errors)


class TestRelayBalance:
    def test_unbalanced_relay_on(self):
        """Relay ON without matching OFF."""
        lines = [
            "QGC WPL 110",
            "0\t1\t0\t16\t0\t0\t0\t0\t30.26720000\t-97.74310000\t0.000000\t1",
            "1\t0\t3\t181\t0\t1\t0\t0\t0.00000000\t0.00000000\t0.000000\t1",
            "2\t0\t3\t16\t0\t0.05\t0\t0\t30.26720500\t-97.74310500\t0.000000\t1",
        ]
        result = validate_waypoints("\n".join(lines))
        assert any("unbalanced" in e.lower() for e in result.errors)

    def test_duplicate_relay_on(self):
        """Two consecutive relay ON commands."""
        lines = [
            "QGC WPL 110",
            "0\t1\t0\t16\t0\t0\t0\t0\t30.26720000\t-97.74310000\t0.000000\t1",
            "1\t0\t3\t181\t0\t1\t0\t0\t0.00000000\t0.00000000\t0.000000\t1",
            "2\t0\t3\t181\t0\t1\t0\t0\t0.00000000\t0.00000000\t0.000000\t1",
            "3\t0\t3\t16\t0\t0.05\t0\t0\t30.26720500\t-97.74310500\t0.000000\t1",
            "4\t0\t3\t181\t0\t0\t0\t0\t0.00000000\t0.00000000\t0.000000\t1",
            "5\t0\t3\t181\t0\t0\t0\t0\t0.00000000\t0.00000000\t0.000000\t1",
        ]
        result = validate_waypoints("\n".join(lines))
        assert any("duplicate" in w.lower() for w in result.warnings)


class TestSpeedValidation:
    def test_zero_speed(self):
        lines = _make_valid_mission().split("\n")
        # Change the transit speed to 0
        fields = lines[2].split("\t")
        fields[5] = "0"
        lines[2] = "\t".join(fields)
        result = validate_waypoints("\n".join(lines))
        assert any("speed" in e.lower() and "positive" in e.lower() for e in result.errors)

    def test_very_high_speed(self):
        lines = _make_valid_mission().split("\n")
        fields = lines[2].split("\t")
        fields[5] = "10.0"
        lines[2] = "\t".join(fields)
        result = validate_waypoints("\n".join(lines))
        assert any("high" in w.lower() for w in result.warnings)


class TestGPSValidation:
    def test_latitude_out_of_range(self):
        lines = _make_valid_mission().split("\n")
        fields = lines[3].split("\t")
        fields[8] = "95.00000000"
        lines[3] = "\t".join(fields)
        result = validate_waypoints("\n".join(lines))
        assert any("latitude" in e.lower() for e in result.errors)

    def test_longitude_out_of_range(self):
        lines = _make_valid_mission().split("\n")
        fields = lines[3].split("\t")
        fields[9] = "-200.00000000"
        lines[3] = "\t".join(fields)
        result = validate_waypoints("\n".join(lines))
        assert any("longitude" in e.lower() for e in result.errors)


class TestFieldParsing:
    def test_too_few_fields(self):
        lines = [
            "QGC WPL 110",
            "0\t1\t0\t16\t0\t0",
        ]
        result = validate_waypoints("\n".join(lines))
        assert any("12 tab-separated" in e for e in result.errors)

    def test_non_numeric_field(self):
        lines = [
            "QGC WPL 110",
            "0\t1\t0\t16\t0\t0\t0\t0\tabc\t-97.743\t0.0\t1",
        ]
        result = validate_waypoints("\n".join(lines))
        assert any("parse error" in e.lower() for e in result.errors)


class TestRealWaypointsFile:
    """Validate the generated example waypoints file."""

    def test_generated_file_passes(self, tmp_path):
        """Generate a mission and validate it."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

        from striper_pathgen.models import Point2D, GeoPoint, PaintJob, PaintSegment
        from striper_pathgen.template_generator import generate_parking_row
        from striper_pathgen.path_optimizer import optimize_path_order
        from striper_pathgen.mission_planner import export_waypoints

        paths = generate_parking_row(
            origin=Point2D(0.0, 0.0),
            count=5,
            spacing=2.7432,
            length=5.4864,
            angle=0.0,
        )
        optimized = optimize_path_order(paths)
        segments = [PaintSegment(path=p, index=i) for i, p in enumerate(optimized)]
        job = PaintJob(
            job_id="test",
            segments=segments,
            datum=GeoPoint(lat=30.2672, lon=-97.7431),
        )

        content = export_waypoints(
            job=job,
            datum_lat=30.2672,
            datum_lon=-97.7431,
            datum_heading=45.0,
        )

        result = validate_waypoints(content)
        assert result.ok, f"Validation failed: {result.errors}"
        assert result.stats["paint_segments"] > 0
        assert result.stats["nav_waypoints"] > 0
