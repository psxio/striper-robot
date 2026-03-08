"""Tests for enhanced job features: time preferences, status transitions,
profile updates, job filtering, admin stats, and billing plan changes."""

import pytest
import pytest_asyncio


LOT_DATA = {
    "name": "Test Lot",
    "center": {"lat": 40.0, "lng": -74.0},
    "features": [],
}


async def _create_lot(auth_client):
    """Helper: create a lot and return its ID."""
    resp = await auth_client.post("/api/lots", json=LOT_DATA)
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_job(auth_client, lot_id, date="2026-04-01", **kwargs):
    """Helper: create a job and return the response JSON."""
    payload = {"lotId": lot_id, "date": date, **kwargs}
    resp = await auth_client.post("/api/jobs", json=payload)
    assert resp.status_code == 201
    return resp.json()


# --- Time Preference ---


@pytest.mark.asyncio
async def test_create_job_with_time_preference(auth_client):
    """Creating a job with time_preference='afternoon' stores and returns it."""
    lot_id = await _create_lot(auth_client)
    job = await _create_job(auth_client, lot_id, time_preference="afternoon")
    assert job["time_preference"] == "afternoon"


@pytest.mark.asyncio
async def test_create_job_default_time_preference(auth_client):
    """Creating a job without time_preference defaults to 'morning'."""
    lot_id = await _create_lot(auth_client)
    resp = await auth_client.post("/api/jobs", json={
        "lotId": lot_id,
        "date": "2026-04-01",
    })
    assert resp.status_code == 201
    assert resp.json()["time_preference"] == "morning"


# --- Status Transitions ---


@pytest.mark.asyncio
async def test_job_status_transition_pending_to_in_progress(auth_client):
    """Transitioning pending -> in_progress should succeed and set started_at."""
    lot_id = await _create_lot(auth_client)
    job = await _create_job(auth_client, lot_id)
    assert job["status"] == "pending"
    assert job["started_at"] is None

    resp = await auth_client.patch(f"/api/jobs/{job['id']}", json={
        "status": "in_progress",
    })
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["status"] == "in_progress"
    assert updated["started_at"] is not None


@pytest.mark.asyncio
async def test_job_status_transition_in_progress_to_completed(auth_client):
    """Transitioning pending -> in_progress -> completed should set completed_at."""
    lot_id = await _create_lot(auth_client)
    job = await _create_job(auth_client, lot_id)

    # pending -> in_progress
    resp = await auth_client.patch(f"/api/jobs/{job['id']}", json={
        "status": "in_progress",
    })
    assert resp.status_code == 200

    # in_progress -> completed
    resp = await auth_client.patch(f"/api/jobs/{job['id']}", json={
        "status": "completed",
    })
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["status"] == "completed"
    assert updated["completed_at"] is not None
    assert updated["started_at"] is not None


@pytest.mark.asyncio
async def test_job_status_transition_pending_to_completed(auth_client):
    """Direct pending -> completed should be allowed."""
    lot_id = await _create_lot(auth_client)
    job = await _create_job(auth_client, lot_id)

    resp = await auth_client.patch(f"/api/jobs/{job['id']}", json={
        "status": "completed",
    })
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["status"] == "completed"
    assert updated["completed_at"] is not None


@pytest.mark.asyncio
async def test_job_invalid_status_transition(auth_client):
    """Completed -> pending should return 400."""
    lot_id = await _create_lot(auth_client)
    job = await _create_job(auth_client, lot_id)

    # Move to completed first
    await auth_client.patch(f"/api/jobs/{job['id']}", json={"status": "completed"})

    # Try to go back to pending
    resp = await auth_client.patch(f"/api/jobs/{job['id']}", json={
        "status": "pending",
    })
    assert resp.status_code == 400
    assert "Invalid status transition" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_job_invalid_status_transition_completed_to_in_progress(auth_client):
    """Completed -> in_progress should return 400."""
    lot_id = await _create_lot(auth_client)
    job = await _create_job(auth_client, lot_id)

    # Move to completed
    await auth_client.patch(f"/api/jobs/{job['id']}", json={"status": "completed"})

    # Try to go back to in_progress
    resp = await auth_client.patch(f"/api/jobs/{job['id']}", json={
        "status": "in_progress",
    })
    assert resp.status_code == 400
    assert "Invalid status transition" in resp.json()["detail"]


