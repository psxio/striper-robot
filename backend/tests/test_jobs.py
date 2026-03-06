"""Tests for job management endpoints."""

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def lot_id(auth_client):
    """Create a lot and return its ID for job tests."""
    resp = await auth_client.post("/api/lots", json={
        "name": "Job Test Lot",
        "center": {"lat": 40.0, "lng": -74.0},
    })
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_job(auth_client, lot_id):
    resp = await auth_client.post("/api/jobs", json={
        "lotId": lot_id,
        "date": "2026-04-01",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["lotId"] == lot_id
    assert data["date"] == "2026-04-01"
    assert data["status"] == "pending"
    assert "id" in data
    assert "created" in data
    assert "modified" in data


@pytest.mark.asyncio
async def test_list_jobs(auth_client, lot_id):
    await auth_client.post("/api/jobs", json={
        "lotId": lot_id,
        "date": "2026-04-01",
    })
    await auth_client.post("/api/jobs", json={
        "lotId": lot_id,
        "date": "2026-04-15",
    })
    resp = await auth_client.get("/api/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_update_job_status(auth_client, lot_id):
    create_resp = await auth_client.post("/api/jobs", json={
        "lotId": lot_id,
        "date": "2026-04-01",
    })
    job_id = create_resp.json()["id"]
    resp = await auth_client.patch(f"/api/jobs/{job_id}", json={
        "status": "completed",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_update_job_date(auth_client, lot_id):
    create_resp = await auth_client.post("/api/jobs", json={
        "lotId": lot_id,
        "date": "2026-04-01",
    })
    job_id = create_resp.json()["id"]
    resp = await auth_client.patch(f"/api/jobs/{job_id}", json={
        "date": "2026-05-01",
    })
    assert resp.status_code == 200
    assert resp.json()["date"] == "2026-05-01"


@pytest.mark.asyncio
async def test_delete_job(auth_client, lot_id):
    create_resp = await auth_client.post("/api/jobs", json={
        "lotId": lot_id,
        "date": "2026-04-01",
    })
    job_id = create_resp.json()["id"]
    resp = await auth_client.delete(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    # Verify it's gone
    resp = await auth_client.get("/api/jobs")
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_job_isolation(client):
    """Verify that one user cannot access another user's jobs."""
    # Register user 1 and create a lot + job
    resp1 = await client.post("/api/auth/register", json={
        "email": "jobuser1@example.com",
        "password": "password123",
    })
    token1 = resp1.json()["token"]
    client.headers["Authorization"] = f"Bearer {token1}"

    lot_resp = await client.post("/api/lots", json={
        "name": "User1 Lot",
        "center": {"lat": 40.0, "lng": -74.0},
    })
    lot_id = lot_resp.json()["id"]

    job_resp = await client.post("/api/jobs", json={
        "lotId": lot_id,
        "date": "2026-04-01",
    })
    job_id = job_resp.json()["id"]

    # Register user 2
    # Need a fresh client without auth header for registration
    del client.headers["Authorization"]
    resp2 = await client.post("/api/auth/register", json={
        "email": "jobuser2@example.com",
        "password": "password123",
    })
    token2 = resp2.json()["token"]
    client.headers["Authorization"] = f"Bearer {token2}"

    # User 2 should not see user 1's jobs
    resp = await client.get("/api/jobs")
    assert resp.json()["items"] == []

    # User 2 should not be able to update user 1's job
    resp = await client.patch(f"/api/jobs/{job_id}", json={
        "status": "completed",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unauthorized(client):
    resp = await client.get("/api/jobs")
    assert resp.status_code == 401
