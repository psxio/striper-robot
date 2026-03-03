"""Export PaintJob data to GeoJSON, KML, and CSV formats.

These exporters convert the local-coordinate paint paths to GPS coordinates
using the job's datum, then write them in standard interchange formats for
visualization, verification, and archival.

All functions operate on the pure-Python pathgen models and have no ROS2
dependency.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from typing import Any

from .coordinate_transform import CoordinateTransformer
from .models import PaintJob, PaintPath, PaintSegment


# ── GeoJSON export ────────────────────────────────────────────────────────


def export_geojson(job: PaintJob) -> dict[str, Any]:
    """Export a PaintJob as a GeoJSON FeatureCollection.

    Each paint segment becomes a GeoJSON Feature with a LineString geometry.
    Properties include ``segment_index``, ``color``, ``line_width``, and
    ``speed``.

    The coordinate reference system is WGS-84 (EPSG:4326), matching the
    GeoJSON specification.

    Args:
        job: The PaintJob to export.

    Returns:
        A GeoJSON FeatureCollection dict.
    """
    xf = CoordinateTransformer.from_geopoint(job.datum)
    features: list[dict[str, Any]] = []

    for seg in job.segments:
        coords = []
        for wp in seg.path.waypoints:
            geo = xf.local_to_geo(wp.x, wp.y)
            # GeoJSON uses [longitude, latitude] order
            coords.append([geo.lon, geo.lat])

        feature: dict[str, Any] = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
            "properties": {
                "segment_index": seg.index,
                "color": seg.path.color,
                "line_width": seg.path.line_width,
                "speed": seg.path.speed,
                "length_m": seg.path.length,
            },
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "job_id": job.job_id,
            "datum_lat": job.datum.lat,
            "datum_lon": job.datum.lon,
            "total_segments": len(job.segments),
            "metadata": job.metadata,
        },
    }


# ── KML export ────────────────────────────────────────────────────────────

_KML_NS = "http://www.opengis.net/kml/2.2"

# Map paint colours to KML colour codes (aabbggrr hex format)
_KML_COLOR_MAP: dict[str, str] = {
    "white": "ffffffff",
    "yellow": "ff00ffff",
    "blue": "ffff0000",
    "red": "ff0000ff",
    "green": "ff00ff00",
}


def export_kml(job: PaintJob) -> str:
    """Export a PaintJob as KML for Google Earth visualization.

    Each paint segment is rendered as a Placemark with a LineString.
    Segments are colour-coded according to their paint colour attribute.

    Args:
        job: The PaintJob to export.

    Returns:
        A KML document as a UTF-8 string.
    """
    xf = CoordinateTransformer.from_geopoint(job.datum)

    kml = ET.Element("kml", xmlns=_KML_NS)
    document = ET.SubElement(kml, "Document")
    ET.SubElement(document, "name").text = f"Striper Job {job.job_id}"
    ET.SubElement(document, "description").text = (
        f"Paint job with {len(job.segments)} segments"
    )

    # Create shared styles for each colour
    colour_set: set[str] = set()
    for seg in job.segments:
        colour_set.add(seg.path.color)

    for colour in sorted(colour_set):
        style = ET.SubElement(document, "Style", id=f"style_{colour}")
        line_style = ET.SubElement(style, "LineStyle")
        ET.SubElement(line_style, "color").text = _KML_COLOR_MAP.get(colour, "ffffffff")
        # KML line width in pixels (scale from meters)
        ET.SubElement(line_style, "width").text = "3"

    # Create placemarks
    for seg in job.segments:
        placemark = ET.SubElement(document, "Placemark")
        ET.SubElement(placemark, "name").text = f"Segment {seg.index}"
        ET.SubElement(placemark, "description").text = (
            f"Color: {seg.path.color}, Width: {seg.path.line_width}m, "
            f"Speed: {seg.path.speed} m/s, Length: {seg.path.length:.2f}m"
        )
        ET.SubElement(placemark, "styleUrl").text = f"#style_{seg.path.color}"

        line_string = ET.SubElement(placemark, "LineString")
        ET.SubElement(line_string, "tessellate").text = "1"
        ET.SubElement(line_string, "altitudeMode").text = "clampToGround"

        coord_parts: list[str] = []
        for wp in seg.path.waypoints:
            geo = xf.local_to_geo(wp.x, wp.y)
            coord_parts.append(f"{geo.lon},{geo.lat},0")
        ET.SubElement(line_string, "coordinates").text = " ".join(coord_parts)

    # Serialize to string
    tree = ET.ElementTree(kml)
    buf = io.BytesIO()
    tree.write(buf, encoding="utf-8", xml_declaration=True)
    return buf.getvalue().decode("utf-8")


# ── CSV export ────────────────────────────────────────────────────────────


def export_csv(job: PaintJob) -> str:
    """Export a PaintJob as a CSV waypoint list.

    Each row contains the segment index, waypoint index, local x/y
    coordinates, GPS lat/lon, paint colour, line width, and speed.
    This format is intended for manual verification and debugging.

    Args:
        job: The PaintJob to export.

    Returns:
        A CSV string with header row.
    """
    xf = CoordinateTransformer.from_geopoint(job.datum)
    lines: list[str] = [
        "segment_index,waypoint_index,local_x,local_y,latitude,longitude,color,line_width,speed"
    ]

    for seg in job.segments:
        for wp_idx, wp in enumerate(seg.path.waypoints):
            geo = xf.local_to_geo(wp.x, wp.y)
            lines.append(
                f"{seg.index},{wp_idx},"
                f"{wp.x:.6f},{wp.y:.6f},"
                f"{geo.lat:.8f},{geo.lon:.8f},"
                f"{seg.path.color},{seg.path.line_width},{seg.path.speed}"
            )

    return "\n".join(lines) + "\n"
