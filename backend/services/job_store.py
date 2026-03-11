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
    job = {
        "id": d["id"],
        "lotId": d["lot_id"],
        "date": d["date"],
        "status": d["status"],
        "time_preference": d.get("time_preference", "morning"),
        "started_at": d.get("started_at"),
        "completed_at": d.get("completed_at"),
        "robot_id": d.get("robot_id"),
        "created": d["created_at"],
        "modified": d["updated_at"],
    }
    if d.get("lot_name") is not None:
        job["lot_name"] = d["lot_name"]
    return job


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


async def get_priority_job(user_id: str) -> Optional[dict]:
    """Return the active job, or the next pending job, for a user."""
    async for db in get_db():
        cursor = await db.execute(
            """
            SELECT j.*, l.name AS lot_name
            FROM jobs j
            LEFT JOIN lots l ON l.id = j.lot_id AND l.user_id = j.user_id
            WHERE j.user_id = ? AND j.status IN ('in_progress', 'pending')
            ORDER BY
                CASE j.status
                    WHEN 'in_progress' THEN 0
                    ELSE 1
                END,
                CASE
                    WHEN j.status = 'pending' THEN j.date
                    ELSE j.updated_at
                END ASC
            LIMIT 1
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def create_job_atomic(user_id: str, lot_id: str, date: str, max_jobs: int, time_preference: str = "morning") -> Optional[dict]:
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
                """INSERT INTO jobs (id, user_id, lot_id, date, status, time_preference, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)""",
                (job_id, user_id, lot_id, date, time_preference, now, now),
            )
            await db.execute("COMMIT")
        except Exception:
            await db.execute("ROLLBACK")
            raise
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        return _row_to_dict(row)


async def create_job(user_id: str, lot_id: str, date: str, time_preference: str = "morning") -> dict:
    """Create a new job and return its dict representation."""
    job_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        await db.execute(
            """INSERT INTO jobs (id, user_id, lot_id, date, status, time_preference, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)""",
            (job_id, user_id, lot_id, date, time_preference, now, now),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        return _row_to_dict(row)


_VALID_TRANSITIONS = {
    "pending": {"in_progress", "completed"},
    "in_progress": {"completed"},
    "completed": set(),
}


async def update_job(
    user_id: str,
    job_id: str,
    status: Optional[str] = None,
    date: Optional[str] = None,
) -> Optional[dict]:
    """Update non-None fields of a job. Returns None if not found.
    Returns False (not None) if the status transition is invalid."""
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
    now = _now()

    if status is not None:
        current_status = existing["status"]
        allowed = _VALID_TRANSITIONS.get(current_status, set())
        if status != current_status and status not in allowed:
            return False  # Invalid transition
        fields.append("status = ?")
        values.append(status)
        if status == "in_progress" and current_status == "pending":
            fields.append("started_at = ?")
            values.append(now)
        elif status == "completed" and current_status != "completed":
            fields.append("completed_at = ?")
            values.append(now)
    if date is not None:
        fields.append("date = ?")
        values.append(date)

    if not fields:
        return _row_to_dict(existing)

    fields.append("updated_at = ?")
    values.append(now)
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
