"""Shared pytest fixtures for striper_pathgen tests."""

from __future__ import annotations

import sys
import os

# Ensure the package is importable when running tests from the repo root.
_pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

import pytest

from striper_pathgen.models import (
    GeoPoint,
    PaintJob,
    PaintPath,
    PaintSegment,
    Point2D,
    TransitPath,
)


# ── Point fixtures ─────────────────────────────────────────────────────── #

@pytest.fixture
def origin_point() -> Point2D:
    """A point at the local origin."""
    return Point2D(0.0, 0.0)


@pytest.fixture
def unit_point() -> Point2D:
    """A point at (1, 1)."""
    return Point2D(1.0, 1.0)


# ── PaintPath fixtures ─────────────────────────────────────────────────── #

@pytest.fixture
def simple_paint_path() -> PaintPath:
    """A simple horizontal paint path from (0,0) to (10,0)."""
    return PaintPath(
        waypoints=[Point2D(0.0, 0.0), Point2D(10.0, 0.0)],
        line_width=0.1,
        color="white",
        speed=0.5,
    )


@pytest.fixture
def multi_waypoint_path() -> PaintPath:
    """A paint path with three waypoints forming an L-shape."""
    return PaintPath(
        waypoints=[Point2D(0.0, 0.0), Point2D(5.0, 0.0), Point2D(5.0, 5.0)],
        line_width=0.15,
        color="yellow",
        speed=0.3,
    )


@pytest.fixture
def vertical_paint_path() -> PaintPath:
    """A vertical paint path from (0,0) to (0,10)."""
    return PaintPath(
        waypoints=[Point2D(0.0, 0.0), Point2D(0.0, 10.0)],
    )


# ── TransitPath fixture ───────────────────────────────────────────────── #

@pytest.fixture
def simple_transit_path() -> TransitPath:
    """A transit path between two points."""
    return TransitPath(
        waypoints=[Point2D(10.0, 0.0), Point2D(20.0, 5.0)],
    )


# ── GeoPoint fixtures ─────────────────────────────────────────────────── #

@pytest.fixture
def sample_geopoint() -> GeoPoint:
    """GPS coordinate near Austin, TX."""
    return GeoPoint(lat=30.2672, lon=-97.7431, alt=150.0)


@pytest.fixture
def datum_geopoint() -> GeoPoint:
    """Datum GPS point for coordinate transform tests."""
    return GeoPoint(lat=40.0, lon=-74.0, alt=0.0)


# ── PaintSegment / PaintJob fixtures ──────────────────────────────────── #

@pytest.fixture
def sample_segments() -> list[PaintSegment]:
    """A list of three paint segments for job-level tests."""
    seg0 = PaintSegment(
        path=PaintPath(
            waypoints=[Point2D(0.0, 0.0), Point2D(0.0, 5.5)],
        ),
        index=0,
    )
    seg1 = PaintSegment(
        path=PaintPath(
            waypoints=[Point2D(2.7, 0.0), Point2D(2.7, 5.5)],
        ),
        index=1,
    )
    seg2 = PaintSegment(
        path=PaintPath(
            waypoints=[Point2D(5.4, 0.0), Point2D(5.4, 5.5)],
        ),
        index=2,
    )
    return [seg0, seg1, seg2]


@pytest.fixture
def sample_paint_job(sample_segments, datum_geopoint) -> PaintJob:
    """A complete PaintJob for serialisation and round-trip tests."""
    return PaintJob(
        job_id="test-job-001",
        segments=sample_segments,
        datum=datum_geopoint,
        metadata={"customer": "test", "lot_id": "A1"},
    )


# ── Scattered paint paths for optimizer tests ─────────────────────────── #

@pytest.fixture
def scattered_paths() -> list[PaintPath]:
    """Paint paths deliberately placed far apart for optimizer tests."""
    return [
        PaintPath(waypoints=[Point2D(0.0, 0.0), Point2D(0.0, 1.0)]),
        PaintPath(waypoints=[Point2D(100.0, 100.0), Point2D(100.0, 101.0)]),
        PaintPath(waypoints=[Point2D(1.0, 0.0), Point2D(1.0, 1.0)]),
        PaintPath(waypoints=[Point2D(99.0, 100.0), Point2D(99.0, 101.0)]),
        PaintPath(waypoints=[Point2D(2.0, 0.0), Point2D(2.0, 1.0)]),
    ]
