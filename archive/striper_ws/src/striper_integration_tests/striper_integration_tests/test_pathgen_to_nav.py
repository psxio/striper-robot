"""Integration tests: pathgen pipeline -> ROS2 navigation message format.

Exercises the full pipeline:
    template_generator -> path_optimizer -> coordinate_transform -> ros_converter
without requiring rclpy.  The ros_converter produces plain dicts that mirror the
PaintSegment.msg structure so that the navigation stack can consume them.
"""

from __future__ import annotations

import math
import sys
import os

import pytest

# ---------------------------------------------------------------------------
# Ensure sibling packages are importable when running from the repo root.
# ---------------------------------------------------------------------------
_ws_src = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
for _pkg in ("striper_pathgen",):
    _candidate = os.path.join(_ws_src, _pkg)
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

from striper_pathgen.models import (
    GeoPoint,
    PaintJob,
    PaintPath,
    PaintSegment,
    Point2D,
)
from striper_pathgen.template_generator import generate_parking_row
from striper_pathgen.path_optimizer import optimize_path_order
from striper_pathgen.coordinate_transform import CoordinateTransformer
from striper_pathgen.ros_converter import (
    msg_to_paint_path,
    paint_job_to_msgs,
    paint_path_to_msg,
)


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def parking_row_paths() -> list[PaintPath]:
    """Generate a 5-space parking row at the origin."""
    return generate_parking_row(
        origin=Point2D(0.0, 0.0),
        angle=0.0,
        count=5,
        spacing=2.7,
        length=5.5,
        line_width=0.1,
        color="white",
    )


@pytest.fixture
def sample_datum() -> GeoPoint:
    return GeoPoint(lat=30.2672, lon=-97.7431)


@pytest.fixture
def sample_job(parking_row_paths, sample_datum) -> PaintJob:
    segments = [
        PaintSegment(path=p, index=i) for i, p in enumerate(parking_row_paths)
    ]
    return PaintJob.create(segments=segments, datum=sample_datum, metadata={"lot": "A"})


# ── 1. Template generation produces valid paths ───────────────────────────


class TestTemplateGeneration:
    """Verify that the template generator produces usable geometry."""

    def test_parking_row_returns_paths(self, parking_row_paths):
        assert len(parking_row_paths) > 0, "Parking row should produce at least one path"

    def test_each_path_has_waypoints(self, parking_row_paths):
        for i, p in enumerate(parking_row_paths):
            assert len(p.waypoints) >= 2, (
                f"Path {i} has fewer than 2 waypoints"
            )

    def test_each_path_has_positive_length(self, parking_row_paths):
        for i, p in enumerate(parking_row_paths):
            assert p.length > 0.0, f"Path {i} has zero or negative length"

    def test_line_widths_are_set(self, parking_row_paths):
        for p in parking_row_paths:
            assert p.line_width == pytest.approx(0.1)

    def test_row_spans_expected_width(self, parking_row_paths):
        """The rightmost waypoint should be near 5*2.7 m = 13.5 m."""
        all_x = [wp.x for p in parking_row_paths for wp in p.waypoints]
        assert max(all_x) == pytest.approx(5 * 2.7, abs=0.5)


# ── 2. Optimizer does not corrupt geometry ────────────────────────────────


class TestOptimizer:
    """Ensure the path optimizer preserves path integrity."""

    def test_optimizer_preserves_count(self, parking_row_paths):
        optimized = optimize_path_order(parking_row_paths)
        assert len(optimized) == len(parking_row_paths)

    def test_optimizer_preserves_total_paint_length(self, parking_row_paths):
        original_total = sum(p.length for p in parking_row_paths)
        optimized = optimize_path_order(parking_row_paths)
        optimized_total = sum(p.length for p in optimized)
        assert optimized_total == pytest.approx(original_total, rel=1e-9)

    def test_optimizer_reduces_or_keeps_transit(self, parking_row_paths):
        from striper_pathgen.path_optimizer import calculate_total_transit_distance

        original_transit = calculate_total_transit_distance(parking_row_paths)
        optimized = optimize_path_order(parking_row_paths)
        optimized_transit = calculate_total_transit_distance(optimized)
        assert optimized_transit <= original_transit + 1e-9


# ── 3. Coordinate transform round-trip ────────────────────────────────────


