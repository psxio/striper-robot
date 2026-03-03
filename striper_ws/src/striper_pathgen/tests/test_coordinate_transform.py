"""Tests for striper_pathgen.coordinate_transform — GPS <-> local conversions."""

from __future__ import annotations

import math

import pytest

from striper_pathgen.models import GeoPoint, Point2D
from striper_pathgen.coordinate_transform import CoordinateTransformer


# ══════════════════════════════════════════════════════════════════════════ #
#  Construction
# ══════════════════════════════════════════════════════════════════════════ #

class TestConstruction:

    def test_basic_construction(self):
        t = CoordinateTransformer(40.0, -74.0)
        assert t.datum_lat == 40.0
        assert t.datum_lon == -74.0
        assert t.heading_deg == 0.0

    def test_construction_with_heading(self):
        t = CoordinateTransformer(40.0, -74.0, heading_deg=45.0)
        assert t.heading_deg == 45.0

    def test_from_geopoint(self, datum_geopoint):
        t = CoordinateTransformer.from_geopoint(datum_geopoint)
        assert t.datum_lat == datum_geopoint.lat
        assert t.datum_lon == datum_geopoint.lon

    def test_from_geopoint_with_heading(self, datum_geopoint):
        t = CoordinateTransformer.from_geopoint(datum_geopoint, heading_deg=90.0)
        assert t.heading_deg == 90.0


# ══════════════════════════════════════════════════════════════════════════ #
#  Datum point maps to origin
# ══════════════════════════════════════════════════════════════════════════ #

class TestDatumAtOrigin:

    def test_geo_to_local_at_datum(self):
        t = CoordinateTransformer(40.0, -74.0)
        p = t.geo_to_local(40.0, -74.0)
        assert math.isclose(p.x, 0.0, abs_tol=1e-9)
        assert math.isclose(p.y, 0.0, abs_tol=1e-9)

    def test_local_to_geo_at_origin(self):
        t = CoordinateTransformer(40.0, -74.0)
        g = t.local_to_geo(0.0, 0.0)
        assert math.isclose(g.lat, 40.0, abs_tol=1e-9)
        assert math.isclose(g.lon, -74.0, abs_tol=1e-9)

    def test_datum_at_equator(self):
        t = CoordinateTransformer(0.0, 0.0)
        p = t.geo_to_local(0.0, 0.0)
        assert math.isclose(p.x, 0.0, abs_tol=1e-9)
        assert math.isclose(p.y, 0.0, abs_tol=1e-9)

    def test_datum_at_high_latitude(self):
        t = CoordinateTransformer(70.0, 25.0)
        p = t.geo_to_local(70.0, 25.0)
        assert math.isclose(p.x, 0.0, abs_tol=1e-9)
        assert math.isclose(p.y, 0.0, abs_tol=1e-9)


# ══════════════════════════════════════════════════════════════════════════ #
#  Round-trip accuracy
# ══════════════════════════════════════════════════════════════════════════ #

class TestRoundTrip:

    def test_round_trip_no_heading(self):
        t = CoordinateTransformer(40.0, -74.0)
        lat, lon = 40.001, -73.999
        p = t.geo_to_local(lat, lon)
        g = t.local_to_geo(p.x, p.y)
        assert math.isclose(g.lat, lat, abs_tol=1e-7)
        assert math.isclose(g.lon, lon, abs_tol=1e-7)

    def test_round_trip_with_heading(self):
        t = CoordinateTransformer(40.0, -74.0, heading_deg=30.0)
        lat, lon = 40.002, -73.998
        p = t.geo_to_local(lat, lon)
        g = t.local_to_geo(p.x, p.y)
        assert math.isclose(g.lat, lat, abs_tol=1e-7)
        assert math.isclose(g.lon, lon, abs_tol=1e-7)

    def test_round_trip_heading_90(self):
        t = CoordinateTransformer(34.0, -118.0, heading_deg=90.0)
        lat, lon = 34.0005, -117.999
        p = t.geo_to_local(lat, lon)
        g = t.local_to_geo(p.x, p.y)
        assert math.isclose(g.lat, lat, abs_tol=1e-7)
        assert math.isclose(g.lon, lon, abs_tol=1e-7)

    def test_round_trip_heading_180(self):
        t = CoordinateTransformer(51.5, -0.1, heading_deg=180.0)
        lat, lon = 51.501, -0.099
        p = t.geo_to_local(lat, lon)
        g = t.local_to_geo(p.x, p.y)
        assert math.isclose(g.lat, lat, abs_tol=1e-7)
        assert math.isclose(g.lon, lon, abs_tol=1e-7)

    def test_round_trip_local_to_geo_to_local(self):
        t = CoordinateTransformer(40.0, -74.0, heading_deg=45.0)
        x, y = 50.0, 100.0
        g = t.local_to_geo(x, y)
        p = t.geo_to_local(g.lat, g.lon)
        assert math.isclose(p.x, x, abs_tol=1e-4)
        assert math.isclose(p.y, y, abs_tol=1e-4)


# ══════════════════════════════════════════════════════════════════════════ #
#  Known GPS coordinate checks
# ══════════════════════════════════════════════════════════════════════════ #

