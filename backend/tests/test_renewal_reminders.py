"""Tests for renewal reminder background loop logic."""

import uuid
from datetime import datetime, timezone, timedelta

import pytest

from backend.services.billing_store import (
    get_subscriptions_expiring_soon,
    mark_renewal_reminder_sent,
)
from backend.database import get_db


async def _create_user(email: str) -> str:
    """Insert a test user directly and return user_id."""
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async for db in get_db():
        await db.execute(
            """INSERT INTO users (id, email, password_hash, name, plan, created_at, updated_at)
               VALUES (?, ?, 'hash', 'Test', 'pro', ?, ?)""",
            (user_id, email, now, now),
        )
        await db.commit()
    return user_id


async def _create_subscription(
    user_id: str,
    status: str = "active",
    plan: str = "pro",
    current_period_end: str | None = None,
    cancel_at_period_end: int = 0,
    renewal_reminder_sent_at: str | None = None,
) -> str:
    """Insert a test subscription directly and return sub_id."""
    sub_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async for db in get_db():
        await db.execute(
            """INSERT INTO subscriptions
               (id, user_id, stripe_customer_id, stripe_subscription_id, plan, status,
                current_period_end, cancel_at_period_end, renewal_reminder_sent_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sub_id, user_id, f"cus_{user_id[:8]}", f"sub_{user_id[:8]}",
             plan, status, current_period_end, cancel_at_period_end, renewal_reminder_sent_at, now, now),
        )
        await db.commit()
    return sub_id


@pytest.mark.asyncio
async def test_expiring_soon_returns_matching_subscriptions(client):
    """Subscriptions expiring within 7 days are returned."""
    user_id = await _create_user("renewal1@example.com")
    expires_in_5_days = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    await _create_subscription(user_id, current_period_end=expires_in_5_days)

    result = await get_subscriptions_expiring_soon(7)
    emails = [r["email"] for r in result]
    assert "renewal1@example.com" in emails


@pytest.mark.asyncio
async def test_expiring_soon_excludes_cancelled(client):
    """Cancelled subscriptions are not returned."""
    user_id = await _create_user("cancelled-renew@example.com")
    expires_in_3_days = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    await _create_subscription(user_id, status="cancelled", current_period_end=expires_in_3_days)

    result = await get_subscriptions_expiring_soon(7)
    emails = [r["email"] for r in result]
    assert "cancelled-renew@example.com" not in emails


@pytest.mark.asyncio
async def test_expiring_soon_excludes_cancel_at_period_end(client):
    """Subscriptions set to cancel at period end are excluded."""
    user_id = await _create_user("cancel-end@example.com")
    expires_in_4_days = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
    await _create_subscription(user_id, current_period_end=expires_in_4_days, cancel_at_period_end=1)

    result = await get_subscriptions_expiring_soon(7)
    emails = [r["email"] for r in result]
    assert "cancel-end@example.com" not in emails


@pytest.mark.asyncio
async def test_expiring_soon_excludes_far_future(client):
    """Subscriptions expiring in 30 days are not returned for 7-day window."""
    user_id = await _create_user("far-future@example.com")
    expires_in_30_days = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    await _create_subscription(user_id, current_period_end=expires_in_30_days)

    result = await get_subscriptions_expiring_soon(7)
    emails = [r["email"] for r in result]
    assert "far-future@example.com" not in emails


@pytest.mark.asyncio
async def test_expiring_soon_excludes_already_reminded(client):
    """Subscriptions already reminded within 6 days are excluded."""
    user_id = await _create_user("reminded@example.com")
    expires_in_5_days = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    reminded_recently = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    await _create_subscription(user_id, current_period_end=expires_in_5_days, renewal_reminder_sent_at=reminded_recently)

    result = await get_subscriptions_expiring_soon(7)
    emails = [r["email"] for r in result]
    assert "reminded@example.com" not in emails


@pytest.mark.asyncio
async def test_mark_renewal_reminder_sent(client):
    """mark_renewal_reminder_sent updates the timestamp."""
    user_id = await _create_user("mark-sent@example.com")
    expires_in_5_days = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    sub_id = await _create_subscription(user_id, current_period_end=expires_in_5_days)

    # Before: should appear
    result = await get_subscriptions_expiring_soon(7)
    assert any(r["id"] == sub_id for r in result)

    # Mark as sent
    await mark_renewal_reminder_sent(sub_id)

    # After: should NOT appear (reminded within 6 days)
    result = await get_subscriptions_expiring_soon(7)
    assert not any(r["id"] == sub_id for r in result)


@pytest.mark.asyncio
async def test_expiring_soon_excludes_no_period_end(client):
    """Subscriptions without current_period_end are excluded."""
    user_id = await _create_user("no-end@example.com")
    await _create_subscription(user_id, current_period_end=None)

    result = await get_subscriptions_expiring_soon(7)
    emails = [r["email"] for r in result]
    assert "no-end@example.com" not in emails