# --- Response Shape ---


@pytest.mark.asyncio
async def test_job_response_has_new_fields(auth_client):
    """Job response should include time_preference, started_at, completed_at, robot_id."""
    lot_id = await _create_lot(auth_client)
    job = await _create_job(auth_client, lot_id)

    assert "time_preference" in job
    assert "started_at" in job
    assert "completed_at" in job
    assert "robot_id" in job

    # Default values for a new job
    assert job["time_preference"] == "morning"
    assert job["started_at"] is None
    assert job["completed_at"] is None
    assert job["robot_id"] is None


# --- Profile Updates ---


@pytest.mark.asyncio
async def test_update_profile_company_name(auth_client):
    """PUT /api/user/profile with company_name should succeed."""
    resp = await auth_client.put("/api/user/profile", json={
        "company_name": "Acme Striping LLC",
    })
    assert resp.status_code == 200
    # UserResponse is returned; verify the user still has valid data
    assert resp.json()["email"] == "test@example.com"

    # Verify it was persisted by checking via the store directly
    from backend.services.user_store import get_user_by_email
    user = await get_user_by_email("test@example.com")
    assert user["company_name"] == "Acme Striping LLC"


@pytest.mark.asyncio
async def test_update_profile_phone(auth_client):
    """PUT /api/user/profile with phone should succeed."""
    resp = await auth_client.put("/api/user/profile", json={
        "phone": "+1-555-867-5309",
    })
    assert resp.status_code == 200

    from backend.services.user_store import get_user_by_email
    user = await get_user_by_email("test@example.com")
    assert user["phone"] == "+1-555-867-5309"


@pytest.mark.asyncio
async def test_update_profile_both_fields(auth_client):
    """Updating both company_name and phone in one request should succeed."""
    resp = await auth_client.put("/api/user/profile", json={
        "company_name": "Parking Pros Inc.",
        "phone": "212-555-0100",
    })
    assert resp.status_code == 200

    from backend.services.user_store import get_user_by_email
    user = await get_user_by_email("test@example.com")
    assert user["company_name"] == "Parking Pros Inc."
    assert user["phone"] == "212-555-0100"


# --- Job Filtering ---


@pytest.mark.asyncio
async def test_job_filter_by_status(auth_client):
    """Filtering jobs by status=pending should only return pending jobs."""
    lot_id = await _create_lot(auth_client)

    # Create two jobs
    job1 = await _create_job(auth_client, lot_id, date="2026-04-01")
    job2 = await _create_job(auth_client, lot_id, date="2026-04-02")

    # Move job2 to completed
    await auth_client.patch(f"/api/jobs/{job2['id']}", json={"status": "completed"})

    # Filter by pending
    resp = await auth_client.get("/api/jobs?status=pending")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == job1["id"]
    assert data["items"][0]["status"] == "pending"


# --- Admin Stats ---


@pytest.mark.asyncio
async def test_admin_stats_include_robot_fields(admin_client):
    """GET /api/admin/stats should include robot_count, robots_available, active_assignments."""
    resp = await admin_client.get("/api/admin/stats")
    assert resp.status_code == 200
    stats = resp.json()

    assert "robot_count" in stats
    assert "robots_available" in stats
    assert "active_assignments" in stats

    # With no robots created, all should be zero
    assert stats["robot_count"] == 0
    assert stats["robots_available"] == 0
    assert stats["active_assignments"] == 0


# --- Billing Plan Changes ---


@pytest.mark.asyncio
async def test_change_plan_endpoint(auth_client):
    """POST /api/billing/change-plan with plan='pro' should update the local plan."""
    resp = await auth_client.post("/api/billing/change-plan", json={
        "plan": "pro",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["plan"] == "pro"


@pytest.mark.asyncio
async def test_change_plan_same_plan_rejected(auth_client):
    """POST /api/billing/change-plan with the current plan should return 400."""
    # auth_client is on the 'free' plan by default
    resp = await auth_client.post("/api/billing/change-plan", json={
        "plan": "free",
    })
    assert resp.status_code == 400
    assert "Already on this plan" in resp.json()["detail"]
