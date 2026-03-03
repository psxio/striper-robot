"""Tests for striper_pathgen.models — dataclasses, serialization, defaults."""

from __future__ import annotations

import json
import math
import uuid

import pytest

from striper_pathgen.models import (
    GeoPoint,
    PaintJob,
    PaintPath,
    PaintSegment,
    Point2D,
    TransitPath,
)


# ══════════════════════════════════════════════════════════════════════════ #
#  Point2D
# ══════════════════════════════════════════════════════════════════════════ #

class TestPoint2D:
    """Tests for the Point2D dataclass."""

    def test_creation(self):
        p = Point2D(3.0, 4.0)
        assert p.x == 3.0
        assert p.y == 4.0

    def test_distance_to_origin(self, origin_point):
        p = Point2D(3.0, 4.0)
        assert math.isclose(p.distance_to(origin_point), 5.0)

    def test_distance_to_self(self):
        p = Point2D(7.0, 11.0)
        assert p.distance_to(p) == 0.0

    def test_distance_symmetry(self):
        a = Point2D(1.0, 2.0)
        b = Point2D(4.0, 6.0)
        assert math.isclose(a.distance_to(b), b.distance_to(a))

    def test_to_dict(self):
        p = Point2D(1.5, -2.5)
        d = p.to_dict()
        assert d == {"x": 1.5, "y": -2.5}

    def test_from_dict(self):
        p = Point2D.from_dict({"x": 3.14, "y": 2.72})
        assert p.x == 3.14
        assert p.y == 2.72

    def test_round_trip_dict(self):
        original = Point2D(99.9, -0.1)
        reconstructed = Point2D.from_dict(original.to_dict())
        assert reconstructed.x == original.x
        assert reconstructed.y == original.y

    def test_equality(self):
        assert Point2D(1.0, 2.0) == Point2D(1.0, 2.0)

    def test_inequality(self):
        assert Point2D(1.0, 2.0) != Point2D(1.0, 3.0)

    def test_negative_coordinates(self):
        p = Point2D(-5.0, -10.0)
        assert p.x == -5.0
        assert p.y == -10.0


# ══════════════════════════════════════════════════════════════════════════ #
#  GeoPoint
# ══════════════════════════════════════════════════════════════════════════ #

class TestGeoPoint:
    """Tests for the GeoPoint dataclass."""

    def test_creation_with_defaults(self):
        g = GeoPoint(lat=30.0, lon=-97.0)
        assert g.lat == 30.0
        assert g.lon == -97.0
        assert g.alt == 0.0

    def test_creation_with_altitude(self, sample_geopoint):
        assert sample_geopoint.alt == 150.0

    def test_to_dict(self, sample_geopoint):
        d = sample_geopoint.to_dict()
        assert d == {"lat": 30.2672, "lon": -97.7431, "alt": 150.0}

    def test_from_dict_with_alt(self):
        g = GeoPoint.from_dict({"lat": 40.0, "lon": -74.0, "alt": 10.0})
        assert g.lat == 40.0
        assert g.lon == -74.0
        assert g.alt == 10.0

    def test_from_dict_without_alt(self):
        g = GeoPoint.from_dict({"lat": 40.0, "lon": -74.0})
        assert g.alt == 0.0

    def test_round_trip_dict(self, sample_geopoint):
        reconstructed = GeoPoint.from_dict(sample_geopoint.to_dict())
        assert reconstructed == sample_geopoint


# ══════════════════════════════════════════════════════════════════════════ #
#  PaintPath
# ══════════════════════════════════════════════════════════════════════════ #

