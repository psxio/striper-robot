"""Job management routes with tenant isolation."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Literal, Optional

from ..auth import get_current_user
from ..config import settings
from ..models.schemas import JobCreate, JobUpdate, JobResponse, PaginatedJobResponse
from ..services import job_store, lot_store

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
logger = logging.getLogger("strype.jobs")


def _to_response(job: dict) -> JobResponse:
    """Convert a store dict to a JobResponse."""
    return JobResponse(**job)


@router.get("", response_model=PaginatedJobResponse)
async def list_jobs(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    status: Optional[Literal["pending", "in_progress", "completed", "cancelled"]] = Query(default=None),
    lot_id: Optional[str] = Query(default=None, alias="lotId"),
    user: dict = Depends(get_current_user),
):
    items, total = await job_store.list_jobs(user["id"], page=page, limit=limit, status=status, lot_id=lot_id)
    return PaginatedJobResponse(
        items=[_to_response(j) for j in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(body: JobCreate, user: dict = Depends(get_current_user)):
    # Validate lot ownership
    lot = await lot_store.get_lot(user["id"], body.lotId)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    # Atomic plan enforcement
    plan = user.get("plan") or "free"
    limits = settings.PLAN_LIMITS.get(plan, settings.PLAN_LIMITS["free"])
    job = await job_store.create_job_atomic(
        user["id"], body.lotId, body.date, limits["max_jobs"],
        time_preference=body.time_preference or "morning",
    )
    if not job:
        raise HTTPException(
            status_code=403,
            detail=f"Plan limited to {limits['max_jobs']} jobs",
        )
    logger.info("Job created: %s for lot %s", job["id"], body.lotId)
    return _to_response(job)


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str, body: JobUpdate, user: dict = Depends(get_current_user)
):
    job = await job_store.update_job(
        user["id"], job_id, status=body.status, date=body.date
    )
    if job is False:
        raise HTTPException(status_code=400, detail="Invalid status transition")
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_response(job)


@router.delete("/{job_id}")
async def delete_job(job_id: str, user: dict = Depends(get_current_user)):
    deleted = await job_store.delete_job(user["id"], job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True}
