"""Tests for Phase 1: Billing guards and plan enforcement.

Verifies that:
- Free-tier users (no subscription) can create resources up to plan limits
- Active subscribers can create resources up to their plan limits
- Cancelled/past_due subscribers are blocked from creating resources
- Robot claim tier limits are enforced per organization
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _register(client: AsyncClient, email: str, password: str = "testpass123", name: str = "Test") -> dict:
    resp = await client.post("/api/auth/register", json={"email": email, "password": password, "name": name})
    assert resp.status_code == 201
    return resp.json()


async def _set_plan(user_id: str, plan: str):
    from backend.services.billing_store import set_user_plan
    await set_user_plan(user_id, plan)


async def _create_subscription(user_id: str, status: str = "active", plan: str = "pro"):
    """Insert a subscription record directly for testing."""
    import uuid
    from datetime import datetime, timezone
    from backend.database import get_db
    sub_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async for db in get_db():
        await db.execute(
            """INSERT INTO subscriptions
               (id, user_id, stripe_customer_id, stripe_subscription_id, plan, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (sub_id, user_id, f"cus_{user_id[:8]}", f"sub_{user_id[:8]}", plan, status, now, now),
        )
        await db.commit()
    return sub_id


async def _create_lot(client: AsyncClient) -> dict:
    resp = await client.post("/api/lots", json={
        "name": "Test Lot",
        "center": {"lat": 33.0, "lng": -97.0},
        "zoom": 18,
        "features": [],
    })
    return resp


async def _create_job(client: AsyncClient, lot_id: str) -> dict:
    resp = await client.post("/api/jobs", json={
        "lotId": lot_id,
        "date": "2026-04-01",
    })
    return resp


# ---------------------------------------------------------------------------
# Free-tier users (no subscription) — should be ALLOWED within limits
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_free_user_can_create_lot(auth_client):
    """Free user with no subscription can create 1 lot (plan limit)."""
    resp = await _create_lot(auth_client)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_free_user_blocked_at_lot_limit(auth_client):
    """Free user cannot exceed 1 lot."""
    resp = await _create_lot(auth_client)
    assert resp.status_code == 201
    # Second lot should be blocked
    resp = await _create_lot(auth_client)
    assert resp.status_code == 403
    assert "limited" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_free_user_can_create_jobs_up_to_limit(auth_client):
    """Free user can create up to 5 jobs."""
    lot_resp = await _create_lot(auth_client)
    lot_id = lot_resp.json()["id"]
    for i in range(5):
        resp = await _create_job(auth_client, lot_id)
        assert resp.status_code == 201, f"Job {i+1} failed: {resp.json()}"
    # 6th job should be blocked
    resp = await _create_job(auth_client, lot_id)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Active subscribers — should be ALLOWED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_active_pro_subscriber_can_create_lots(client):
    """Pro user with active subscription can create multiple lots."""
    data = await _register(client, "activepro@example.com")
    user_id = data["user"]["id"]
    client.headers["Authorization"] = f"Bearer {data['token']}"
    await _set_plan(user_id, "pro")
    await _create_subscription(user_id, status="active", plan="pro")

    # Create several lots — pro has 999 limit
    for i in range(3):
        resp = await _create_lot(client)
        assert resp.status_code == 201, f"Lot {i+1} failed"


