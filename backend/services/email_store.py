"""Email event persistence: bounce/unsubscribe tracking and suppression."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from ..database import get_db

# Event types that cause email suppression
_SUPPRESSION_TYPES = ("bounce", "spamreport", "unsubscribe")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def record_email_event(
    email: str,
    event_type: str,
    reason: str = "",
    sg_event_id: str | None = None,
    sg_message_id: str = "",
) -> dict:
    """Record a SendGrid webhook event. Deduplicates by sg_event_id."""
    event_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        await db.execute(
            """INSERT OR IGNORE INTO email_events
               (id, email, event_type, reason, sg_event_id, sg_message_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (event_id, email.lower(), event_type, reason, sg_event_id, sg_message_id, now),
        )
        await db.commit()
    return {"id": event_id, "email": email, "event_type": event_type}


async def is_email_suppressed(email: str) -> bool:
    """Check if an email address should be suppressed (bounced, spam reported, or unsubscribed)."""
    async for db in get_db():
        cursor = await db.execute(
            "SELECT 1 FROM email_events WHERE email = ? AND event_type IN (?, ?, ?) LIMIT 1",
            (email.lower(), *_SUPPRESSION_TYPES),
        )
        return await cursor.fetchone() is not None


async def get_events_for_email(email: str, limit: int = 50) -> list[dict]:
    """Get recent email events for an address (admin troubleshooting)."""
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM email_events WHERE email = ? ORDER BY created_at DESC LIMIT ?",
            (email.lower(), limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