class TestCoordinateTransform:
    """Verify local <-> GPS round-trip fidelity."""

    def test_round_trip_at_datum(self, sample_datum):
        xf = CoordinateTransformer.from_geopoint(sample_datum)
        local = xf.geo_to_local(sample_datum.lat, sample_datum.lon)
        assert local.x == pytest.approx(0.0, abs=1e-6)
        assert local.y == pytest.approx(0.0, abs=1e-6)

    def test_round_trip_offset(self, sample_datum):
        xf = CoordinateTransformer.from_geopoint(sample_datum)
        # Move 10m east, 10m north in local frame
        geo = xf.local_to_geo(10.0, 10.0)
        back = xf.geo_to_local(geo.lat, geo.lon)
        assert back.x == pytest.approx(10.0, abs=0.01)
        assert back.y == pytest.approx(10.0, abs=0.01)


# ── 4. ROS converter: PaintPath -> msg dict -> PaintPath ─────────────────


class TestRosConverter:
    """Test the glue layer between pathgen models and ROS2 message dicts."""

    def test_paint_path_to_msg_structure(self):
        path = PaintPath(
            waypoints=[Point2D(1.0, 2.0), Point2D(3.0, 4.0)],
            line_width=0.1,
            color="white",
            speed=0.5,
        )
        msg = paint_path_to_msg(path)

        assert "waypoints" in msg
        assert "line_width" in msg
        assert "color" in msg
        assert "speed" in msg
        assert len(msg["waypoints"]) == 2

    def test_waypoint_format(self):
        path = PaintPath(
            waypoints=[Point2D(1.5, 2.5)],
            line_width=0.1,
            color="white",
            speed=0.5,
        )
        msg = paint_path_to_msg(path)
        wp = msg["waypoints"][0]
        assert wp["x"] == pytest.approx(1.5)
        assert wp["y"] == pytest.approx(2.5)
        assert wp["z"] == pytest.approx(0.0)

    def test_round_trip_single_path(self):
        original = PaintPath(
            waypoints=[Point2D(0.0, 0.0), Point2D(5.5, 0.0), Point2D(5.5, 3.0)],
            line_width=0.15,
            color="yellow",
            speed=0.3,
        )
        msg = paint_path_to_msg(original)
        restored = msg_to_paint_path(msg)

        assert len(restored.waypoints) == len(original.waypoints)
        for orig_wp, rest_wp in zip(original.waypoints, restored.waypoints):
            assert rest_wp.x == pytest.approx(orig_wp.x)
            assert rest_wp.y == pytest.approx(orig_wp.y)
        assert restored.line_width == pytest.approx(original.line_width)
        assert restored.color == original.color
        assert restored.speed == pytest.approx(original.speed)

    def test_paint_job_to_msgs(self, sample_job):
        msgs = paint_job_to_msgs(sample_job)
        assert len(msgs) == len(sample_job.segments)
        for m in msgs:
            assert len(m["waypoints"]) >= 2
            assert m["line_width"] > 0.0


# ── 5. Full pipeline integration ─────────────────────────────────────────


class TestFullPipeline:
    """End-to-end: generate -> optimize -> transform -> convert."""

    def test_pipeline_produces_valid_messages(self, sample_datum):
        # Step 1: generate
        paths = generate_parking_row(
            origin=Point2D(0.0, 0.0), angle=0.0, count=3
        )
        assert len(paths) > 0

        # Step 2: optimize
        optimized = optimize_path_order(paths)
        assert len(optimized) == len(paths)

        # Step 3: coordinate transform (local -> GPS -> back to local to verify)
        xf = CoordinateTransformer.from_geopoint(sample_datum)
        for p in optimized:
            for wp in p.waypoints:
                geo = xf.local_to_geo(wp.x, wp.y)
                back = xf.geo_to_local(geo.lat, geo.lon)
                assert back.x == pytest.approx(wp.x, abs=0.02)
                assert back.y == pytest.approx(wp.y, abs=0.02)

        # Step 4: convert to ROS message dicts
        segments = [PaintSegment(path=p, index=i) for i, p in enumerate(optimized)]
        job = PaintJob.create(segments=segments, datum=sample_datum)
        msgs = paint_job_to_msgs(job)

        assert len(msgs) == len(optimized)
        for msg in msgs:
            assert len(msg["waypoints"]) >= 2
            assert msg["speed"] > 0.0
            assert msg["line_width"] > 0.0
            # Verify every waypoint has x, y, z
            for wp in msg["waypoints"]:
                assert "x" in wp and "y" in wp and "z" in wp
