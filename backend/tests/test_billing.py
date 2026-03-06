"""Tests for Phase 3: Plan Enforcement & Stripe Billing."""

import pytest
import pytest_asyncio


LOT_DATA = {
    "name": "Test Lot",
    "center": {"lat": 40.0, "lng": -74.0},
}


@pytest_asyncio.fixture
async def lot_id(auth_client):
    """Create a lot and return its ID."""
    resp = await auth_client.post("/api/lots", json=LOT_DATA)
    return resp.json()["id"]


# --- Plan Limits ---

@pytest.mark.asyncio
async def test_free_user_lot_limit(auth_client):
    """Free user can create 1 lot but not a 2nd."""
    resp = await auth_client.post("/api/lots", json=LOT_DATA)
    assert resp.status_code == 201

    resp = await auth_client.post("/api/lots", json={
        "name": "Second Lot",
        "center": {"lat": 41.0, "lng": -75.0},
    })
    assert resp.status_code == 403
    assert "Free plan" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_pro_user_unlimited_lots(client):
    """Pro user can create multiple lots."""
    resp = await client.post("/api/auth/register", json={
        "email": "pro@example.com",
        "password": "password123",
    })
    token = resp.json()["token"]
    user_id = resp.json()["user"]["id"]
    client.headers["Authorization"] = f"Bearer {token}"

    # Manually upgrade to pro
    from backend.services.billing_store import set_user_plan
    await set_user_plan(user_id, "pro")

    for i in range(3):
        resp = await client.post("/api/lots", json={
            "name": f"Pro Lot {i}",
            "center": {"lat": 40.0 + i, "lng": -74.0},
        })
        assert resp.status_code == 201


@pytest.mark.asyncio
async def test_free_user_job_limit(auth_client, lot_id):
    """Free user is limited to 5 jobs."""
    for i in range(5):
        resp = await auth_client.post("/api/jobs", json={
            "lotId": lot_id,
            "date": f"2026-04-{i+1:02d}",
        })
        assert resp.status_code == 201

    resp = await auth_client.post("/api/jobs", json={
        "lotId": lot_id,
        "date": "2026-04-06",
    })
    assert resp.status_code == 403
    assert "Free plan" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_user_response_includes_limits(auth_client):
    """UserResponse should include plan limits."""
    resp = await auth_client.get("/api/auth/me")
    data = resp.json()
    assert data["plan"] == "free"
    assert data["limits"]["max_lots"] == 1
    assert data["limits"]["max_jobs"] == 5


# --- Stripe Endpoints (without config) ---

@pytest.mark.asyncio
async def test_checkout_no_stripe(auth_client):
    """Checkout returns 501 when Stripe is not configured."""
    resp = await auth_client.post("/api/billing/create-checkout")
    assert resp.status_code == 501


@pytest.mark.asyncio
async def test_portal_no_stripe(auth_client):
    """Portal returns 501 when Stripe is not configured."""
    resp = await auth_client.get("/api/billing/portal")
    assert resp.status_code == 501


@pytest.mark.asyncio
async def test_webhook_no_stripe(client):
    """Webhook returns 501 when Stripe is not configured."""
    resp = await client.post("/api/billing/webhook", content=b"{}")
    assert resp.status_code == 501
