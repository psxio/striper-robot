"""Organization-scoped site scans and cloud simulation routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..models.commercial_schemas import (
    SiteScanCreateRequest,
    SiteScanResponse,
    SiteSimulationCreateRequest,
    SiteSimulationResponse,
)
from ..orgs import get_organization_context, require_organization_role
from ..services import cloud_store, organization_audit_store, site_store

router = APIRouter(tags=["cloud"])


@router.get("/api/site-scans")
async def list_site_scans(
    site_id: Optional[str] = Query(default=None),
    context: dict = Depends(get_organization_context),
):
    items = await cloud_store.list_site_scans(context["organization"]["id"], site_id=site_id)
    return {"items": [SiteScanResponse(**item) for item in items], "total": len(items)}


@router.post("/api/site-scans", response_model=SiteScanResponse, status_code=201)
async def create_site_scan(
    body: SiteScanCreateRequest,
    context: dict = Depends(require_organization_role("manager")),
):
    site = await site_store.get_site(context["organization"]["id"], body.site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    scan = await cloud_store.create_site_scan(
        context["organization"]["id"],
        context["user"]["id"],
        body.site_id,
        scan_type=body.scan_type,
        notes=body.notes,
        source_media_asset_id=body.source_media_asset_id,
    )
    await organization_audit_store.log_event(
        context["organization"]["id"],
        "site.scan_created",
        actor_user_id=context["user"]["id"],
        target_type="site_scan",
        target_id=scan["id"],
        detail={"site_id": body.site_id, "scan_type": body.scan_type},
    )
    return SiteScanResponse(**scan)


@router.get("/api/site-simulations")
async def list_site_simulations(
    site_id: Optional[str] = Query(default=None),
    scan_id: Optional[str] = Query(default=None),
    context: dict = Depends(get_organization_context),
):
    items = await cloud_store.list_simulation_runs(
        context["organization"]["id"],
        site_id=site_id,
        scan_id=scan_id,
    )
    return {"items": [SiteSimulationResponse(**item) for item in items], "total": len(items)}


@router.post("/api/site-simulations", response_model=SiteSimulationResponse, status_code=201)
async def create_site_simulation(
    body: SiteSimulationCreateRequest,
    context: dict = Depends(require_organization_role("dispatcher")),
):
    site = await site_store.get_site(context["organization"]["id"], body.site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    try:
        simulation = await cloud_store.create_simulation_run(
            context["organization"]["id"],
            context["user"]["id"],
            site_id=body.site_id,
            scan_id=body.scan_id,
            work_order_id=body.work_order_id,
            robot_id=body.robot_id,
            mode=body.mode,
            speed_mph=body.speed_mph,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await organization_audit_store.log_event(
        context["organization"]["id"],
        "site.simulation_created",
        actor_user_id=context["user"]["id"],
        target_type="simulation_run",
        target_id=simulation["id"],
        detail={"site_id": body.site_id, "mode": body.mode, "robot_id": body.robot_id},
    )
    return SiteSimulationResponse(**simulation)
