"""Path management — upload, template generation, preview."""

import math
import os
import sys
import tempfile
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile

from ..models.schemas import (
    PathPreview,
    PathUploadResponse,
    TemplateRequest,
    TemplateResponse,
    TemplateType,
)

# Add striper_pathgen to path so we can import it.
_PATHGEN_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "striper_ws", "src", "striper_pathgen")
)
if _PATHGEN_DIR not in sys.path:
    sys.path.insert(0, _PATHGEN_DIR)

router = APIRouter(prefix="/api/paths", tags=["paths"])

# Available templates metadata
TEMPLATES = {
    TemplateType.STANDARD: {
        "name": "Standard (90-degree)",
        "description": "Standard perpendicular parking stalls, 9 ft wide x 18 ft deep",
        "default_spacing_ft": 9.0,
        "default_length_ft": 18.0,
    },
    TemplateType.ANGLED_60: {
        "name": "60-Degree Angled",
        "description": "60-degree angled parking stalls",
        "default_spacing_ft": 9.0,
        "default_length_ft": 18.0,
    },
    TemplateType.ANGLED_45: {
        "name": "45-Degree Angled",
        "description": "45-degree angled parking stalls",
        "default_spacing_ft": 9.0,
        "default_length_ft": 18.0,
    },
    TemplateType.HANDICAP: {
        "name": "Handicap Accessible",
        "description": "ADA-compliant handicap stalls, 12 ft wide x 18 ft deep",
        "default_spacing_ft": 12.0,
        "default_length_ft": 18.0,
    },
    TemplateType.COMPACT: {
        "name": "Compact",
        "description": "Compact parking stalls, 8 ft wide x 16 ft deep",
        "default_spacing_ft": 8.0,
        "default_length_ft": 16.0,
    },
    TemplateType.ARROW: {
        "name": "Directional Arrow",
        "description": "Straight, left-turn, or right-turn arrow marking",
        "arrow_types": ["straight", "left", "right"],
    },
    TemplateType.CROSSWALK: {
        "name": "Crosswalk",
        "description": "Parallel stripe crosswalk marking",
        "default_width_ft": 10.0,
        "default_length_ft": 20.0,
    },
}

# Rough meter-per-degree at mid latitudes
METERS_PER_DEG_LAT = 111_320.0
METERS_PER_DEG_LNG_AT_30 = 96_486.0  # cos(30deg) * 111320

FT_TO_M = 0.3048


def _ft_to_deg_lat(ft: float) -> float:
    return (ft * FT_TO_M) / METERS_PER_DEG_LAT


def _ft_to_deg_lng(ft: float) -> float:
    return (ft * FT_TO_M) / METERS_PER_DEG_LNG_AT_30


def _rotate(dx: float, dy: float, angle_deg: float) -> tuple[float, float]:
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    return dx * cos_a - dy * sin_a, dx * sin_a + dy * cos_a


def _generate_lines(req: TemplateRequest) -> list[dict[str, Any]]:
    """Generate GeoJSON line features for the requested template."""
    features: list[dict[str, Any]] = []
    origin_lat = req.origin.lat
    origin_lng = req.origin.lng
    angle = req.angle

    stall_angle = {
        TemplateType.STANDARD: 90.0,
        TemplateType.ANGLED_60: 60.0,
        TemplateType.ANGLED_45: 45.0,
        TemplateType.HANDICAP: 90.0,
        TemplateType.COMPACT: 90.0,
    }.get(req.template_type, 90.0)

    for i in range(req.count + 1):
        # Stall divider line
        x_offset_ft = i * req.spacing_ft
        line_angle = angle + (90.0 - stall_angle)

        # Base of the line along the row
        dx_base = _ft_to_deg_lng(x_offset_ft)
        dy_base = 0.0
        dx_base_r, dy_base_r = _rotate(dx_base, dy_base, angle)

        # Tip of the stall divider line
        line_dx = req.length_ft * math.sin(math.radians(stall_angle))
        line_dy = req.length_ft * math.cos(math.radians(stall_angle))
        dx_tip = _ft_to_deg_lng(x_offset_ft + line_dx)
        dy_tip = _ft_to_deg_lat(line_dy)
        dx_tip_r, dy_tip_r = _rotate(dx_tip, dy_tip, angle)

        start = [origin_lng + dx_base_r, origin_lat + dy_base_r]
        end = [origin_lng + dx_tip_r, origin_lat + dy_tip_r]

        features.append({
            "type": "Feature",
            "properties": {
                "line_type": "stall_divider",
                "index": i,
                "color": "#FFFFFF",
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [start, end],
            },
        })

    # End lines connecting the bases and tips of the dividers
    if req.include_end_lines and len(features) >= 2:
        first = features[0]["geometry"]["coordinates"]
        last = features[-1]["geometry"]["coordinates"]
        # Base line (curb line)
        features.append({
            "type": "Feature",
            "properties": {"line_type": "base_line", "color": "#FFFF00"},
            "geometry": {
                "type": "LineString",
                "coordinates": [first[0], last[0]],
            },
        })
        # Top line
        features.append({
            "type": "Feature",
            "properties": {"line_type": "top_line", "color": "#FFFF00"},
            "geometry": {
                "type": "LineString",
                "coordinates": [first[1], last[1]],
            },
        })

    return features