class TestPaintPath:
    """Tests for the PaintPath dataclass."""

    def test_default_values(self):
        pp = PaintPath(waypoints=[Point2D(0, 0), Point2D(1, 0)])
        assert pp.line_width == 0.1
        assert pp.color == "white"
        assert pp.speed == 0.5

    def test_custom_values(self, multi_waypoint_path):
        assert multi_waypoint_path.line_width == 0.15
        assert multi_waypoint_path.color == "yellow"
        assert multi_waypoint_path.speed == 0.3

    def test_start_property(self, simple_paint_path):
        assert simple_paint_path.start == Point2D(0.0, 0.0)

    def test_end_property(self, simple_paint_path):
        assert simple_paint_path.end == Point2D(10.0, 0.0)

    def test_length_straight(self, simple_paint_path):
        assert math.isclose(simple_paint_path.length, 10.0)

    def test_length_l_shape(self, multi_waypoint_path):
        # 5 along x + 5 along y = 10
        assert math.isclose(multi_waypoint_path.length, 10.0)

    def test_reversed(self, simple_paint_path):
        rev = simple_paint_path.reversed()
        assert rev.start == simple_paint_path.end
        assert rev.end == simple_paint_path.start
        assert rev.color == simple_paint_path.color
        assert rev.line_width == simple_paint_path.line_width
        assert rev.speed == simple_paint_path.speed

    def test_reversed_preserves_length(self, multi_waypoint_path):
        rev = multi_waypoint_path.reversed()
        assert math.isclose(rev.length, multi_waypoint_path.length)

    def test_to_dict(self, simple_paint_path):
        d = simple_paint_path.to_dict()
        assert "waypoints" in d
        assert len(d["waypoints"]) == 2
        assert d["line_width"] == 0.1
        assert d["color"] == "white"
        assert d["speed"] == 0.5

    def test_from_dict(self):
        d = {
            "waypoints": [{"x": 0.0, "y": 0.0}, {"x": 5.0, "y": 5.0}],
            "line_width": 0.2,
            "color": "yellow",
            "speed": 0.3,
        }
        pp = PaintPath.from_dict(d)
        assert len(pp.waypoints) == 2
        assert pp.line_width == 0.2
        assert pp.color == "yellow"
        assert pp.speed == 0.3

    def test_from_dict_defaults(self):
        d = {"waypoints": [{"x": 0, "y": 0}, {"x": 1, "y": 0}]}
        pp = PaintPath.from_dict(d)
        assert pp.line_width == 0.1
        assert pp.color == "white"
        assert pp.speed == 0.5

    def test_round_trip_dict(self, multi_waypoint_path):
        reconstructed = PaintPath.from_dict(multi_waypoint_path.to_dict())
        assert len(reconstructed.waypoints) == len(multi_waypoint_path.waypoints)
        for orig, rec in zip(multi_waypoint_path.waypoints, reconstructed.waypoints):
            assert orig == rec
        assert reconstructed.color == multi_waypoint_path.color
        assert reconstructed.line_width == multi_waypoint_path.line_width


# ══════════════════════════════════════════════════════════════════════════ #
#  TransitPath
# ══════════════════════════════════════════════════════════════════════════ #

class TestTransitPath:
    """Tests for the TransitPath dataclass."""

    def test_creation(self, simple_transit_path):
        assert len(simple_transit_path.waypoints) == 2

    def test_length(self):
        tp = TransitPath(waypoints=[Point2D(0, 0), Point2D(3, 4)])
        assert math.isclose(tp.length, 5.0)

    def test_to_dict(self, simple_transit_path):
        d = simple_transit_path.to_dict()
        assert "waypoints" in d
        assert len(d["waypoints"]) == 2

    def test_from_dict(self):
        d = {"waypoints": [{"x": 0, "y": 0}, {"x": 6, "y": 8}]}
        tp = TransitPath.from_dict(d)
        assert math.isclose(tp.length, 10.0)

    def test_round_trip_dict(self, simple_transit_path):
        reconstructed = TransitPath.from_dict(simple_transit_path.to_dict())
        assert math.isclose(reconstructed.length, simple_transit_path.length)


# ══════════════════════════════════════════════════════════════════════════ #
#  PaintSegment
# ══════════════════════════════════════════════════════════════════════════ #

