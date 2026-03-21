"""Organization-scoped work orders, executions, and schedules."""

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import get_db
from ..models.commercial_schemas import (
    JobRunCreateRequest,
    JobRunResponse,
    JobRunUpdateRequest,
    WorkOrderCreateRequest,
    WorkOrderUpdateRequest,
)
from ..models.schemas import ScheduleCreate, ScheduleUpdate
from ..orgs import get_organization_context, require_organization_role
from ..services import job_store, organization_audit_store, quote_store, report_store, schedule_store, site_store

router = APIRouter(tags=["operations"])


async def _validate_assignee_membership(organization_id: str, user_id: str | None) -> bool:
    if not user_id:
        return True
    async for db in get_db():
        cursor = await db.execute(
            "SELECT 1 FROM memberships WHERE organization_id = ? AND user_id = ? AND status = 'active'",
            (organization_id, user_id),
        )
        return await cursor.fetchone() is not None
    return False


@router.get("/api/work-orders")
async def list_work_orders(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    site_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    context: dict = Depends(get_organization_context),
):
    items, total = await job_store.list_work_orders(
        context["organization"]["id"],
        page=page,
        limit=limit,
        site_id=site_id,
        status=status,
    )
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.post("/api/work-orders", status_code=201)
async def create_work_order(
    body: WorkOrderCreateRequest,
    context: dict = Depends(require_organization_role("dispatcher")),
):
    site = await site_store.get_site(context["organization"]["id"], body.site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    if body.quote_id:
        quote = await quote_store.get_quote(context["organization"]["id"], body.quote_id)
        if not quote:
            raise HTTPException(status_code=404, detail="Quote not found")
    if not await _validate_assignee_membership(context["organization"]["id"], body.assigned_user_id):
        raise HTTPException(status_code=404, detail="Assigned technician not found in organization")
    work_order = await job_store.create_work_order(
        context["organization"]["id"],
        context["user"]["id"],
        body.site_id,
        body.title,
        body.date,
        body.status,
        time_preference=body.time_preference or "morning",
        quote_id=body.quote_id,
        lot_id=body.lot_id or site.get("lot_id"),
        scheduled_start_at=body.scheduled_start_at,
        scheduled_end_at=body.scheduled_end_at,
        assigned_robot_id=body.assigned_robot_id,
        assigned_user_id=body.assigned_user_id,
        notes=body.notes or body.title,
    )
    await organization_audit_store.log_event(
        context["organization"]["id"],
        "work_order.created",
        actor_user_id=context["user"]["id"],
        target_type="work_order",
        target_id=work_order["id"],
        detail={
            "site_id": work_order["site_id"],
            "status": work_order["status"],
            "assigned_user_id": work_order.get("assigned_user_id"),
            "robot_id": work_order.get("robot_id"),
        },
    )
    return work_order


@router.get("/api/work-orders/{job_id}")
async def get_work_order(job_id: str, context: dict = Depends(get_organization_context)):
    work_order = await job_store.get_job_by_org(context["organization"]["id"], job_id)
    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")
    return work_order


@router.patch("/api/work-orders/{job_id}")
async def update_work_order(
    job_id: str,
    body: WorkOrderUpdateRequest,
    context: dict = Depends(require_organization_role("dispatcher")),
):
    if not await _validate_assignee_membership(context["organization"]["id"], body.assigned_user_id):
        raise HTTPException(status_code=404, detail="Assigned technician not found in organization")
    existing = await job_store.get_job_by_org(context["organization"]["id"], job_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Work order not found")
    if body.status == "verified":
        report = await report_store.get_latest_job_report(context["organization"]["id"], job_id)
        issues = report_store.report_readiness_issues(report)
        if issues:
            raise HTTPException(
                status_code=400,
                detail="Customer-ready verification blocked: " + "; ".join(issues),
            )
    work_order = await job_store.update_work_order(
        context["organization"]["id"],
        job_id,
        status=body.status,
        scheduled_start_at=body.scheduled_start_at,
        scheduled_end_at=body.scheduled_end_at,
        assigned_user_id=body.assigned_user_id,
        robot_id=body.assigned_robot_id,
        notes=body.notes,
        verified_at=body.verified_at,
    )
    if work_order is False:
        raise HTTPException(status_code=400, detail="Invalid status transition")
    changed_detail = {}
    if body.status and body.status != existing.get("status"):
        changed_detail["status"] = {"from": existing.get("status"), "to": body.status}
    if body.assigned_user_id is not None and body.assigned_user_id != existing.get("assigned_user_id"):
        changed_detail["assigned_user_id"] = body.assigned_user_id
    if body.assigned_robot_id is not None and body.assigned_robot_id != existing.get("robot_id"):
        changed_detail["robot_id"] = body.assigned_robot_id
    if changed_detail:
        await organization_audit_store.log_event(
            context["organization"]["id"],
            "work_order.updated",
            actor_user_id=context["user"]["id"],
            target_type="work_order",
            target_id=job_id,
            detail=changed_detail,
        )
    return work_order


@router.get("/api/work-orders/{job_id}/runs")
async def list_job_runs(job_id: str, context: dict = Depends(get_organization_context)):
    items = await job_store.list_job_runs(context["organization"]["id"], job_id=job_id)
    return {"items": [JobRunResponse(**item) for item in items], "total": len(items)}


@router.post("/api/work-orders/{job_id}/runs", response_model=JobRunResponse, status_code=201)
async def create_job_run(
    job_id: str,
    body: JobRunCreateRequest,
    context: dict = Depends(require_organization_role("technician")),
):
    work_order = await job_store.get_job_by_org(context["organization"]["id"], job_id)
    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")
    if body.job_id != job_id:
        raise HTTPException(status_code=400, detail="Job run payload does not match route job ID")
    if not await _validate_assignee_membership(context["organization"]["id"], body.technician_user_id):
        raise HTTPException(status_code=404, detail="Assigned technician not found in organization")
    run = await job_store.create_job_run(
        context["organization"]["id"],
        job_id,
        work_order.get("site_id"),
        body.robot_id or work_order.get("robot_id"),
        body.technician_user_id or context["user"]["id"],
        notes=body.notes,
    )
    return JobRunResponse(**run)


@router.patch("/api/job-runs/{run_id}", response_model=JobRunResponse)
async def update_job_run(
    run_id: str,
    body: JobRunUpdateRequest,
    context: dict = Depends(require_organization_role("technician")),
):
    run = await job_store.update_job_run(
        context["organization"]["id"],
        run_id,
        status=body.status,
        notes=body.notes,
        actual_paint_gallons=body.actual_paint_gallons,
        telemetry_summary=body.telemetry_summary,
    )
    if not run:
        raise HTTPException(status_code=404, detail="Job run not found")
    return JobRunResponse(**run)


@router.get("/api/schedules/organization")
async def list_org_schedules(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    site_id: str | None = Query(default=None),
    context: dict = Depends(get_organization_context),
):
    items, total = await schedule_store.list_schedules_by_org(
        context["organization"]["id"],
        page=page,
        limit=limit,
        site_id=site_id,
    )
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.post("/api/schedules/organization", status_code=201)
async def create_org_schedule(
    body: ScheduleCreate,
    context: dict = Depends(require_organization_role("dispatcher")),
):
    site = await site_store.get_site_by_lot(body.lot_id)
    if not site or site["organization_id"] != context["organization"]["id"]:
        raise HTTPException(status_code=404, detail="Lot not found")
    schedule = await schedule_store.create_schedule(
        context["user"]["id"],
        body.lot_id,
        body.frequency,
        body.day_of_week,
        body.day_of_month,
        body.time_preference,
    )
    return schedule


@router.put("/api/schedules/organization/{schedule_id}")
async def update_org_schedule(
    schedule_id: str,
    body: ScheduleUpdate,
    context: dict = Depends(require_organization_role("dispatcher")),
):
    existing = await schedule_store.get_schedule_by_org(context["organization"]["id"], schedule_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule not found")
    updated = await schedule_store.update_schedule(
        existing["user_id"],
        schedule_id,
        frequency=body.frequency,
        day_of_week=body.day_of_week,
        day_of_month=body.day_of_month,
        time_preference=body.time_preference,
        active=int(body.active) if body.active is not None else None,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return updated


@router.delete("/api/schedules/organization/{schedule_id}")
async def delete_org_schedule(
    schedule_id: str,
    context: dict = Depends(require_organization_role("dispatcher")),
):
    existing = await schedule_store.get_schedule_by_org(context["organization"]["id"], schedule_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule not found")
    deleted = await schedule_store.delete_schedule(existing["user_id"], schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"ok": True}
