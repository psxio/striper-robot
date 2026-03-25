"""Tests for job estimate JOIN — verify estimate fields appear in job responses."""

import uuid
from datetime import datetime, timezone

import pytest


async def _create_lot(client):
    """Create a lot and return its ID."""
    resp = await client.post("/api/lots", json={
        "name": "Estimate Test Lot",
        "center": {"lat": 33.0, "lng": -97.0},
        "zoom": 18,
        "features": [],
    })
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_job(client, lot_id):
    """Create a job and return the response."""
    resp = await client.post("/api/jobs", json={
        "lotId": lot_id,
        "date": "2026-05-01",
    })
    assert resp.status_code == 201
    return resp.json()


async def _insert_estimate(job_id: str, cost: float = 150.0, runtime: int = 45, gallons: float = 2.5, length: float = 1200.0):
    """Insert a job estimate directly into the database."""
    from backend.database import get_db
    estimate_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async for db in get_db():
        await db.execute(
            """INSERT INTO job_estimates (id, job_id, total_line_length_ft, paint_gallons, estimated_runtime_min, estimated_cost, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (estimate_id, job_id, length, gallons, runtime, cost, now),
        )
        await db.commit()


@pytest.mark.asyncio
async def test_job_response_includes_estimate(auth_client):
    """Job GET response includes estimate fields when estimate exists."""
    lot_id = await _create_lot(auth_client)
    job = await _create_job(auth_client, lot_id)
    await _insert_estimate(job["id"], cost=200.0, runtime=60, gallons=3.0, length=1500.0)

    resp = await auth_client.get(f"/api/jobs/{job['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["estimated_cost"] == 200.0
    assert data["estimated_runtime_min"] == 60
    assert data["paint_gallons"] == 3.0
    assert data["total_line_length_ft"] == 1500.0


@pytest.mark.asyncio
async def test_job_response_without_estimate(auth_client):
    """Job GET response has null estimate fields when no estimate exists."""
    lot_id = await _create_lot(auth_client)
    job = await _create_job(auth_client, lot_id)

    resp = await auth_client.get(f"/api/jobs/{job['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("estimated_cost") is None
    assert data.get("estimated_runtime_min") is None


@pytest.mark.asyncio
async def test_job_list_includes_estimates(auth_client):
    """Job list response includes estimate fields on items that have estimates."""
    lot_id = await _create_lot(auth_client)
    job1 = await _create_job(auth_client, lot_id)
    job2_resp = await auth_client.post("/api/jobs", json={"lotId": lot_id, "date": "2026-05-02"})
    job2 = job2_resp.json()

    # Only job1 gets an estimate
    await _insert_estimate(job1["id"], cost=100.0, runtime=30)

    resp = await auth_client.get("/api/jobs")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2

    job1_item = next(j for j in items if j["id"] == job1["id"])
    job2_item = next(j for j in items if j["id"] == job2["id"])

    assert job1_item["estimated_cost"] == 100.0
    assert job1_item["estimated_runtime_min"] == 30
    assert job2_item.get("estimated_cost") is None


@pytest.mark.asyncio
async def test_job_response_includes_lot_name(auth_client):
    """Job response includes the lot_name field."""
    lot_id = await _create_lot(auth_client)
    job = await _create_job(auth_client, lot_id)

    resp = await auth_client.get(f"/api/jobs/{job['id']}")
    assert resp.status_code == 200
    assert resp.json()["lot_name"] == "Estimate Test Lot"


@pytest.mark.asyncio
async def test_job_response_includes_notes(auth_client):
    """Job response includes the notes field."""
    lot_id = await _create_lot(auth_client)
    job = await _create_job(auth_client, lot_id)

    resp = await auth_client.get(f"/api/jobs/{job['id']}")
    assert resp.status_code == 200
    assert "notes" in resp.json()
