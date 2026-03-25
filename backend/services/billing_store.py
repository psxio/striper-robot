"""Billing/subscription persistence layer using aiosqlite."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from ..database import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_subscription_by_user(user_id: str) -> Optional[dict]:
    """Get the most recent active subscription for a user."""
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM subscriptions WHERE user_id = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_subscription_by_stripe_id(stripe_subscription_id: str) -> Optional[dict]:
    """Get subscription by Stripe subscription ID."""
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM subscriptions WHERE stripe_subscription_id = ?",
            (stripe_subscription_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_subscription(
    user_id: str,
    stripe_customer_id: str,
    stripe_subscription_id: str,
    plan: str = "pro",
    status: str = "active",
    current_period_end: Optional[str] = None,
) -> dict:
    """Create a new subscription record."""
    sub_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        await db.execute(
            """INSERT INTO subscriptions
               (id, user_id, stripe_customer_id, stripe_subscription_id, plan, status, current_period_end, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sub_id, user_id, stripe_customer_id, stripe_subscription_id,
             plan, status, current_period_end, now, now),
        )
        # Update user's stripe_customer_id and plan
        await db.execute(
            "UPDATE users SET stripe_customer_id = ?, plan = ?, updated_at = ? WHERE id = ?",
            (stripe_customer_id, plan, now, user_id),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,))
        row = await cursor.fetchone()
        return dict(row)


async def update_subscription_status(
    stripe_subscription_id: str,
    status: str,
    plan: Optional[str] = None,
) -> Optional[dict]:
    """Update subscription status (e.g., when cancelled)."""
    now = _now()
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM subscriptions WHERE stripe_subscription_id = ?",
            (stripe_subscription_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        sub = dict(row)
        new_plan = plan or sub["plan"]

        await db.execute(
            "UPDATE subscriptions SET status = ?, plan = ?, updated_at = ? WHERE stripe_subscription_id = ?",
            (status, new_plan, now, stripe_subscription_id),
        )

        # If cancelled, downgrade user to free
        user_plan = new_plan if status == "active" else "free"
        await db.execute(
            "UPDATE users SET plan = ?, updated_at = ? WHERE id = ?",
            (user_plan, now, sub["user_id"]),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM subscriptions WHERE stripe_subscription_id = ?",
            (stripe_subscription_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def set_user_plan(user_id: str, plan: str) -> bool:
    """Directly set a user's plan (for admin use)."""
    now = _now()
    async for db in get_db():
        cursor = await db.execute(
            "UPDATE users SET plan = ?, updated_at = ? WHERE id = ?",
            (plan, now, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def is_billing_active(user_id: str) -> bool:
    """Check whether a user is allowed to create resources.

    - Free-tier users (no subscription row, plan='free') → always allowed
    - Paid users → allowed only if their subscription status is 'active'
    - Users with a cancelled/past_due/unpaid subscription → blocked

    This queries the subscriptions table directly rather than relying on the
    user's plan column, which may have a race window after cancellation.
    """
    async for db in get_db():
        # Check if user has any non-free subscription
        cursor = await db.execute(
            "SELECT status FROM subscriptions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            # No subscription record — free tier, always allowed
            return True
        return row["status"] == "active"
