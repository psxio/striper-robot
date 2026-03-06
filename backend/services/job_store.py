"""Job persistence layer using aiosqlite with tenant isolation."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from ..database import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row) -> dict:
    """Convert a DB row to a frontend-shaped dict."""
    d = dict(row)
    return {
        "id": d["id"],
        "lotId": d["lot_id"],
        "date": d["date"],
        "status": d["status"],
        "created": d["created_at"],
        "modified": d["updated_at"],
    }


async def list_jobs(user_id: str, page: int = 1, limit: int = 50, status: str | None = None, lot_id: str | None = None) -> tuple[list[dict], int]:
    """Return paginated jobs for a given user, optionally filtered."""
    async for db in get_db():
        where = "WHERE user_id = ?"
        params: list = [user_id]
        if status:
            where += " AND status = ?"
            params.append(status)
        if lot_id:
            where += " AND lot_id = ?"
            params.append(lot_id)

        cursor = await db.execute(
            f"SELECT COUNT(*) FROM jobs {where}", tuple(params)
        )
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * limit
        cursor = await db.execute(
            f"SELECT * FROM jobs {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            tuple(params + [limit, offset]),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows], total


async def count_jobs(user_id: str) -> int:
    """Return the total number of jobs for a user."""
    async for db in get_db():
        cursor = await db.execute(
            "SELECT COUNT(*) FROM jobs WHERE user_id = ?", (user_id,)
        )
        return (await cursor.fetchone())[0]


async def create_job_atomic(user_id: str, lot_id: str, date: str, max_jobs: int) -> Optional[dict]:
    """Create a job atomically with plan limit check. Returns None if over limit."""
    job_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        await db.execute("BEGIN IMMEDIATE")
        try:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM jobs WHERE user_id = ?", (user_id,)
            )
            count = (await cursor.fetchone())[0]
            if count >= max_jobs:
                await db.execute("ROLLBACK")
                return None
            await db.execute(
                """INSERT INTO jobs (id, user_id, lot_id, date, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
                (job_id, user_id, lot_id, date, now, now),
            )
            await db.execute("COMMIT")
        except Exception:
            await db.execute("ROLLBACK")
            raise
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        return _row_to_dict(row)


async def create_job(user_id: str, lot_id: str, date: str) -> dict:
    """Create a new job and return its dict representation."""
    job_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        await db.execute(
            """INSERT INTO jobs (id, user_id, lot_id, date, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
            (job_id, user_id, lot_id, date, now, now),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        return _row_to_dict(row)


async def update_job(
    user_id: str,
    job_id: str,
    status: Optional[str] = None,
    date: Optional[str] = None,
) -> Optional[dict]:
    """Update non-None fields of a job. Returns None if not found."""
    # Check existence and ownership
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM jobs WHERE id = ? AND user_id = ?",
            (job_id, user_id),
        )
        existing = await cursor.fetchone()
        if not existing:
            return None

    fields: list[str] = []
    values: list[object] = []

    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if date is not None:
        fields.append("date = ?")
        values.append(date)

    if not fields:
        return _row_to_dict(existing)

    fields.append("updated_at = ?")
    values.append(_now())
    values.append(job_id)
    values.append(user_id)

    async for db in get_db():
        await db.execute(
            f"UPDATE jobs SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            tuple(values),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM jobs WHERE id = ? AND user_id = ?",
            (job_id, user_id),
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def delete_job(user_id: str, job_id: str) -> bool:
    """Delete a job. Returns True if it existed and was deleted."""
    async for db in get_db():
        cursor = await db.execute(
            "DELETE FROM jobs WHERE id = ? AND user_id = ?",
            (job_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0
