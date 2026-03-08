"""Waitlist persistence layer using aiosqlite."""

from datetime import datetime, timezone

from ..database import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def add_to_waitlist(email: str, source: str = "landing") -> dict:
    """Add an email to the waitlist. Deduplicates by email."""
    now = _now()
    async for db in get_db():
        # Check for duplicate
        cursor = await db.execute(
            "SELECT * FROM waitlist WHERE email = ?", (email,)
        )
        existing = await cursor.fetchone()
        if existing:
            return dict(existing)

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


async def delete_waitlist_entry(entry_id: int) -> bool:
    """Delete a waitlist entry by ID."""
    async for db in get_db():
        cursor = await db.execute(
            "DELETE FROM waitlist WHERE id = ?", (entry_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
