"""SQLite-backed job persistence using aiosqlite."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite

from ..models.schemas import JobCreate, JobResponse, JobStatus, JobUpdate

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "jobs.db"


async def _ensure_db() -> None:
    """Create the database and tables if they do not exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                path_data TEXT,
                metadata TEXT
            )
        """)
        await db.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_job(row: aiosqlite.Row) -> JobResponse:
    return JobResponse(
        id=row[0],
        name=row[1],
        status=JobStatus(row[2]),
        created_at=row[3],
        updated_at=row[4],
        path_data=json.loads(row[5]) if row[5] else None,
        metadata=json.loads(row[6]) if row[6] else None,
    )


async def init_db() -> None:
    await _ensure_db()


async def create_job(job: JobCreate) -> JobResponse:
    now = _now()
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "INSERT INTO jobs (name, status, created_at, updated_at, path_data, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (
                job.name,
                JobStatus.PENDING.value,
                now,
                now,
                json.dumps(job.path_data) if job.path_data else None,
                json.dumps(job.metadata) if job.metadata else None,
            ),
        )
        await db.commit()
        job_id = cursor.lastrowid

        row = await db.execute_fetchall(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        )
        return _row_to_job(row[0])


async def get_job(job_id: int) -> Optional[JobResponse]:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        rows = await db.execute_fetchall(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        )
        if not rows:
            return None
        return _row_to_job(rows[0])


async def list_jobs() -> list[JobResponse]:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        rows = await db.execute_fetchall(
            "SELECT * FROM jobs ORDER BY updated_at DESC"
        )
        return [_row_to_job(r) for r in rows]


async def update_job(job_id: int, update: JobUpdate) -> Optional[JobResponse]:
    existing = await get_job(job_id)
    if not existing:
        return None

    fields: list[str] = []
    values: list[object] = []

    if update.name is not None:
        fields.append("name = ?")
        values.append(update.name)
    if update.status is not None:
        fields.append("status = ?")
        values.append(update.status.value)
    if update.path_data is not None:
        fields.append("path_data = ?")
        values.append(json.dumps(update.path_data))
    if update.metadata is not None:
        fields.append("metadata = ?")
        values.append(json.dumps(update.metadata))

    if not fields:
        return existing

    fields.append("updated_at = ?")
    values.append(_now())
    values.append(job_id)

    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        await db.commit()

    return await get_job(job_id)


async def delete_job(job_id: int) -> bool:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        await db.commit()
        return cursor.rowcount > 0
