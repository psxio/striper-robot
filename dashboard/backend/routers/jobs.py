"""Job CRUD and execution control endpoints."""

from fastapi import APIRouter, HTTPException

from ..models.schemas import JobCreate, JobResponse, JobStatus, JobUpdate
from ..services import job_store
from ..services.ros_bridge import ros_bridge

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
async def list_jobs():
    return await job_store.list_jobs()


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(job: JobCreate):
    return await job_store.create_job(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int):
    job = await job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(job_id: int, update: JobUpdate):
    job = await job_store.update_job(job_id, update)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}")
async def delete_job(job_id: int):
    deleted = await job_store.delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True, "message": f"Job {job_id} deleted"}


@router.post("/{job_id}/start")
async def start_job(job_id: int):
    job = await job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in (JobStatus.PENDING, JobStatus.READY, JobStatus.PAUSED):
        raise HTTPException(status_code=400, detail=f"Cannot start job in {job.status} state")
    await job_store.update_job(job_id, JobUpdate(status=JobStatus.RUNNING))
    result = await ros_bridge.start_job(job_id)
    return result


@router.post("/{job_id}/pause")
async def pause_job(job_id: int):
    job = await job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Job is not running")
    await job_store.update_job(job_id, JobUpdate(status=JobStatus.PAUSED))
    result = await ros_bridge.pause_job(job_id)
    return result


@router.post("/{job_id}/stop")
async def stop_job(job_id: int):
    job = await job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await job_store.update_job(job_id, JobUpdate(status=JobStatus.CANCELLED))
    result = await ros_bridge.stop_job(job_id)
    return result
