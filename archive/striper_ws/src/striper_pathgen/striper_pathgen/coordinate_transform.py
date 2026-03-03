"""Coordinate transformations between GPS and local meter coordinates."""

from __future__ import annotations

import math

from .models import GeoPoint, Point2D

# WGS-84 constants
_EARTH_RADIUS_M = 6_378_137.0


class CoordinateTransformer:
    """Converts between GPS (lat/lon) and local 2D meter coordinates.

    Uses an equirectangular (flat-Earth) approximation which is accurate to
    within ~0.1 % for areas up to a few kilometres across — more than
    sufficient for a single parking lot.

    The local coordinate frame has:
      * origin at the datum point
      * +X pointing East  (before heading rotation)
      * +Y pointing North (before heading rotation)

    An optional *heading* (degrees, clockwise from North) rotates the
    local frame so that +X aligns with the lot's primary axis.
    """

    def __init__(self, datum_lat: float, datum_lon: float, heading_deg: float = 0.0):
        self.datum_lat = datum_lat
        self.datum_lon = datum_lon
        self.heading_deg = heading_deg

        # Pre-compute scale factors at the datum latitude.
        lat_rad = math.radians(datum_lat)
        self._m_per_deg_lat = math.pi / 180.0 * _EARTH_RADIUS_M
        self._m_per_deg_lon = math.pi / 180.0 * _EARTH_RADIUS_M * math.cos(lat_rad)

        # Heading rotation (applied to local coords).
        heading_rad = math.radians(heading_deg)
        self._cos_h = math.cos(heading_rad)
        self._sin_h = math.sin(heading_rad)

    # ----- public helpers -------------------------------------------------- #

    @classmethod
    def from_geopoint(cls, datum: GeoPoint, heading_deg: float = 0.0) -> CoordinateTransformer:
        """Convenience constructor from a GeoPoint datum."""
        return cls(datum.lat, datum.lon, heading_deg)

    # ----- conversions ----------------------------------------------------- #

    def geo_to_local(self, lat: float, lon: float) -> Point2D:
        """Convert a GPS coordinate to local (x, y) metres relative to datum.

        Returns a Point2D where x is east-ish and y is north-ish (before the
        heading rotation is applied).
        """
        dx = (lon - self.datum_lon) * self._m_per_deg_lon
        dy = (lat - self.datum_lat) * self._m_per_deg_lat

        # Apply heading rotation (rotate coordinate axes, not the point).
        rx = dx * self._cos_h + dy * self._sin_h
        ry = -dx * self._sin_h + dy * self._cos_h
        return Point2D(rx, ry)

    def local_to_geo(self, x: float, y: float) -> GeoPoint:
        """Convert local (x, y) metres back to GPS (lat, lon)."""
        # Inverse heading rotation.
        dx = x * self._cos_h - y * self._sin_h
        dy = x * self._sin_h + y * self._cos_h

        lon = self.datum_lon + dx / self._m_per_deg_lon
        lat = self.datum_lat + dy / self._m_per_deg_lat
        return GeoPoint(lat, lon)