class TestPaintSegment:
    """Tests for the PaintSegment dataclass."""

    def test_creation(self, simple_paint_path):
        seg = PaintSegment(path=simple_paint_path, index=0)
        assert seg.index == 0
        assert seg.path is simple_paint_path

    def test_to_dict(self, simple_paint_path):
        seg = PaintSegment(path=simple_paint_path, index=3)
        d = seg.to_dict()
        assert d["index"] == 3
        assert "path" in d

    def test_from_dict(self):
        d = {
            "path": {
                "waypoints": [{"x": 0, "y": 0}, {"x": 1, "y": 0}],
                "line_width": 0.1,
                "color": "white",
                "speed": 0.5,
            },
            "index": 7,
        }
        seg = PaintSegment.from_dict(d)
        assert seg.index == 7
        assert len(seg.path.waypoints) == 2

    def test_round_trip_dict(self, simple_paint_path):
        original = PaintSegment(path=simple_paint_path, index=2)
        reconstructed = PaintSegment.from_dict(original.to_dict())
        assert reconstructed.index == original.index
        assert len(reconstructed.path.waypoints) == len(original.path.waypoints)


# ══════════════════════════════════════════════════════════════════════════ #
#  PaintJob
# ══════════════════════════════════════════════════════════════════════════ #

class TestPaintJob:
    """Tests for the PaintJob dataclass."""

    def test_creation(self, sample_paint_job):
        assert sample_paint_job.job_id == "test-job-001"
        assert len(sample_paint_job.segments) == 3
        assert sample_paint_job.metadata["customer"] == "test"

    def test_create_class_method(self, sample_segments, datum_geopoint):
        job = PaintJob.create(
            segments=sample_segments,
            datum=datum_geopoint,
            metadata={"lot": "B2"},
        )
        # Should have a valid UUID4.
        parsed_uuid = uuid.UUID(job.job_id)
        assert parsed_uuid.version == 4
        assert len(job.segments) == 3
        assert job.metadata == {"lot": "B2"}

    def test_create_default_metadata(self, sample_segments, datum_geopoint):
        job = PaintJob.create(segments=sample_segments, datum=datum_geopoint)
        assert job.metadata == {}

    def test_to_dict(self, sample_paint_job):
        d = sample_paint_job.to_dict()
        assert d["job_id"] == "test-job-001"
        assert len(d["segments"]) == 3
        assert "datum" in d
        assert d["metadata"]["customer"] == "test"

    def test_from_dict(self, sample_paint_job):
        d = sample_paint_job.to_dict()
        reconstructed = PaintJob.from_dict(d)
        assert reconstructed.job_id == sample_paint_job.job_id
        assert len(reconstructed.segments) == len(sample_paint_job.segments)
        assert reconstructed.datum == sample_paint_job.datum
        assert reconstructed.metadata == sample_paint_job.metadata

    def test_from_dict_missing_metadata(self):
        d = {
            "job_id": "j1",
            "segments": [],
            "datum": {"lat": 0, "lon": 0, "alt": 0},
        }
        job = PaintJob.from_dict(d)
        assert job.metadata == {}

    def test_to_json(self, sample_paint_job):
        j = sample_paint_job.to_json()
        parsed = json.loads(j)
        assert parsed["job_id"] == "test-job-001"

    def test_from_json(self, sample_paint_job):
        j = sample_paint_job.to_json()
        reconstructed = PaintJob.from_json(j)
        assert reconstructed.job_id == sample_paint_job.job_id
        assert len(reconstructed.segments) == 3

    def test_json_round_trip(self, sample_paint_job):
        j = sample_paint_job.to_json()
        reconstructed = PaintJob.from_json(j)
        # Serialise again and compare JSON strings.
        assert json.loads(j) == json.loads(reconstructed.to_json())

    def test_default_metadata_factory(self, sample_segments, datum_geopoint):
        """Ensure default_factory produces independent dicts."""
        job_a = PaintJob(
            job_id="a", segments=sample_segments, datum=datum_geopoint
        )
        job_b = PaintJob(
            job_id="b", segments=sample_segments, datum=datum_geopoint
        )
        job_a.metadata["key"] = "value"
        assert "key" not in job_b.metadata
