"""Job management routes with tenant isolation."""

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user
from ..config import settings
from ..models.schemas import JobCreate, JobUpdate, JobResponse, PaginatedJobResponse
from ..services import job_store

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _to_response(job: dict) -> JobResponse:
    """Convert a store dict to a JobResponse."""
    return JobResponse(**job)


@router.get("", response_model=PaginatedJobResponse)
async def list_jobs(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    items, total = await job_store.list_jobs(user["id"], page=page, limit=limit)
    return PaginatedJobResponse(
        items=[_to_response(j) for j in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(body: JobCreate, user: dict = Depends(get_current_user)):
    # Plan enforcement
    plan = user.get("plan") or "free"
    limits = settings.PLAN_LIMITS.get(plan, settings.PLAN_LIMITS["free"])
    current_count = await job_store.count_jobs(user["id"])
    if current_count >= limits["max_jobs"]:
        raise HTTPException(
            status_code=403,
            detail=f"Free plan limited to {limits['max_jobs']} jobs",
        )
    job = await job_store.create_job(user["id"], body.lotId, body.date)
    return _to_response(job)


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str, body: JobUpdate, user: dict = Depends(get_current_user)
):
    job = await job_store.update_job(
        user["id"], job_id, status=body.status, date=body.date
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_response(job)


@router.delete("/{job_id}")
async def delete_job(job_id: str, user: dict = Depends(get_current_user)):
    deleted = await job_store.delete_job(user["id"], job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True}
