"""Tests for media asset uploads and job report management."""

import io
import pytest


async def _org_headers(auth_client):
    me = (await auth_client.get("/api/auth/me")).json()
    return {"X-Organization-ID": me["active_organization_id"]}


@pytest.mark.asyncio
async def test_upload_jpeg_allowed(auth_client):
    """POST /api/media-assets accepts a JPEG image."""
    headers = await _org_headers(auth_client)
    file_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # JPEG magic bytes
    resp = await auth_client.post(
        "/api/media-assets",
        headers=headers,
        data={"asset_type": "photo"},
        files={"file": ("before_photo.jpg", io.BytesIO(file_content), "image/jpeg")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["asset_type"] == "photo"
    assert data["filename"] == "before_photo.jpg"


@pytest.mark.asyncio
async def test_upload_pdf_allowed(auth_client):
    """POST /api/media-assets accepts a PDF."""
    headers = await _org_headers(auth_client)
    file_content = b"%PDF-1.4 fake content"
    resp = await auth_client.post(
        "/api/media-assets",
        headers=headers,
        data={"asset_type": "document"},
        files={"file": ("report.pdf", io.BytesIO(file_content), "application/pdf")},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_upload_disallowed_type_rejected(auth_client):
    """POST /api/media-assets rejects exe files (application/octet-stream)."""
    headers = await _org_headers(auth_client)
    resp = await auth_client.post(
        "/api/media-assets",
        headers=headers,
        data={"asset_type": "photo"},
        files={"file": ("malware.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upload_extension_mismatch_rejected(auth_client):
    """POST /api/media-assets rejects JPEG MIME type with .png extension."""
    headers = await _org_headers(auth_client)
    file_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    resp = await auth_client.post(
        "/api/media-assets",
        headers=headers,
        data={"asset_type": "photo"},
        files={"file": ("sneaky.png", io.BytesIO(file_content), "image/jpeg")},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_media_assets_empty(auth_client):
    """GET /api/media-assets returns empty list before any uploads."""
    headers = await _org_headers(auth_client)
    resp = await auth_client.get("/api/media-assets", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_media_assets_after_upload(auth_client):
    """GET /api/media-assets includes the uploaded asset."""
    headers = await _org_headers(auth_client)
    file_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    await auth_client.post(
        "/api/media-assets",
        headers=headers,
        data={"asset_type": "photo"},
        files={"file": ("site1.jpg", io.BytesIO(file_content), "image/jpeg")},
    )
    resp = await auth_client.get("/api/media-assets", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_create_and_list_job_reports(auth_client):
    """POST /api/job-reports creates a report; GET lists it."""
    headers = await _org_headers(auth_client)

    # Need a lot/site/work-order first
    lot_data = {
        "name": "Report Lot",
        "center": {"lat": 40.7, "lng": -74.0},
        "zoom": 19,
        "features": [],
    }
    lot_resp = await auth_client.post("/api/lots", json=lot_data)
    assert lot_resp.status_code == 201

    sites_resp = await auth_client.get("/api/sites", headers=headers)
    site = sites_resp.json()["items"][0]

    wo_resp = await auth_client.post(
        "/api/work-orders",
        headers=headers,
        json={
            "site_id": site["id"],
            "title": "RPT-WO-001",
            "date": "2026-05-01",
            "status": "scheduled",
        },
    )
    assert wo_resp.status_code == 201
    work_order = wo_resp.json()

    me = (await auth_client.get("/api/auth/me")).json()
    run_resp = await auth_client.post(
        f"/api/work-orders/{work_order['id']}/runs",
        headers=headers,
        json={"job_id": work_order["id"], "technician_user_id": me["id"]},
    )
    assert run_resp.status_code == 201
    run = run_resp.json()

    report_resp = await auth_client.post(
        "/api/job-reports",
        headers=headers,
        data={"job_id": work_order["id"], "job_run_id": run["id"]},
    )
    assert report_resp.status_code == 201
    report = report_resp.json()
    assert report["job_id"] == work_order["id"]

    list_resp = await auth_client.get("/api/job-reports", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_media_assets_require_auth(client):
    """Media asset endpoints require authentication."""
    resp = await client.get("/api/media-assets")
    assert resp.status_code == 401
