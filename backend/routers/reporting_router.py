"""Media asset and report routes."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

from ..models.commercial_schemas import JobReportResponse, MediaAssetResponse
from ..orgs import get_organization_context, require_organization_role
from ..services import media_store, organization_audit_store, report_store

router = APIRouter(tags=["reporting"])


@router.get("/api/media-assets")
async def list_media_assets(
    site_id: Optional[str] = Query(default=None),
    job_id: Optional[str] = Query(default=None),
    job_run_id: Optional[str] = Query(default=None),
    report_id: Optional[str] = Query(default=None),
    asset_type: Optional[str] = Query(default=None),
    context: dict = Depends(get_organization_context),
):
    items = await media_store.list_media_assets(
        context["organization"]["id"],
        site_id=site_id,
        job_id=job_id,
        job_run_id=job_run_id,
        report_id=report_id,
        asset_type=asset_type,
    )
    return {"items": [MediaAssetResponse(**item) for item in items], "total": len(items)}


@router.post("/api/media-assets", response_model=MediaAssetResponse, status_code=201)
async def upload_media_asset(
    asset_type: str = Form(...),
    file: UploadFile = File(...),
    site_id: Optional[str] = Form(default=None),
    job_id: Optional[str] = Form(default=None),
    job_run_id: Optional[str] = Form(default=None),
    report_id: Optional[str] = Form(default=None),
    context: dict = Depends(require_organization_role("technician")),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    asset = await media_store.create_media_asset(
        context["organization"]["id"],
        context["user"]["id"],
        asset_type,
        file.filename or "upload.bin",
        content,
        content_type=file.content_type or "application/octet-stream",
        site_id=site_id,
        job_id=job_id,
        job_run_id=job_run_id,
        report_id=report_id,
    )
    return MediaAssetResponse(**asset)


@router.get("/api/media-assets/{asset_id}/download")
async def download_media_asset(asset_id: str, context: dict = Depends(get_organization_context)):
    asset, content = await media_store.read_media_asset(context["organization"]["id"], asset_id)
    if not asset or content is None:
        raise HTTPException(status_code=404, detail="Media asset not found")
    return Response(
        content=content,
        media_type=asset["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{asset["filename"]}"'},
    )


@router.get("/api/job-reports")
async def list_job_reports(
    site_id: Optional[str] = Query(default=None),
    job_id: Optional[str] = Query(default=None),
    context: dict = Depends(get_organization_context),
):
    items = await report_store.list_job_reports(context["organization"]["id"], site_id=site_id, job_id=job_id)
    return {"items": [JobReportResponse(**item) for item in items], "total": len(items)}


@router.post("/api/job-reports", response_model=JobReportResponse, status_code=201)
async def create_job_report(
    job_id: str = Form(...),
    job_run_id: Optional[str] = Form(default=None),
    context: dict = Depends(require_organization_role("dispatcher")),
):
    try:
        report = await report_store.create_job_report(
            context["organization"]["id"],
            context["user"]["id"],
            job_id,
            job_run_id=job_run_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await organization_audit_store.log_event(
        context["organization"]["id"],
        "report.generated",
        actor_user_id=context["user"]["id"],
        target_type="job_report",
        target_id=report["id"],
        detail={"job_id": report["job_id"], "job_run_id": report.get("job_run_id")},
    )
    return JobReportResponse(**report)


@router.get("/api/job-reports/{report_id}", response_model=JobReportResponse)
async def get_job_report(report_id: str, context: dict = Depends(get_organization_context)):
    report = await report_store.get_job_report(context["organization"]["id"], report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Job report not found")
    return JobReportResponse(**report)


@router.get("/api/job-reports/{report_id}/download")
async def download_job_report(
    report_id: str,
    format: str = Query(default="json"),
    context: dict = Depends(get_organization_context),
):
    report = await report_store.get_job_report(context["organization"]["id"], report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Job report not found")
    if format == "pdf":
        pdf_asset_id = report.get("pdf_asset_id")
        if not pdf_asset_id:
            raise HTTPException(status_code=404, detail="PDF asset not found")
        asset, content = await media_store.read_media_asset(context["organization"]["id"], pdf_asset_id)
        if not asset or content is None:
            raise HTTPException(status_code=404, detail="PDF asset not found")
        await organization_audit_store.log_event(
            context["organization"]["id"],
            "report.downloaded",
            actor_user_id=context["user"]["id"],
            target_type="job_report",
            target_id=report_id,
            detail={"format": "pdf"},
        )
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="report-{report_id}.pdf"'},
        )
    await organization_audit_store.log_event(
        context["organization"]["id"],
        "report.downloaded",
        actor_user_id=context["user"]["id"],
        target_type="job_report",
        target_id=report_id,
        detail={"format": "json"},
    )
    return Response(
        content=json.dumps(report["report_json"], indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="report-{report_id}.json"'},
    )
