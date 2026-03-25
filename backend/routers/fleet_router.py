"""Organization-scoped fleet operations routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..models.commercial_schemas import (
    ConsumableItemCreateRequest,
    ConsumableItemUpdateRequest,
    ConsumableUsageCreateRequest,
    ConsumableUsageResponse,
    MaintenanceEventCreateRequest,
    MaintenanceEventResponse,
    ServiceChecklistCreateRequest,
    ServiceChecklistResponse,
)
from ..orgs import get_organization_context, require_organization_role
from ..services import fleet_store, organization_audit_store, robot_store

router = APIRouter(prefix="/api/fleet", tags=["fleet"])


class FleetRobotUpdateRequest(BaseModel):
    status: Optional[str] = None
    firmware_version: Optional[str] = Field(default=None, max_length=50)
    maintenance_status: Optional[str] = Field(default=None, max_length=50)
    battery_health_pct: Optional[int] = Field(default=None, ge=0, le=100)
    service_due_at: Optional[str] = None
    last_successful_mission_at: Optional[str] = None
    issue_state: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=1000)


async def _get_org_robot_or_404(organization_id: str, robot_id: str) -> dict:
    robot = await robot_store.get_robot_for_organization(organization_id, robot_id)
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found in organization fleet")
    return robot


@router.get("/robots")
async def list_robots(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    status: Optional[str] = Query(default=None),
    context: dict = Depends(get_organization_context),
):
    items, total = await robot_store.list_robots(
        page=page,
        limit=limit,
        status=status,
        organization_id=context["organization"]["id"],
    )
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.get("/claimed-robots")
async def list_claimed_robots(context: dict = Depends(get_organization_context)):
    items = await robot_store.list_claimed_robots(context["organization"]["id"])
    return {"items": items, "total": len(items)}


@router.patch("/robots/{robot_id}")
async def update_robot(
    robot_id: str,
    body: FleetRobotUpdateRequest,
    context: dict = Depends(require_organization_role("dispatcher")),
):
    await _get_org_robot_or_404(context["organization"]["id"], robot_id)
    robot = await robot_store.update_robot(
        robot_id,
        status=body.status,
        firmware_version=body.firmware_version,
        notes=body.notes,
        maintenance_status=body.maintenance_status,
        battery_health_pct=body.battery_health_pct,
        service_due_at=body.service_due_at,
        last_successful_mission_at=body.last_successful_mission_at,
        issue_state=body.issue_state,
    )
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found")
    await organization_audit_store.log_event(
        context["organization"]["id"],
        "fleet.robot_updated",
        actor_user_id=context["user"]["id"],
        target_type="robot",
        target_id=robot_id,
        detail={
            "status": body.status,
            "maintenance_status": body.maintenance_status,
            "battery_health_pct": body.battery_health_pct,
            "issue_state": body.issue_state,
        },
    )
    return robot


@router.get("/maintenance-events")
async def list_maintenance_events(
    robot_id: Optional[str] = Query(default=None),
    context: dict = Depends(get_organization_context),
):
    if robot_id:
        await _get_org_robot_or_404(context["organization"]["id"], robot_id)
    items = await fleet_store.list_maintenance_events(
        organization_id=context["organization"]["id"],
        robot_id=robot_id,
    )
    return {"items": [MaintenanceEventResponse(**item) for item in items], "total": len(items)}


@router.post("/maintenance-events", response_model=MaintenanceEventResponse, status_code=201)
async def create_maintenance_event(
    body: MaintenanceEventCreateRequest,
    context: dict = Depends(require_organization_role("dispatcher")),
):
    await _get_org_robot_or_404(context["organization"]["id"], body.robot_id)
    item = await fleet_store.create_maintenance_event(
        body.robot_id,
        context["organization"]["id"],
        context["user"]["id"],
        body.event_type,
        body.summary,
        details=body.details,
        completed_at=body.completed_at,
    )
    await organization_audit_store.log_event(
        context["organization"]["id"],
        "fleet.maintenance_logged",
        actor_user_id=context["user"]["id"],
        target_type="robot",
        target_id=body.robot_id,
        detail={"event_type": body.event_type, "summary": body.summary},
    )
    return MaintenanceEventResponse(**item)


@router.get("/service-checklists")
async def list_service_checklists(
    robot_id: Optional[str] = Query(default=None),
    context: dict = Depends(get_organization_context),
):
    if robot_id:
        await _get_org_robot_or_404(context["organization"]["id"], robot_id)
    items = await fleet_store.list_service_checklists(
        organization_id=context["organization"]["id"],
        robot_id=robot_id,
    )
    return {"items": [ServiceChecklistResponse(**item) for item in items], "total": len(items)}


@router.post("/service-checklists", response_model=ServiceChecklistResponse, status_code=201)
async def create_service_checklist(
    body: ServiceChecklistCreateRequest,
    context: dict = Depends(require_organization_role("dispatcher")),
):
    await _get_org_robot_or_404(context["organization"]["id"], body.robot_id)
    item = await fleet_store.create_service_checklist(
        body.robot_id,
        context["organization"]["id"],
        context["user"]["id"],
        body.name,
        body.checklist_items,
        completed_at=body.completed_at,
    )
    await organization_audit_store.log_event(
        context["organization"]["id"],
        "fleet.checklist_logged",
        actor_user_id=context["user"]["id"],
        target_type="robot",
        target_id=body.robot_id,
        detail={"name": body.name, "items": len(body.checklist_items)},
    )
    return ServiceChecklistResponse(**item)


@router.get("/consumables")
async def list_consumables(context: dict = Depends(get_organization_context)):
    items = await fleet_store.list_consumable_items(context["organization"]["id"])
    return {"items": items, "total": len(items)}


@router.post("/consumables", status_code=201)
async def create_consumable_item(
    body: ConsumableItemCreateRequest,
    context: dict = Depends(require_organization_role("dispatcher")),
):
    item = await fleet_store.create_consumable_item(
        context["organization"]["id"],
        body.sku,
        body.name,
        body.unit,
        body.on_hand,
        body.reorder_level,
    )
    return item


@router.patch("/consumables/{item_id}")
async def update_consumable_item(
    item_id: str,
    body: ConsumableItemUpdateRequest,
    context: dict = Depends(require_organization_role("dispatcher")),
):
    item = await fleet_store.update_consumable_item(
        context["organization"]["id"],
        item_id,
        name=body.name,
        unit=body.unit,
        on_hand=body.on_hand,
        reorder_level=body.reorder_level,
    )
    if not item:
        raise HTTPException(status_code=404, detail="Consumable item not found")
    return item


@router.get("/consumable-usage")
async def list_consumable_usage(
    job_run_id: Optional[str] = Query(default=None),
    context: dict = Depends(get_organization_context),
):
    items = await fleet_store.list_consumable_usage(context["organization"]["id"], job_run_id=job_run_id)
    return {"items": [ConsumableUsageResponse(**item) for item in items], "total": len(items)}


@router.post("/consumable-usage", response_model=ConsumableUsageResponse, status_code=201)
async def create_consumable_usage(
    body: ConsumableUsageCreateRequest,
    context: dict = Depends(require_organization_role("technician")),
):
    item = await fleet_store.create_consumable_usage(
        context["organization"]["id"],
        body.consumable_item_id,
        context["user"]["id"],
        body.quantity,
        job_run_id=body.job_run_id,
        notes=body.notes,
    )
    if not item:
        raise HTTPException(status_code=404, detail="Consumable item not found")
    await organization_audit_store.log_event(
        context["organization"]["id"],
        "fleet.consumable_used",
        actor_user_id=context["user"]["id"],
        target_type="consumable",
        target_id=body.consumable_item_id,
        detail={"quantity": body.quantity, "job_run_id": body.job_run_id},
    )
    return ConsumableUsageResponse(**item)
