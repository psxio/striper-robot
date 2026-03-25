"""Lot management routes with tenant isolation."""

import json
import logging
import os
import tempfile
import uuid
from importlib import import_module

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Literal

from ..auth import require_active_billing
from ..config import settings
from ..models.schemas import LotCreate, LotUpdate, LotResponse, PaginatedLotResponse
from ..orgs import get_organization_context
from ..services import lot_store, organization_audit_store

router = APIRouter(prefix="/api/lots", tags=["lots"])
logger = logging.getLogger("strype.lots")

MAX_IMPORT_SIZE = 5 * 1024 * 1024  # 5 MB


def _load_pathgen_module(module_name: str):
    """Import striper_pathgen modules in either installed or repo-local layout."""
    candidates = (
        f"striper_pathgen.{module_name}",
        f"striper_pathgen.striper_pathgen.{module_name}",
    )
    last_exc = None
    for candidate in candidates:
        try:
            return import_module(candidate)
        except ModuleNotFoundError as exc:
            if exc.name != candidate:
                raise
            last_exc = exc
    raise last_exc or ModuleNotFoundError(module_name)


def _to_response(lot: dict) -> LotResponse:
    """Convert a store dict to a LotResponse."""
    return LotResponse(**lot)


@router.get("", response_model=PaginatedLotResponse)
async def list_lots(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    search: str = Query(default=None, max_length=200),
    context: dict = Depends(get_organization_context),
):
    items, total = await lot_store.list_lots(
        context["user"]["id"],
        page=page,
        limit=limit,
        search=search,
        organization_id=context["organization"]["id"],
    )
    return PaginatedLotResponse(
        items=[_to_response(l) for l in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("", response_model=LotResponse, status_code=201)
async def create_lot(body: LotCreate, _billing=Depends(require_active_billing), context: dict = Depends(get_organization_context)):
    # Atomic plan enforcement
    user = context["user"]
    plan = user.get("plan") or "free"
    limits = settings.PLAN_LIMITS.get(plan, settings.PLAN_LIMITS["free"])
    lot = await lot_store.create_lot_atomic(
        user["id"],
        body,
        limits["max_lots"],
        organization_id=context["organization"]["id"],
    )
    if not lot:
        raise HTTPException(
            status_code=403,
            detail=f"Plan limited to {limits['max_lots']} lot"
                   + ("s" if limits["max_lots"] != 1 else ""),
        )
    logger.info("Lot created: %s by user %s", lot["id"], user["id"])
    await organization_audit_store.log_event(
        context["organization"]["id"], "lot.created",
        actor_user_id=user["id"], target_type="lot", target_id=lot["id"],
    )
    return _to_response(lot)


@router.get("/{lot_id}", response_model=LotResponse)
async def get_lot(lot_id: str, context: dict = Depends(get_organization_context)):
    lot = await lot_store.get_lot(
        context["user"]["id"],
        lot_id,
        organization_id=context["organization"]["id"],
    )
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    return _to_response(lot)


@router.put("/{lot_id}", response_model=LotResponse)
async def update_lot(
    lot_id: str, body: LotUpdate, context: dict = Depends(get_organization_context)
):
    lot = await lot_store.update_lot(
        context["user"]["id"],
        lot_id,
        body,
        organization_id=context["organization"]["id"],
    )
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    await organization_audit_store.log_event(
        context["organization"]["id"], "lot.updated",
        actor_user_id=context["user"]["id"], target_type="lot", target_id=lot_id,
    )
    return _to_response(lot)


@router.delete("/{lot_id}")
async def delete_lot(lot_id: str, context: dict = Depends(get_organization_context)):
    deleted = await lot_store.delete_lot(
        context["user"]["id"],
        lot_id,
        organization_id=context["organization"]["id"],
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Lot not found")
    await organization_audit_store.log_event(
        context["organization"]["id"], "lot.deleted",
        actor_user_id=context["user"]["id"], target_type="lot", target_id=lot_id,
    )
    return {"ok": True}


@router.post("/{lot_id}/duplicate", response_model=LotResponse, status_code=201)
async def duplicate_lot(lot_id: str, _billing=Depends(require_active_billing), context: dict = Depends(get_organization_context)):
    # Enforce plan lot limit (same as create_lot)
    user = context["user"]
    plan = user.get("plan") or "free"
    limits = settings.PLAN_LIMITS.get(plan, settings.PLAN_LIMITS["free"])
    _, total = await lot_store.list_lots(user["id"], organization_id=context["organization"]["id"])
    if total >= limits["max_lots"]:
        raise HTTPException(
            status_code=403,
            detail=f"Plan limited to {limits['max_lots']} lot"
                   + ("s" if limits["max_lots"] != 1 else ""),
        )
    lot = await lot_store.duplicate_lot(
        user["id"],
        lot_id,
        organization_id=context["organization"]["id"],
    )
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    return _to_response(lot)


# --- Import / Export ---

@router.post("/{lot_id}/import", response_model=LotResponse)
async def import_file(
    lot_id: str,
    file: UploadFile = File(...),
    context: dict = Depends(get_organization_context),
):
    """Import DXF or SVG file into a lot's features."""
    lot = await lot_store.get_lot(
        context["user"]["id"],
        lot_id,
        organization_id=context["organization"]["id"],
    )
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

    # Validate magic bytes
    try:
        text_preview = content[:500].decode("utf-8", errors="ignore")
    except Exception:
        text_preview = ""
    if ext == ".dxf" and not text_preview.lstrip().startswith("0"):
        raise HTTPException(status_code=400, detail="Invalid DXF file content")
    if ext == ".svg" and "<svg" not in text_preview.lower():
        raise HTTPException(status_code=400, detail="Invalid SVG file content")

    # Write to temp file and import
    suffix = ext
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        os.write(tmp_fd, content)
        os.close(tmp_fd)

        if ext == ".dxf":
            paths = _load_pathgen_module("dxf_importer").import_dxf(tmp_path)
        else:
            paths = _load_pathgen_module("svg_importer").import_svg(tmp_path)
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
    CoordinateTransformer = _load_pathgen_module("coordinate_transform").CoordinateTransformer
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
        context["user"]["id"], lot_id,
        LotUpdate(features=all_features),
        organization_id=context["organization"]["id"],
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
    context: dict = Depends(get_organization_context),
):
    """Export lot features as waypoints, GeoJSON, or KML."""
    lot = await lot_store.get_lot(
        context["user"]["id"],
        lot_id,
        organization_id=context["organization"]["id"],
    )
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    if not lot["features"]:
        raise HTTPException(status_code=400, detail="Lot has no features to export")

    # Convert lot features to PaintJob
    models = _load_pathgen_module("models")
    PaintPath = models.PaintPath
    PaintSegment = models.PaintSegment
    PaintJob = models.PaintJob
    GeoPoint = models.GeoPoint
    CoordinateTransformer = _load_pathgen_module("coordinate_transform").CoordinateTransformer

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
        export_waypoints = _load_pathgen_module("mission_planner").export_waypoints
        content = export_waypoints(job, datum_lat=datum_lat, datum_lon=datum_lng)
        return Response(
            content=content,
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="{lot["name"]}.waypoints"'},
        )
    elif body.format == "geojson":
        export_geojson = _load_pathgen_module("job_exporter").export_geojson
        geojson = export_geojson(job)
        return Response(
            content=json.dumps(geojson, indent=2),
            media_type="application/geo+json",
            headers={"Content-Disposition": f'attachment; filename="{lot["name"]}.geojson"'},
        )
    else:  # kml
        export_kml = _load_pathgen_module("job_exporter").export_kml
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