class TestKnownCoordinates:

    def test_north_is_positive_y(self):
        t = CoordinateTransformer(40.0, -74.0)
        p = t.geo_to_local(40.001, -74.0)  # slightly north
        assert p.y > 0.0
        assert math.isclose(p.x, 0.0, abs_tol=1e-6)

    def test_east_is_positive_x(self):
        t = CoordinateTransformer(40.0, -74.0)
        p = t.geo_to_local(40.0, -73.999)  # slightly east
        assert p.x > 0.0
        assert math.isclose(p.y, 0.0, abs_tol=1e-6)

    def test_south_is_negative_y(self):
        t = CoordinateTransformer(40.0, -74.0)
        p = t.geo_to_local(39.999, -74.0)  # slightly south
        assert p.y < 0.0

    def test_west_is_negative_x(self):
        t = CoordinateTransformer(40.0, -74.0)
        p = t.geo_to_local(40.0, -74.001)  # slightly west
        assert p.x < 0.0

    def test_one_degree_lat_approximately_111km(self):
        t = CoordinateTransformer(0.0, 0.0)
        p = t.geo_to_local(1.0, 0.0)
        # 1 degree latitude ~ 111,320 m
        assert 110_000 < p.y < 112_000

    def test_one_degree_lon_at_equator_approximately_111km(self):
        t = CoordinateTransformer(0.0, 0.0)
        p = t.geo_to_local(0.0, 1.0)
        # 1 degree longitude at equator ~ 111,320 m
        assert 110_000 < p.x < 112_000

    def test_one_degree_lon_at_60_lat_smaller(self):
        """At 60 degrees latitude, 1 degree of longitude is about half."""
        t = CoordinateTransformer(60.0, 0.0)
        p = t.geo_to_local(60.0, 1.0)
        # cos(60) = 0.5, so ~55,660 m
        assert 54_000 < p.x < 57_000


# ══════════════════════════════════════════════════════════════════════════ #
#  Heading rotation
# ══════════════════════════════════════════════════════════════════════════ #

class TestHeadingRotation:

    def test_zero_heading_identity(self):
        t = CoordinateTransformer(40.0, -74.0, heading_deg=0.0)
        p = t.geo_to_local(40.001, -74.0)
        # Should be purely in +Y.
        assert math.isclose(p.x, 0.0, abs_tol=1e-4)
        assert p.y > 0.0

    def test_heading_90_rotates_north_to_positive_x(self):
        """With heading=90, North in GPS maps to +X in local."""
        t = CoordinateTransformer(40.0, -74.0, heading_deg=90.0)
        p = t.geo_to_local(40.001, -74.0)  # Point due north
        # After 90-degree heading, north should map to positive x.
        assert p.x > 0.0
        assert math.isclose(p.y, 0.0, abs_tol=1.0)

    def test_heading_180_flips_y(self):
        t0 = CoordinateTransformer(40.0, -74.0, heading_deg=0.0)
        t180 = CoordinateTransformer(40.0, -74.0, heading_deg=180.0)
        p0 = t0.geo_to_local(40.001, -74.0)
        p180 = t180.geo_to_local(40.001, -74.0)
        # Y should be approximately negated.
        assert math.isclose(p0.y, -p180.y, rel_tol=1e-4)

    def test_heading_preserves_distance(self):
        """Heading rotation should not change the distance from origin."""
        lat, lon = 40.001, -73.999
        t0 = CoordinateTransformer(40.0, -74.0, heading_deg=0.0)
        t45 = CoordinateTransformer(40.0, -74.0, heading_deg=45.0)
        p0 = t0.geo_to_local(lat, lon)
        p45 = t45.geo_to_local(lat, lon)
        d0 = math.sqrt(p0.x**2 + p0.y**2)
        d45 = math.sqrt(p45.x**2 + p45.y**2)
        assert math.isclose(d0, d45, rel_tol=1e-6)


# ══════════════════════════════════════════════════════════════════════════ #
#  Datum at different locations
# ══════════════════════════════════════════════════════════════════════════ #

class TestDatumLocations:

    @pytest.mark.parametrize(
        "lat,lon",
        [
            (0.0, 0.0),        # equator/prime meridian
            (40.0, -74.0),     # New York area
            (-33.9, 151.2),    # Sydney area
            (55.75, 37.62),    # Moscow area
            (35.68, 139.69),   # Tokyo area
            (70.0, 25.0),      # high latitude (Hammerfest)
        ],
    )
    def test_round_trip_various_datums(self, lat, lon):
        t = CoordinateTransformer(lat, lon)
        offset_lat = lat + 0.0001
        offset_lon = lon + 0.0001
        p = t.geo_to_local(offset_lat, offset_lon)
        g = t.local_to_geo(p.x, p.y)
        assert math.isclose(g.lat, offset_lat, abs_tol=1e-7)
        assert math.isclose(g.lon, offset_lon, abs_tol=1e-7)

    def test_southern_hemisphere(self):
        t = CoordinateTransformer(-33.9, 151.2)
        p = t.geo_to_local(-33.9, 151.2)
        assert math.isclose(p.x, 0.0, abs_tol=1e-9)
        assert math.isclose(p.y, 0.0, abs_tol=1e-9)

    def test_negative_longitude(self):
        t = CoordinateTransformer(40.0, -74.0)
        g = t.local_to_geo(100.0, 200.0)
        # Longitude should still be negative (near New York).
        assert g.lon < 0.0
