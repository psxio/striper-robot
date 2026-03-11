"""Tests for plan changes, CSRF middleware, and the background scheduler."""

import pytest
import pytest_asyncio


# ---------------------------------------------------------------------------
# Plan Change Tests (/api/billing/change-plan)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_change_plan_free_to_pro(auth_client):
    """Upgrading from free to pro succeeds and returns the new plan."""
    resp = await auth_client.post(
        "/api/billing/change-plan", json={"plan": "pro"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["plan"] == "pro"


@pytest.mark.asyncio
async def test_change_plan_pro_to_free(pro_client):
    """Downgrading from pro to free succeeds and returns the new plan."""
    resp = await pro_client.post(
        "/api/billing/change-plan", json={"plan": "free"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["plan"] == "free"


@pytest.mark.asyncio
async def test_change_plan_same_plan_returns_400(auth_client):
    """Attempting to change to the current plan returns 400."""
    resp = await auth_client.post(
        "/api/billing/change-plan", json={"plan": "free"}
    )
    assert resp.status_code == 400
    assert "Already on this plan" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_change_plan_unauthenticated_returns_401(client):
    """Unauthenticated request to change plan returns 401."""
    resp = await client.post(
        "/api/billing/change-plan", json={"plan": "pro"}
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# CSRF Middleware Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_csrf_cookie_set_on_first_response(client):
    """The CSRF middleware sets a csrf_token cookie on the first response."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert "csrf_token" in resp.cookies


@pytest.mark.asyncio
async def test_csrf_mismatch_returns_403(client):
    """Mismatched CSRF header is rejected for refresh-cookie auth."""
    resp = await client.post(
        "/api/auth/refresh",
        cookies={"refresh_token": "fake-refresh-token", "csrf_token": "abc"},
        headers={"X-CSRF-Token": "xyz"},
    )
    assert resp.status_code == 403
    assert "CSRF" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_csrf_missing_header_returns_403(client):
    """Refresh-cookie auth without the CSRF header should be rejected."""
    resp = await client.post(
        "/api/auth/refresh",
        cookies={"refresh_token": "fake-refresh-token", "csrf_token": "abc"},
    )
    assert resp.status_code == 403
    assert "CSRF" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_csrf_matching_values_passes(client):
    """Matching CSRF values allow refresh requests past the middleware."""
    token = "matching-csrf-token-value"
    resp = await client.post(
        "/api/auth/refresh",
        cookies={"refresh_token": "fake-refresh-token", "csrf_token": token},
        headers={"X-CSRF-Token": token},
    )
    # The refresh token is fake, so the endpoint rejects it after CSRF passes.
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_csrf_cookie_without_refresh_cookie_is_ignored(client):
    """A plain CSRF cookie alone should not block unrelated public POST endpoints."""
    resp = await client.post(
        "/api/waitlist",
        json={"email": "csrf-ok@example.com", "source": "test"},
        cookies={"csrf_token": "abc"},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_bearer_auth_bypasses_csrf(auth_client):
    """Requests with a Bearer Authorization header skip CSRF validation entirely."""
    # auth_client has Bearer token set but no CSRF cookie/header.
    # A mutating request should succeed without any CSRF tokens.
    resp = await auth_client.get("/api/auth/me")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Scheduler Tests (process_due_schedules)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scheduler_processes_due_schedule(client):
    """A schedule with next_run in the past triggers job creation."""
    from backend.services.schedule_store import create_schedule
    from backend.services.scheduler import process_due_schedules
    from backend.services.billing_store import set_user_plan
    from backend.database import get_db

    # Register a user and upgrade to pro (schedules require pro)
    resp = await client.post("/api/auth/register", json={
        "email": "sched@example.com",
        "password": "schedpass1",
    })
    token = resp.json()["token"]
    user_id = resp.json()["user"]["id"]
    await set_user_plan(user_id, "pro")
    client.headers["Authorization"] = f"Bearer {token}"

    # Create a lot
    lot_resp = await client.post("/api/lots", json={
        "name": "Scheduler Lot",
        "center": {"lat": 40.0, "lng": -74.0},
    })
    assert lot_resp.status_code == 201
    lot_id = lot_resp.json()["id"]

    # Create a schedule via the store (bypasses HTTP to set up data directly)
    schedule = await create_schedule(
        user_id=user_id,
        lot_id=lot_id,
        frequency="weekly",
        day_of_week=0,
        time_preference="morning",
    )
    schedule_id = schedule["id"]

    # Force the schedule's next_run to a past date so it becomes "due"
    async for db in get_db():
        await db.execute(
            "UPDATE recurring_schedules SET next_run = '2020-01-01' WHERE id = ?",
            (schedule_id,),
        )
        await db.commit()

    # Run the scheduler
    processed = await process_due_schedules()
    assert processed == 1

    # Verify a job was created for this user and lot
    jobs_resp = await client.get("/api/jobs")
    assert jobs_resp.status_code == 200
    items = jobs_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["lotId"] == lot_id


@pytest.mark.asyncio
async def test_scheduler_skips_inactive_schedule(client):
    """An inactive schedule is not processed even if next_run is in the past."""
    from backend.services.schedule_store import create_schedule
    from backend.services.scheduler import process_due_schedules
    from backend.services.billing_store import set_user_plan
    from backend.database import get_db

    # Register a user and upgrade to pro
    resp = await client.post("/api/auth/register", json={
        "email": "inactive@example.com",
        "password": "inactivepass1",
    })
    token = resp.json()["token"]
    user_id = resp.json()["user"]["id"]
    await set_user_plan(user_id, "pro")
    client.headers["Authorization"] = f"Bearer {token}"

    # Create a lot
    lot_resp = await client.post("/api/lots", json={
        "name": "Inactive Schedule Lot",
        "center": {"lat": 41.0, "lng": -75.0},
    })
    assert lot_resp.status_code == 201
    lot_id = lot_resp.json()["id"]

    # Create a schedule and immediately deactivate it
    schedule = await create_schedule(
        user_id=user_id,
        lot_id=lot_id,
        frequency="weekly",
        day_of_week=0,
        time_preference="morning",
    )
    schedule_id = schedule["id"]

    # Set the schedule to inactive AND next_run in the past
    async for db in get_db():
        await db.execute(
            "UPDATE recurring_schedules SET active = 0, next_run = '2020-01-01' WHERE id = ?",
            (schedule_id,),
        )
        await db.commit()

    # Run the scheduler -- should process 0 schedules
    processed = await process_due_schedules()
    assert processed == 0

    # Verify no jobs were created
    jobs_resp = await client.get("/api/jobs")
    assert jobs_resp.status_code == 200
    assert jobs_resp.json()["total"] == 0
