"""Tests for Phase 3: Plan Enforcement & Stripe Billing."""

import sys
import types

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
    assert "limited to" in resp.json()["detail"].lower()


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
    assert "limited to" in resp.json()["detail"].lower()


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


def _install_fake_stripe(monkeypatch, event=None, *, on_delete=None, on_retrieve=None, on_modify=None):
    class FakeStripeError(Exception):
        pass

    class FakeSignatureVerificationError(Exception):
        pass

    class FakeWebhook:
        @staticmethod
        def construct_event(payload, sig, secret):
            return event

    class FakeSubscription:
        @staticmethod
        def delete(subscription_id):
            if on_delete:
                return on_delete(subscription_id)
            return {"id": subscription_id}

        @staticmethod
        def retrieve(subscription_id):
            if on_retrieve:
                return on_retrieve(subscription_id)
            return {"id": subscription_id, "items": {"data": [{"id": "si_default"}]}}

        @staticmethod
        def modify(subscription_id, items=None, proration_behavior=None):
            if on_modify:
                return on_modify(subscription_id, items, proration_behavior)
            return {"id": subscription_id}

    fake_stripe = types.SimpleNamespace(
        api_key="",
        Webhook=FakeWebhook,
        Subscription=FakeSubscription,
        error=types.SimpleNamespace(
            StripeError=FakeStripeError,
            SignatureVerificationError=FakeSignatureVerificationError,
        ),
    )
    monkeypatch.setitem(sys.modules, "stripe", fake_stripe)
    return fake_stripe


@pytest.mark.asyncio
async def test_change_plan_free_cancels_stripe_subscription(client, monkeypatch):
    """Downgrading to free should cancel the upstream Stripe subscription as well as local state."""
    from backend.config import settings
    from backend.services.billing_store import create_subscription

    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(settings, "STRIPE_PRICE_ID", "price_pro")

    resp = await client.post("/api/auth/register", json={
        "email": "cancel@example.com",
        "password": "password123",
    })
    token = resp.json()["token"]
    user_id = resp.json()["user"]["id"]
    client.headers["Authorization"] = f"Bearer {token}"

    await create_subscription(
        user_id=user_id,
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_123",
        plan="pro",
        status="active",
    )

    cancelled = {}

    def on_delete(subscription_id):
        cancelled["subscription_id"] = subscription_id
        return {"id": subscription_id}

    _install_fake_stripe(monkeypatch, on_delete=on_delete)

    resp = await client.post("/api/billing/change-plan", json={"plan": "free"})
    assert resp.status_code == 200
    assert cancelled["subscription_id"] == "sub_123"

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["plan"] == "free"


@pytest.mark.asyncio
async def test_webhook_invoice_paid_preserves_robot_plan(client, monkeypatch):
    """Invoice webhook should not coerce a robot subscription back to pro."""
    from backend.config import settings
    from backend.services.billing_store import create_subscription, get_subscription_by_user

    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(settings, "STRIPE_PRICE_ID", "price_pro")
    monkeypatch.setattr(settings, "STRIPE_ROBOT_PRICE_ID", "price_robot")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")

    resp = await client.post("/api/auth/register", json={
        "email": "robot-plan@example.com",
        "password": "password123",
    })
    user_id = resp.json()["user"]["id"]

    await create_subscription(
        user_id=user_id,
        stripe_customer_id="cus_robot",
        stripe_subscription_id="sub_robot",
        plan="robot",
        status="active",
    )

    event = {
        "id": "evt_invoice_paid",
        "type": "invoice.paid",
        "data": {
            "object": {
                "subscription": "sub_robot",
                "lines": {
                    "data": [
                        {"price": {"id": "price_robot"}},
                    ]
                },
            }
        },
    }
    _install_fake_stripe(monkeypatch, event=event)

    resp = await client.post(
        "/api/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "sig"},
    )
    assert resp.status_code == 200

    sub = await get_subscription_by_user(user_id)
    assert sub["plan"] == "robot"


@pytest.mark.asyncio
async def test_change_plan_uses_subscription_item_id_for_stripe_modify(client, monkeypatch):
    """Paid plan changes must send the Stripe subscription item ID, not the subscription ID."""
    from backend.config import settings
    from backend.services.billing_store import create_subscription

    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(settings, "STRIPE_PRICE_ID", "price_pro")
    monkeypatch.setattr(settings, "STRIPE_ROBOT_PRICE_ID", "price_robot")

    resp = await client.post("/api/auth/register", json={
        "email": "modify@example.com",
        "password": "password123",
    })
    token = resp.json()["token"]
    user_id = resp.json()["user"]["id"]
    client.headers["Authorization"] = f"Bearer {token}"

    await create_subscription(
        user_id=user_id,
        stripe_customer_id="cus_modify",
        stripe_subscription_id="sub_modify",
        plan="pro",
        status="active",
    )

    captured = {}

    def on_retrieve(subscription_id):
        return {"id": subscription_id, "items": {"data": [{"id": "si_123"}]}}

    def on_modify(subscription_id, items, proration_behavior):
        captured["subscription_id"] = subscription_id
        captured["item_id"] = items[0]["id"]
        captured["price"] = items[0]["price"]
        captured["proration_behavior"] = proration_behavior
        return {"id": subscription_id}

    _install_fake_stripe(monkeypatch, on_retrieve=on_retrieve, on_modify=on_modify)

    resp = await client.post("/api/billing/change-plan", json={"plan": "robot"})
    assert resp.status_code == 200
    assert captured == {
        "subscription_id": "sub_modify",
        "item_id": "si_123",
        "price": "price_robot",
        "proration_behavior": "create_prorations",
    }
