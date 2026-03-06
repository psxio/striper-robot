"""Waitlist persistence layer using aiosqlite."""

from datetime import datetime, timezone

from ..database import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def add_to_waitlist(email: str, source: str = "landing") -> dict:
    """Add an email to the waitlist and return the created entry."""
    now = _now()
    async for db in get_db():
        cursor = await db.execute(
            "INSERT INTO waitlist (email, source, created_at) VALUES (?, ?, ?)",
            (email, source, now),
        )
        await db.commit()
        return {
            "id": cursor.lastrowid,
            "email": email,
            "source": source,
            "created_at": now,
        }
