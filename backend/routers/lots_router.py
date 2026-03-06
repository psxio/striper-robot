"""Lot management routes with tenant isolation."""

import json
import os
import tempfile
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Literal

from ..auth import get_current_user
from ..config import settings
from ..models.schemas import LotCreate, LotUpdate, LotResponse, PaginatedLotResponse
from ..services import lot_store

router = APIRouter(prefix="/api/lots", tags=["lots"])

MAX_IMPORT_SIZE = 5 * 1024 * 1024  # 5 MB


def _to_response(lot: dict) -> LotResponse:
    """Convert a store dict to a LotResponse."""
    return LotResponse(**lot)


@router.get("", response_model=PaginatedLotResponse)
async def list_lots(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    items, total = await lot_store.list_lots(user["id"], page=page, limit=limit)
    return PaginatedLotResponse(
        items=[_to_response(l) for l in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("", response_model=LotResponse, status_code=201)
async def create_lot(body: LotCreate, user: dict = Depends(get_current_user)):
    # Plan enforcement
    plan = user.get("plan") or "free"
    limits = settings.PLAN_LIMITS.get(plan, settings.PLAN_LIMITS["free"])
    current_count = await lot_store.count_lots(user["id"])
    if current_count >= limits["max_lots"]:
        raise HTTPException(
            status_code=403,
            detail=f"Free plan limited to {limits['max_lots']} lot"
                   + ("s" if limits["max_lots"] != 1 else ""),
        )
    lot = await lot_store.create_lot(user["id"], body)
    return _to_response(lot)


@router.get("/{lot_id}", response_model=LotResponse)
async def get_lot(lot_id: str, user: dict = Depends(get_current_user)):
    lot = await lot_store.get_lot(user["id"], lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    return _to_response(lot)


@router.put("/{lot_id}", response_model=LotResponse)
async def update_lot(
    lot_id: str, body: LotUpdate, user: dict = Depends(get_current_user)
):
    lot = await lot_store.update_lot(user["id"], lot_id, body)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    return _to_response(lot)


@router.delete("/{lot_id}")
async def delete_lot(lot_id: str, user: dict = Depends(get_current_user)):
    deleted = await lot_store.delete_lot(user["id"], lot_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Lot not found")
    return {"ok": True}


@router.post("/{lot_id}/duplicate", response_model=LotResponse, status_code=201)
async def duplicate_lot(lot_id: str, user: dict = Depends(get_current_user)):
    lot = await lot_store.duplicate_lot(user["id"], lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    return _to_response(lot)


# --- Import / Export ---

@router.post("/{lot_id}/import", response_model=LotResponse)
async def import_file(
    lot_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Import DXF or SVG file into a lot's features."""
    lot = await lot_store.get_lot(user["id"], lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    # Validate file extension
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".dxf", ".svg"):
        raise HTTPException(status_code=400, detail="Only .dxf and .svg files are supported")

    # Read and check size
    content = await file.read()
    if len(content) > MAX_IMPORT_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 5 MB limit")

    # Write to temp file and import
    suffix = ext
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        os.write(tmp_fd, content)
        os.close(tmp_fd)

        if ext == ".dxf":
            from striper_pathgen.dxf_importer import import_dxf
            paths = import_dxf(tmp_path)
        else:
            from striper_pathgen.svg_importer import import_svg
            paths = import_svg(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if not paths:
        raise HTTPException(status_code=400, detail="No paths found in file")

    # Convert local coordinates to GeoJSON features using lot center as datum
    from striper_pathgen.coordinate_transform import CoordinateTransformer
    transformer = CoordinateTransformer(
        datum_lat=lot["center"]["lat"],
        datum_lon=lot["center"]["lng"],
    )

    new_features = []
    for path in paths:
        coords = []
        for wp in path.waypoints:
            geo = transformer.local_to_geo(wp.x, wp.y)
            coords.append([geo.lon, geo.lat])

        feature = {
            "type": "Feature",
            "properties": {
                "id": str(uuid.uuid4()),
                "type": "standard",
                "lineType": "Imported Line",
                "color": _paint_color_to_hex(path.color),
                "width": round(path.line_width * 39.3701),  # meters to inches
                "notes": f"Imported from {filename}",
                "geometryType": "polyline",
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
        }
        new_features.append(feature)

    # Append to existing features
    all_features = lot["features"] + new_features
    updated = await lot_store.update_lot(
        user["id"], lot_id,
        LotUpdate(features=all_features),
    )
    return _to_response(updated)


def _paint_color_to_hex(color: str) -> str:
    """Convert paint color name to hex."""
    mapping = {
        "white": "#ffffff",
        "yellow": "#ffff00",
        "blue": "#0000ff",
        "red": "#ff0000",
        "green": "#00ff00",
    }
    return mapping.get(color.lower(), "#ffffff")


class ExportRequest(BaseModel):
    format: Literal["waypoints", "geojson", "kml"]


@router.post("/{lot_id}/export")
async def export_lot(
    lot_id: str,
    body: ExportRequest,
    user: dict = Depends(get_current_user),
):
    """Export lot features as waypoints, GeoJSON, or KML."""
    lot = await lot_store.get_lot(user["id"], lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    if not lot["features"]:
        raise HTTPException(status_code=400, detail="Lot has no features to export")

    # Convert lot features to PaintJob
    from striper_pathgen.models import PaintPath, PaintSegment, PaintJob, GeoPoint, Point2D
    from striper_pathgen.coordinate_transform import CoordinateTransformer

    datum_lat = lot["center"]["lat"]
    datum_lng = lot["center"]["lng"]
    transformer = CoordinateTransformer(datum_lat=datum_lat, datum_lon=datum_lng)

    segments = []
    for i, feature in enumerate(lot["features"]):
        coords = _extract_coords(feature)
        if not coords or len(coords) < 2:
            continue

        waypoints = []
        for coord in coords:
            lng, lat = coord[0], coord[1]
            local = transformer.geo_to_local(lat, lng)
            waypoints.append(local)

        props = feature.get("properties", {}) if isinstance(feature, dict) else {}
        width_inches = props.get("width", 4) if isinstance(props, dict) else 4
        color = props.get("color", "white") if isinstance(props, dict) else "white"

        path = PaintPath(
            waypoints=waypoints,
            line_width=width_inches * 0.0254,  # inches to meters
            color=_hex_to_paint_color(color),
        )
        segments.append(PaintSegment(path=path, index=i))

    if not segments:
        raise HTTPException(status_code=400, detail="No exportable features found")

    datum = GeoPoint(lat=datum_lat, lon=datum_lng)
    job = PaintJob.create(segments, datum, metadata={"lot_name": lot["name"]})

    # Export
    if body.format == "waypoints":
        from striper_pathgen.mission_planner import export_waypoints
        content = export_waypoints(job, datum_lat=datum_lat, datum_lon=datum_lng)
        return Response(
            content=content,
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="{lot["name"]}.waypoints"'},
        )
    elif body.format == "geojson":
        from striper_pathgen.job_exporter import export_geojson
        geojson = export_geojson(job)
        return Response(
            content=json.dumps(geojson, indent=2),
            media_type="application/geo+json",
            headers={"Content-Disposition": f'attachment; filename="{lot["name"]}.geojson"'},
        )
    else:  # kml
        from striper_pathgen.job_exporter import export_kml
        content = export_kml(job)
        return Response(
            content=content,
            media_type="application/vnd.google-earth.kml+xml",
            headers={"Content-Disposition": f'attachment; filename="{lot["name"]}.kml"'},
        )


def _extract_coords(feature) -> list:
    """Extract coordinate pairs from a feature (GeoJSON or simple format)."""
    if not isinstance(feature, dict):
        return []
    # GeoJSON Feature
    geom = feature.get("geometry", {})
    if isinstance(geom, dict) and "coordinates" in geom:
        return geom["coordinates"]
    # Simple format: {"coords": [[x,y], ...]}
    if "coords" in feature:
        return feature["coords"]
    return []


def _hex_to_paint_color(hex_color: str) -> str:
    """Convert hex color to paint color name."""
    mapping = {
        "#ffffff": "white",
        "#ffff00": "yellow",
        "#0000ff": "blue",
        "#ff0000": "red",
        "#00ff00": "green",
    }
    return mapping.get(hex_color.lower(), "white")
