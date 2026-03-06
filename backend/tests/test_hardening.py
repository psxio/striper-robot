"""Tests for Phase 1: Production Hardening — rate limits, validation, health, pagination, security headers."""

import pytest


# --- Health Endpoint ---

@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.3.0"


# --- Security Headers ---

@pytest.mark.asyncio
async def test_security_headers(client):
    resp = await client.get("/api/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


# --- Input Validation ---

@pytest.mark.asyncio
async def test_register_bad_email(client):
    resp = await client.post("/api/auth/register", json={
        "email": "not-an-email",
        "password": "password123",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(client):
    resp = await client.post("/api/auth/register", json={
        "email": "valid@example.com",
        "password": "ab",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_long_name(client):
    resp = await client.post("/api/auth/register", json={
        "email": "valid@example.com",
        "password": "password123",
        "name": "x" * 101,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_bad_email(client):
    resp = await client.post("/api/auth/login", json={
        "email": "bad",
        "password": "password123",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_lot_invalid_coords(auth_client):
    resp = await auth_client.post("/api/lots", json={
        "name": "Bad Lot",
        "center": {"lat": 100.0, "lng": -74.0},
    })
    assert resp.status_code == 422

    resp = await auth_client.post("/api/lots", json={
        "name": "Bad Lot",
        "center": {"lat": 40.0, "lng": -200.0},
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_lot_invalid_zoom(auth_client):
    resp = await auth_client.post("/api/lots", json={
        "name": "Bad Zoom",
        "center": {"lat": 40.0, "lng": -74.0},
        "zoom": 25,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_lot_name_too_long(auth_client):
    resp = await auth_client.post("/api/lots", json={
        "name": "x" * 201,
        "center": {"lat": 40.0, "lng": -74.0},
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_job_invalid_status(auth_client):
    lot_resp = await auth_client.post("/api/lots", json={
        "name": "Test Lot",
        "center": {"lat": 40.0, "lng": -74.0},
    })
    lot_id = lot_resp.json()["id"]
    job_resp = await auth_client.post("/api/jobs", json={
        "lotId": lot_id,
        "date": "2026-04-01",
    })
    job_id = job_resp.json()["id"]
    resp = await auth_client.patch(f"/api/jobs/{job_id}", json={
        "status": "invalid_status",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_lot_feature_limit(auth_client):
    """Verify that lots reject more than 10000 features."""
    resp = await auth_client.post("/api/lots", json={
        "name": "Too Many Features",
        "center": {"lat": 40.0, "lng": -74.0},
        "features": [{"type": "Feature"} for _ in range(10001)],
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_waitlist_bad_email(client):
    resp = await client.post("/api/waitlist", json={
        "email": "not-valid",
    })
    assert resp.status_code == 422


# --- Pagination ---

@pytest.mark.asyncio
async def test_lots_pagination(auth_client):
    # Upgrade to pro to create multiple lots
    from backend.services.billing_store import set_user_plan
    me = await auth_client.get("/api/auth/me")
    await set_user_plan(me.json()["id"], "pro")

    # Create 3 lots
    for i in range(3):
        await auth_client.post("/api/lots", json={
            "name": f"Lot {i}",
            "center": {"lat": 40.0, "lng": -74.0},
        })
    # Page 1, limit 2
    resp = await auth_client.get("/api/lots?page=1&limit=2")
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["limit"] == 2

    # Page 2, limit 2
    resp = await auth_client.get("/api/lots?page=2&limit=2")
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["total"] == 3
    assert data["page"] == 2


@pytest.mark.asyncio
async def test_jobs_pagination(auth_client):
    lot_resp = await auth_client.post("/api/lots", json={
        "name": "Pagination Lot",
        "center": {"lat": 40.0, "lng": -74.0},
    })
    lot_id = lot_resp.json()["id"]
    for i in range(3):
        await auth_client.post("/api/jobs", json={
            "lotId": lot_id,
            "date": f"2026-04-{i+1:02d}",
        })
    resp = await auth_client.get("/api/jobs?page=1&limit=2")
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 3


# --- Rate Limiting ---

@pytest.mark.asyncio
async def test_login_rate_limit(client):
    """Verify login is rate-limited to 5/minute."""
    from backend.rate_limit import limiter
    limiter.enabled = True
    try:
        # Send 5 login requests (all will fail with 401 but still count)
        for _ in range(5):
            await client.post("/api/auth/login", json={
                "email": "test@example.com",
                "password": "wrongpassword1",
            })
        # 6th should be rate limited
        resp = await client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword1",
        })
        assert resp.status_code == 429
    finally:
        limiter.enabled = False
