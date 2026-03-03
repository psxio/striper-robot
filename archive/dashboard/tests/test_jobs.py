"""Tests for the /api/jobs endpoints."""

import pytest


# ---------------------------------------------------------------------------
# POST /api/jobs  -- create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_job(client):
    resp = await client.post("/api/jobs", json={"name": "Parking Lot A"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Parking Lot A"
    assert body["status"] == "pending"
    assert "id" in body
    assert "created_at" in body
    assert "updated_at" in body


@pytest.mark.asyncio
async def test_create_job_with_path_data(client):
    path_data = {"features": [{"type": "Feature"}]}
    resp = await client.post(
        "/api/jobs",
        json={"name": "With Path", "path_data": path_data},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["path_data"] == path_data


@pytest.mark.asyncio
async def test_create_job_with_metadata(client):
    meta = {"surface": "asphalt", "temperature": 72}
    resp = await client.post(
        "/api/jobs",
        json={"name": "With Meta", "metadata": meta},
    )
    assert resp.status_code == 201
    assert resp.json()["metadata"] == meta


# ---------------------------------------------------------------------------
# GET /api/jobs  -- list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_jobs_empty(client):
    resp = await client.get("/api/jobs")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_jobs_with_data(client):
    await client.post("/api/jobs", json={"name": "Job 1"})
    await client.post("/api/jobs", json={"name": "Job 2"})

    resp = await client.get("/api/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    names = {j["name"] for j in data}
    assert names == {"Job 1", "Job 2"}


# ---------------------------------------------------------------------------
# GET /api/jobs/{id}  -- get specific
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_job(client):
    create_resp = await client.post("/api/jobs", json={"name": "Test Job"})
    job_id = create_resp.json()["id"]

    resp = await client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Job"
    assert resp.json()["id"] == job_id


@pytest.mark.asyncio
async def test_get_nonexistent_job(client):
    resp = await client.get("/api/jobs/99999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Job not found"


# ---------------------------------------------------------------------------
# PUT /api/jobs/{id}  -- update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_job_name(client):
    create_resp = await client.post("/api/jobs", json={"name": "Old Name"})
    job_id = create_resp.json()["id"]

    resp = await client.put(f"/api/jobs/{job_id}", json={"name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_job_status(client):
    create_resp = await client.post("/api/jobs", json={"name": "Status Test"})
    job_id = create_resp.json()["id"]

    resp = await client.put(f"/api/jobs/{job_id}", json={"status": "ready"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_update_nonexistent_job(client):
    resp = await client.put("/api/jobs/99999", json={"name": "Ghost"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/jobs/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_job(client):
    create_resp = await client.post("/api/jobs", json={"name": "Doomed"})
    job_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/jobs/{job_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["ok"] is True

    # Verify it is gone
    get_resp = await client.get(f"/api/jobs/{job_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_job(client):
    resp = await client.delete("/api/jobs/99999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/jobs/{id}/start
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_job(client):
    create_resp = await client.post("/api/jobs", json={"name": "Start Me"})
    job_id = create_resp.json()["id"]

    resp = await client.post(f"/api/jobs/{job_id}/start")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "started" in body["message"]

    # Job status should now be running
    get_resp = await client.get(f"/api/jobs/{job_id}")
    assert get_resp.json()["status"] == "running"


@pytest.mark.asyncio
async def test_start_job_wrong_state(client):
    create_resp = await client.post("/api/jobs", json={"name": "Completed"})
    job_id = create_resp.json()["id"]
    await client.put(f"/api/jobs/{job_id}", json={"status": "completed"})

    resp = await client.post(f"/api/jobs/{job_id}/start")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_start_nonexistent_job(client):
    resp = await client.post("/api/jobs/99999/start")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/jobs/{id}/pause
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pause_job(client):
    create_resp = await client.post("/api/jobs", json={"name": "Pause Me"})
    job_id = create_resp.json()["id"]

    # Must be running first
    await client.post(f"/api/jobs/{job_id}/start")

    resp = await client.post(f"/api/jobs/{job_id}/pause")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "paused" in body["message"]

    get_resp = await client.get(f"/api/jobs/{job_id}")
    assert get_resp.json()["status"] == "paused"


@pytest.mark.asyncio
async def test_pause_job_not_running(client):
    create_resp = await client.post("/api/jobs", json={"name": "Not Running"})
    job_id = create_resp.json()["id"]

    resp = await client.post(f"/api/jobs/{job_id}/pause")
    assert resp.status_code == 400
    assert "not running" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_pause_nonexistent_job(client):
    resp = await client.post("/api/jobs/99999/pause")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/jobs/{id}/stop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stop_job(client):
    create_resp = await client.post("/api/jobs", json={"name": "Stop Me"})
    job_id = create_resp.json()["id"]

    await client.post(f"/api/jobs/{job_id}/start")

    resp = await client.post(f"/api/jobs/{job_id}/stop")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "stopped" in body["message"]

    get_resp = await client.get(f"/api/jobs/{job_id}")
    assert get_resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_stop_nonexistent_job(client):
    resp = await client.post("/api/jobs/99999/stop")
    assert resp.status_code == 404