# ---------------------------------------------------------------------------
# Cancelled subscribers — should be BLOCKED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancelled_subscriber_blocked_from_creating_lot(client):
    """User with cancelled subscription cannot create lots."""
    data = await _register(client, "cancelled@example.com")
    user_id = data["user"]["id"]
    client.headers["Authorization"] = f"Bearer {data['token']}"
    # User was pro, subscription got cancelled, plan downgraded to free
    await _set_plan(user_id, "free")
    await _create_subscription(user_id, status="cancelled", plan="pro")

    resp = await _create_lot(client)
    assert resp.status_code == 403
    assert "billing" in resp.json()["detail"].lower() or "subscription" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cancelled_subscriber_blocked_from_creating_job(client):
    """User with cancelled subscription cannot create jobs."""
    data = await _register(client, "cancelledjob@example.com")
    user_id = data["user"]["id"]
    client.headers["Authorization"] = f"Bearer {data['token']}"
    await _set_plan(user_id, "free")
    await _create_subscription(user_id, status="cancelled", plan="pro")

    # They can't even create a lot, so we test the jobs endpoint directly
    resp = await client.post("/api/jobs", json={
        "lotId": "nonexistent",
        "date": "2026-04-01",
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_past_due_subscriber_blocked(client):
    """User with past_due subscription is blocked from creating resources."""
    data = await _register(client, "pastdue@example.com")
    user_id = data["user"]["id"]
    client.headers["Authorization"] = f"Bearer {data['token']}"
    # Plan still shows pro (webhook hasn't downgraded yet) but subscription is past_due
    await _set_plan(user_id, "pro")
    await _create_subscription(user_id, status="past_due", plan="pro")

    resp = await _create_lot(client)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Schedule billing guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancelled_subscriber_blocked_from_creating_schedule(client):
    """Cancelled subscriber cannot create recurring schedules."""
    data = await _register(client, "cancelsched@example.com")
    user_id = data["user"]["id"]
    client.headers["Authorization"] = f"Bearer {data['token']}"
    await _set_plan(user_id, "pro")
    await _create_subscription(user_id, status="cancelled", plan="pro")

    resp = await client.post("/api/schedules", json={
        "lot_id": "nonexistent",
        "frequency": "weekly",
        "day_of_week": 1,
    })
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Robot claim tier limits
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_free_user_cannot_claim_robot(client):
    """Free-tier user (robots=0) is blocked from claiming a robot."""
    data = await _register(client, "freeclaim@example.com")
    client.headers["Authorization"] = f"Bearer {data['token']}"
    # Free users have robots=0 in PLAN_LIMITS

    # Try to claim with a fake code — should hit billing/tier check before code validation
    resp = await client.post("/api/robot-claims/fake_code/claim", json={
        "friendly_name": "My Robot",
        "deployment_notes": "",
    })
    # Should be 403 (tier limit) or 403 (billing) — not 400 (invalid code)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_robot_tier_can_claim_one_robot(client):
    """Robot-tier user can claim 1 robot, is blocked on 2nd."""
    from backend.services.admin_store import set_admin

    # Register admin user
    admin_data = await _register(client, "claimadmin@example.com")
    admin_token = admin_data["token"]
    await set_admin(admin_data["user"]["id"], True)

    # Register a robot-tier user
    from httpx import AsyncClient, ASGITransport
    from backend.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as user_client:
        user_data = await _register(user_client, "robottier@example.com")
        user_id = user_data["user"]["id"]
        user_client.headers["Authorization"] = f"Bearer {user_data['token']}"
        await _set_plan(user_id, "robot")

        # Admin creates a robot and generates a claim code
        client.headers["Authorization"] = f"Bearer {admin_token}"
        robot_resp = await client.post("/api/admin/robots", json={"serial_number": "CLAIM-001"})
        assert robot_resp.status_code == 201
        robot_id = robot_resp.json()["id"]
        claim_resp = await client.post("/api/robot-claims", json={"robot_id": robot_id})
        assert claim_resp.status_code == 201
        code1 = claim_resp.json()["claim_code"]

        # Robot-tier user claims first robot — should succeed
        resp = await user_client.post(f"/api/robot-claims/{code1}/claim", json={
            "friendly_name": "Primary Robot",
            "deployment_notes": "First robot",
        })
        assert resp.status_code == 200

        # Admin creates second robot + claim
        robot_resp2 = await client.post("/api/admin/robots", json={"serial_number": "CLAIM-002"})
        robot_id2 = robot_resp2.json()["id"]
        claim_resp2 = await client.post("/api/robot-claims", json={"robot_id": robot_id2})
        code2 = claim_resp2.json()["claim_code"]

        # Robot-tier user tries to claim second — should be blocked (limit=1)
        resp2 = await user_client.post(f"/api/robot-claims/{code2}/claim", json={
            "friendly_name": "Second Robot",
            "deployment_notes": "Should fail",
        })
        assert resp2.status_code == 403
        assert "plan" in resp2.json()["detail"].lower() or "robot" in resp2.json()["detail"].lower()


# ---------------------------------------------------------------------------
# is_billing_active unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_is_billing_active_no_subscription(client):
    """User with no subscription row → billing is active (free tier)."""
    data = await _register(client, "nosub@example.com")
    from backend.services.billing_store import is_billing_active
    assert await is_billing_active(data["user"]["id"]) is True


@pytest.mark.asyncio
async def test_is_billing_active_active_subscription(client):
    """User with active subscription → billing is active."""
    data = await _register(client, "activesub@example.com")
    await _create_subscription(data["user"]["id"], status="active")
    from backend.services.billing_store import is_billing_active
    assert await is_billing_active(data["user"]["id"]) is True


@pytest.mark.asyncio
async def test_is_billing_active_cancelled_subscription(client):
    """User with cancelled subscription → billing is NOT active."""
    data = await _register(client, "cancelledsub@example.com")
    await _create_subscription(data["user"]["id"], status="cancelled")
    from backend.services.billing_store import is_billing_active
    assert await is_billing_active(data["user"]["id"]) is False


@pytest.mark.asyncio
async def test_is_billing_active_past_due_subscription(client):
    """User with past_due subscription → billing is NOT active."""
    data = await _register(client, "pastduesub@example.com")
    await _create_subscription(data["user"]["id"], status="past_due")
    from backend.services.billing_store import is_billing_active
    assert await is_billing_active(data["user"]["id"]) is False
