"""Report generation and persistence for completed work."""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..database import get_db
from . import estimate_store, job_store, media_store, site_store


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _generate_simple_pdf(lines: list[str]) -> bytes:
    text_commands = ["BT", "/F1 12 Tf", "50 780 Td"]
    for index, line in enumerate(lines):
        if index:
            text_commands.append("0 -16 Td")
        text_commands.append(f"({_escape_pdf_text(line)}) Tj")
    text_commands.append("ET")
    stream = "\n".join(text_commands).encode("latin-1", errors="replace")

    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        f"5 0 obj << /Length {len(stream)} >> stream\n".encode("latin-1") + stream + b"\nendstream endobj\n",
    ]

    output = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(output))
        output += obj
    xref_start = len(output)
    output += f"xref\n0 {len(offsets)}\n".encode("latin-1")
    output += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        output += f"{offset:010d} 00000 n \n".encode("latin-1")
    output += (
        f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n"
    ).encode("latin-1")
    return output


async def _get_lot_data(lot_id: Optional[str]) -> Optional[dict]:
    if not lot_id:
        return None
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM lots WHERE id = ?",
            (lot_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def _get_report_row(organization_id: str, report_id: str):
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM job_reports WHERE organization_id = ? AND id = ?",
            (organization_id, report_id),
        )
        return await cursor.fetchone()


async def get_job_report(organization_id: str, report_id: str) -> Optional[dict]:
    row = await _get_report_row(organization_id, report_id)
    if not row:
        return None
    data = dict(row)
    data["report_json"] = json.loads(data.get("report_json") or "{}")
    return data


async def list_job_reports(
    organization_id: str,
    *,
    site_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> list[dict]:
    async for db in get_db():
        where = "WHERE organization_id = ?"
        params: list[object] = [organization_id]
        if site_id:
            where += " AND site_id = ?"
            params.append(site_id)
        if job_id:
            where += " AND job_id = ?"
            params.append(job_id)
        cursor = await db.execute(
            f"SELECT * FROM job_reports {where} ORDER BY generated_at DESC",
            tuple(params),
        )
        rows = await cursor.fetchall()
        reports = []
        for row in rows:
            data = dict(row)
            data["report_json"] = json.loads(data.get("report_json") or "{}")
            reports.append(data)
        return reports


async def get_latest_job_report(organization_id: str, job_id: str) -> Optional[dict]:
    reports = await list_job_reports(organization_id, job_id=job_id)
    return reports[0] if reports else None


def report_readiness_issues(report: Optional[dict]) -> list[str]:
    if not report:
        return ["No generated report is attached to this work order"]

    payload = report.get("report_json") or {}
    design = payload.get("design") or {}
    execution = payload.get("execution") or {}
    media_assets = payload.get("media_assets") or []
    run = execution.get("job_run") or {}
    job = payload.get("job") or {}
    issues: list[str] = []

    if not design.get("geometry_snapshot"):
        issues.append("Missing geometry snapshot")
    if design.get("paint_estimate_gallons") in (None, ""):
        issues.append("Missing estimated paint usage")
    if execution.get("actual_paint_gallons") in (None, ""):
        issues.append("Missing actual paint usage")
    if not (run.get("started_at") or job.get("started_at")):
        issues.append("Missing execution start timestamp")
    if not (run.get("completed_at") or job.get("completed_at")):
        issues.append("Missing execution completion timestamp")
    if not media_assets:
        issues.append("Missing linked media evidence")
    if not report.get("pdf_asset_id"):
        issues.append("Missing downloadable PDF artifact")
    if not payload:
        issues.append("Missing JSON report payload")
    return issues


async def create_job_report(
    organization_id: str,
    created_by_user_id: str,
    job_id: str,
    *,
    job_run_id: Optional[str] = None,
) -> dict:
    job = await job_store.get_job_by_org(organization_id, job_id)
    if not job:
        raise ValueError("Job not found")
    site = await site_store.get_site(organization_id, job["site_id"]) if job.get("site_id") else None
    lot = await _get_lot_data(job.get("lotId"))
    features = []
    if lot and lot.get("features"):
        try:
            features = json.loads(lot["features"])
        except json.JSONDecodeError:
            features = []
    estimate = estimate_store.calculate_estimate(features)
    run = await job_store.get_job_run(organization_id, job_run_id) if job_run_id else None
    media = await media_store.list_media_assets(
        organization_id,
        job_id=job_id,
        job_run_id=job_run_id,
    )
    report_json = {
        "job": job,
        "site": site,
        "design": {
            "lot_id": job.get("lotId"),
            "line_length_ft": estimate["total_line_length_ft"],
            "paint_estimate_gallons": estimate["paint_gallons"],
            "estimated_runtime_min": estimate["estimated_runtime_min"],
            "geometry_snapshot": features,
        },
        "execution": {
            "job_run": run,
            "actual_paint_gallons": run.get("actual_paint_gallons") if run else None,
            "telemetry_summary": run.get("telemetry_summary") if run else None,
            "completed_at": job.get("completed_at"),
            "verified_at": job.get("verified_at"),
        },
        "media_assets": media,
    }

    report_id = str(uuid.uuid4())
    now = _now()
    pdf_lines = [
        f"Strype Completion Report: {site['name'] if site else job.get('lot_name', 'Site')}",
        f"Job ID: {job_id}",
        f"Status: {job['status']}",
        f"Scheduled Date: {job['date']}",
        f"Line Length (ft): {estimate['total_line_length_ft']}",
        f"Estimated Paint (gal): {estimate['paint_gallons']}",
        f"Actual Paint (gal): {run.get('actual_paint_gallons') if run else 'n/a'}",
        f"Completed At: {job.get('completed_at') or 'n/a'}",
        f"Verified At: {job.get('verified_at') or 'n/a'}",
    ]
    pdf_asset = await media_store.create_media_asset(
        organization_id,
        created_by_user_id,
        "report_pdf",
        f"report-{job_id}.pdf",
        _generate_simple_pdf(pdf_lines),
        content_type="application/pdf",
        site_id=job.get("site_id"),
        job_id=job_id,
        job_run_id=job_run_id,
        report_id=report_id,
    )

    async for db in get_db():
        await db.execute(
            """INSERT INTO job_reports
               (id, organization_id, site_id, job_id, job_run_id, status, report_json, pdf_asset_id,
                generated_at, created_by_user_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'generated', ?, ?, ?, ?, ?, ?)""",
            (
                report_id,
                organization_id,
                job["site_id"],
                job_id,
                job_run_id,
                json.dumps(report_json),
                pdf_asset["id"],
                now,
                created_by_user_id,
                now,
                now,
            ),
        )
        await db.commit()
    return await get_job_report(organization_id, report_id) or {}