@router.get("/templates")
async def list_templates():
    return TEMPLATES


@router.post("/template", response_model=TemplateResponse)
async def generate_template(req: TemplateRequest):
    # For arrow and crosswalk, use striper_pathgen's template generators.
    if req.template_type in (TemplateType.ARROW, TemplateType.CROSSWALK):
        try:
            from striper_pathgen.models import Point2D as PGPoint2D
            from striper_pathgen.template_generator import generate_arrow, generate_crosswalk
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="striper_pathgen not available for template generation",
            )

        origin = PGPoint2D(0.0, 0.0)
        if req.template_type == TemplateType.ARROW:
            paint_paths = generate_arrow(origin, req.angle, arrow_type=req.arrow_type)
        else:
            paint_paths = generate_crosswalk(
                origin, req.angle,
                width=req.crosswalk_width_ft * FT_TO_M,
                length=req.crosswalk_length_ft * FT_TO_M,
            )

        features = _paint_paths_to_geojson(paint_paths, req.origin.lat, req.origin.lng)
        return TemplateResponse(
            template_type=req.template_type,
            line_count=len(features),
            geojson=PathPreview(features=features),
        )

    # Parking stall templates use the built-in geometric generator.
    features = _generate_lines(req)
    return TemplateResponse(
        template_type=req.template_type,
        line_count=len(features),
        geojson=PathPreview(features=features),
    )


def _paint_paths_to_geojson(
    paint_paths: list,
    origin_lat: float = 30.2672,
    origin_lng: float = -97.7431,
) -> list[dict[str, Any]]:
    """Convert striper_pathgen PaintPath objects to GeoJSON features.

    PaintPaths use local meters, so we project them to lat/lng using the
    CoordinateTransformer with a default datum (overridden per-job later).
    """
    from striper_pathgen.coordinate_transform import CoordinateTransformer

    ct = CoordinateTransformer(origin_lat, origin_lng)
    features: list[dict[str, Any]] = []

    for idx, pp in enumerate(paint_paths):
        coords = []
        for wp in pp.waypoints:
            geo = ct.local_to_geo(wp.x, wp.y)
            coords.append([geo.lon, geo.lat])

        features.append({
            "type": "Feature",
            "properties": {
                "line_type": "paint_path",
                "index": idx,
                "color": getattr(pp, "color", "#FFFFFF"),
                "line_width": getattr(pp, "line_width", 0.1),
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
        })
    return features


@router.post("/upload", response_model=PathUploadResponse)
async def upload_path(file: UploadFile):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("dxf", "svg"):
        raise HTTPException(status_code=400, detail="Only DXF and SVG files are supported")

    content = await file.read()

    # Write to a temp file so the importers can read it.
    suffix = f".{ext}"
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        paint_paths: list = []
        if ext == "dxf":
            try:
                from striper_pathgen.dxf_importer import import_dxf
                paint_paths = import_dxf(tmp_path)
            except ImportError:
                raise HTTPException(
                    status_code=422,
                    detail="DXF support requires the 'ezdxf' package. Install with: pip install ezdxf",
                )
        elif ext == "svg":
            try:
                from striper_pathgen.svg_importer import import_svg
                paint_paths = import_svg(tmp_path)
            except ImportError:
                raise HTTPException(
                    status_code=422,
                    detail="SVG support requires the 'svgpathtools' package. Install with: pip install svgpathtools",
                )
    finally:
        os.unlink(tmp_path)

    features = _paint_paths_to_geojson(paint_paths) if paint_paths else []

    # Calculate bounds from all coordinates.
    bounds = None
    if features:
        all_coords = [
            c for f in features for c in f["geometry"]["coordinates"]
        ]
        lngs = [c[0] for c in all_coords]
        lats = [c[1] for c in all_coords]
        bounds = {
            "south": min(lats), "north": max(lats),
            "west": min(lngs), "east": max(lngs),
        }

    return PathUploadResponse(
        filename=file.filename,
        path_count=len(paint_paths),
        bounds=bounds,
        geojson=PathPreview(features=features),
    )


@router.get("/preview/{job_id}", response_model=PathPreview)
async def get_preview(job_id: int):
    from ..services import job_store

    job = await job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.path_data and "features" in job.path_data:
        return PathPreview(features=job.path_data["features"])
    return PathPreview(features=[])
