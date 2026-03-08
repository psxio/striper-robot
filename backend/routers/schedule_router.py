"""Recurring schedule management routes with tenant isolation."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user
from ..config import settings
from ..models.schemas import ScheduleCreate, ScheduleUpdate, ScheduleResponse
from ..services import schedule_store, lot_store

router = APIRouter(prefix="/api/schedules", tags=["schedules"])
logger = logging.getLogger("strype.schedules")


def _to_response(schedule: dict) -> ScheduleResponse:
    """Convert a store dict to a ScheduleResponse."""
    return ScheduleResponse(**schedule)


@router.get("")
async def list_schedules(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    items, total = await schedule_store.list_schedules(user["id"], page=page, limit=limit)
    return {
        "items": [_to_response(s) for s in items],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.post("", response_model=ScheduleResponse, status_code=201)
async def create_schedule(body: ScheduleCreate, user: dict = Depends(get_current_user)):
    # Require Pro+ plan
    plan = user.get("plan") or "free"
    if plan == "free":
        raise HTTPException(
            status_code=403,
            detail="Recurring schedules require a Pro plan or higher",
        )

    # Validate lot ownership
    lot = await lot_store.get_lot(user["id"], body.lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    schedule = await schedule_store.create_schedule(
        user["id"],
        body.lot_id,
        body.frequency,
        body.day_of_week,
        body.day_of_month,
        body.time_preference,
    )
    logger.info("Schedule created: %s for lot %s", schedule["id"], body.lot_id)
    return _to_response(schedule)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: str, body: ScheduleUpdate, user: dict = Depends(get_current_user)
):
    # Check ownership
    existing = await schedule_store.get_schedule(user["id"], schedule_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule not found")

    updated = await schedule_store.update_schedule(
        user["id"],
        schedule_id,
        frequency=body.frequency,
        day_of_week=body.day_of_week,
        day_of_month=body.day_of_month,
        time_preference=body.time_preference,
        active=body.active,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return _to_response(updated)


@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: str, user: dict = Depends(get_current_user)):
    deleted = await schedule_store.delete_schedule(user["id"], schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"ok": True}
