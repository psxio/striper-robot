"""Path management — upload, template generation, preview."""

import math
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile

from ..models.schemas import (
    PathPreview,
    PathUploadResponse,
    TemplateRequest,
    TemplateResponse,
    TemplateType,
)

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
    features = _generate_lines(req)
    return TemplateResponse(
        template_type=req.template_type,
        line_count=len(features),
        geojson=PathPreview(features=features),
    )


@router.post("/upload", response_model=PathUploadResponse)
async def upload_path(file: UploadFile):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("dxf", "svg"):
        raise HTTPException(status_code=400, detail="Only DXF and SVG files are supported")

    content = await file.read()

    # Placeholder: real implementation would parse DXF/SVG into GeoJSON.
    # For now return a stub so the API contract is fulfilled.
    return PathUploadResponse(
        filename=file.filename,
        path_count=0,
        bounds=None,
        geojson=PathPreview(features=[]),
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
