"""Job and execution persistence layer using aiosqlite."""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..database import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row) -> dict:
    data = dict(row)
    job = {
        "id": data["id"],
        "lotId": data["lot_id"],
        "organization_id": data.get("organization_id"),
        "site_id": data.get("site_id"),
        "quote_id": data.get("quote_id"),
        "date": data["date"],
        "status": data["status"],
        "time_preference": data.get("time_preference", "morning"),
        "scheduled_start_at": data.get("scheduled_start_at"),
        "scheduled_end_at": data.get("scheduled_end_at"),
        "assigned_user_id": data.get("assigned_user_id"),
        "started_at": data.get("started_at"),
        "completed_at": data.get("completed_at"),
        "verified_at": data.get("verified_at"),
        "robot_id": data.get("robot_id"),
        "notes": data.get("notes") or "",
        "created": data["created_at"],
        "modified": data["updated_at"],
    }
    if data.get("lot_name") is not None:
        job["lot_name"] = data["lot_name"]
    if data.get("site_name") is not None:
        job["site_name"] = data["site_name"]
    return job


def _job_run_to_dict(row) -> dict:
    data = dict(row)
    data["telemetry_summary"] = json.loads(data.get("telemetry_summary") or "{}")
    return data


async def get_job(user_id: str, job_id: str) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute(
            """SELECT j.*, l.name AS lot_name, s.name AS site_name
               FROM jobs j
               LEFT JOIN lots l ON l.id = j.lot_id
               LEFT JOIN sites s ON s.id = j.site_id
               WHERE j.id = ? AND j.user_id = ?""",
            (job_id, user_id),
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def get_job_by_org(organization_id: str, job_id: str) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute(
            """SELECT j.*, l.name AS lot_name, s.name AS site_name
               FROM jobs j
               LEFT JOIN lots l ON l.id = j.lot_id
               LEFT JOIN sites s ON s.id = j.site_id
               WHERE j.id = ? AND j.organization_id = ?""",
            (job_id, organization_id),
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def list_jobs(
    user_id: str,
    page: int = 1,
    limit: int = 50,
    status: str | None = None,
    lot_id: str | None = None,
) -> tuple[list[dict], int]:
    async for db in get_db():
        where = "WHERE j.user_id = ?"
        params: list[object] = [user_id]
        if status:
            where += " AND j.status = ?"
            params.append(status)
        if lot_id:
            where += " AND j.lot_id = ?"
            params.append(lot_id)
        cursor = await db.execute(
            f"SELECT COUNT(*) FROM jobs j {where}",
            tuple(params),
        )
        total = (await cursor.fetchone())[0]
        offset = (page - 1) * limit
        cursor = await db.execute(
            f"""SELECT j.*, l.name AS lot_name, s.name AS site_name
                FROM jobs j
                LEFT JOIN lots l ON l.id = j.lot_id
                LEFT JOIN sites s ON s.id = j.site_id
                {where}
                ORDER BY j.updated_at DESC
                LIMIT ? OFFSET ?""",
            tuple(params + [limit, offset]),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(row) for row in rows], total


async def list_work_orders(
    organization_id: str,
    page: int = 1,
    limit: int = 50,
    site_id: Optional[str] = None,
    status: Optional[str] = None,
) -> tuple[list[dict], int]:
    async for db in get_db():
        where = "WHERE j.organization_id = ?"
        params: list[object] = [organization_id]
        if site_id:
            where += " AND j.site_id = ?"
            params.append(site_id)
        if status:
            where += " AND j.status = ?"
            params.append(status)
        cursor = await db.execute(f"SELECT COUNT(*) FROM jobs j {where}", tuple(params))
        total = (await cursor.fetchone())[0]
        offset = (page - 1) * limit
        cursor = await db.execute(
            f"""SELECT j.*, l.name AS lot_name, s.name AS site_name
                FROM jobs j
                LEFT JOIN lots l ON l.id = j.lot_id
                LEFT JOIN sites s ON s.id = j.site_id
                {where}
                ORDER BY COALESCE(j.scheduled_start_at, j.date) DESC
                LIMIT ? OFFSET ?""",
            tuple(params + [limit, offset]),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(row) for row in rows], total


async def count_jobs(user_id: str) -> int:
    async for db in get_db():
        cursor = await db.execute("SELECT COUNT(*) FROM jobs WHERE user_id = ?", (user_id,))
        return (await cursor.fetchone())[0]


async def get_priority_job(user_id: str) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute(
            """
            SELECT j.*, l.name AS lot_name, s.name AS site_name
            FROM jobs j
            LEFT JOIN lots l ON l.id = j.lot_id AND l.user_id = j.user_id
            LEFT JOIN sites s ON s.id = j.site_id
            WHERE j.user_id = ? AND j.status IN ('in_progress', 'assigned', 'scheduled', 'pending')
            ORDER BY
                CASE j.status
                    WHEN 'in_progress' THEN 0
                    WHEN 'assigned' THEN 1
                    WHEN 'scheduled' THEN 2
                    ELSE 3
                END,
                COALESCE(j.scheduled_start_at, j.date, j.updated_at) ASC
            LIMIT 1
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def _lot_context(db, lot_id: str) -> dict:
    cursor = await db.execute(
        "SELECT user_id, organization_id FROM lots WHERE id = ?",
        (lot_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return {}
    cursor = await db.execute("SELECT id FROM sites WHERE lot_id = ?", (lot_id,))
    site = await cursor.fetchone()
    return {
        "user_id": row["user_id"],
        "organization_id": row["organization_id"],
        "site_id": site["id"] if site else None,
    }


async def create_job_atomic(
    user_id: str,
    lot_id: str,
    date: str,
    max_jobs: int,
    time_preference: str = "morning",
    recurring_schedule_id: Optional[str] = None,
) -> Optional[dict]:
    job_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        await db.execute("BEGIN IMMEDIATE")
        try:
            cursor = await db.execute("SELECT COUNT(*) FROM jobs WHERE user_id = ?", (user_id,))
            count = (await cursor.fetchone())[0]
            if count >= max_jobs:
                await db.execute("ROLLBACK")
                return None
            ctx = await _lot_context(db, lot_id)
            await db.execute(
                """INSERT INTO jobs
                   (id, user_id, organization_id, site_id, lot_id, recurring_schedule_id, date, status, time_preference, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
                (job_id, user_id, ctx.get("organization_id"), ctx.get("site_id"), lot_id, recurring_schedule_id, date, time_preference, now, now),
            )
            await db.execute("COMMIT")
        except Exception:
            await db.execute("ROLLBACK")
            raise
    return await get_job(user_id, job_id)


async def create_job(
    user_id: str,
    lot_id: str,
    date: str,
    time_preference: str = "morning",
    recurring_schedule_id: Optional[str] = None,
) -> dict:
    job = await create_job_atomic(
        user_id,
        lot_id,
        date,
        max_jobs=10**9,
        time_preference=time_preference,
        recurring_schedule_id=recurring_schedule_id,
    )
    return job or {}


async def create_work_order(
    organization_id: str,
    user_id: str,
    site_id: str,
    title: str,
    date: str,
    status: str,
    time_preference: str = "morning",
    quote_id: Optional[str] = None,
    lot_id: Optional[str] = None,
    scheduled_start_at: Optional[str] = None,
    scheduled_end_at: Optional[str] = None,
    assigned_robot_id: Optional[str] = None,
    assigned_user_id: Optional[str] = None,
    notes: str = "",
) -> dict:
    job_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        final_lot_id = lot_id
        if not final_lot_id:
            cursor = await db.execute("SELECT lot_id FROM sites WHERE id = ?", (site_id,))
            row = await cursor.fetchone()
            final_lot_id = row["lot_id"] if row else None
        if not final_lot_id:
            raise ValueError("Site must be linked to a design lot before creating a work order")
        await db.execute(
            """INSERT INTO jobs
               (id, user_id, organization_id, site_id, lot_id, quote_id, date, status, time_preference,
                scheduled_start_at, scheduled_end_at, assigned_user_id, robot_id, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job_id,
                user_id,
                organization_id,
                site_id,
                final_lot_id,
                quote_id,
                date,
                status,
                time_preference,
                scheduled_start_at,
                scheduled_end_at,
                assigned_user_id,
                assigned_robot_id,
                notes or title,
                now,
                now,
            ),
        )
        await db.commit()
    return await get_job_by_org(organization_id, job_id) or {}


_VALID_TRANSITIONS = {
    "draft": {"quoted", "scheduled", "cancelled"},
    "quoted": {"scheduled", "cancelled"},
    "scheduled": {"assigned", "in_progress", "cancelled", "pending"},
    "assigned": {"in_progress", "cancelled"},
    "pending": {"in_progress", "completed", "cancelled", "assigned", "scheduled"},
    "in_progress": {"completed", "verified", "cancelled"},
    "completed": {"verified"},
    "verified": set(),
    "cancelled": set(),
}


async def update_job(
    user_id: str,
    job_id: str,
    status: Optional[str] = None,
    date: Optional[str] = None,
    *,
    scheduled_start_at: Optional[str] = None,
    scheduled_end_at: Optional[str] = None,
    assigned_user_id: Optional[str] = None,
    robot_id: Optional[str] = None,
    notes: Optional[str] = None,
    verified_at: Optional[str] = None,
) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ? AND user_id = ?", (job_id, user_id))
        existing = await cursor.fetchone()
        if not existing:
            return None

    fields = []
    values: list[object] = []
    now = _now()
    if status is not None:
        current_status = existing["status"]
        allowed = _VALID_TRANSITIONS.get(current_status, set())
        if status != current_status and status not in allowed:
            return False
        fields.append("status = ?")
        values.append(status)
        if status == "in_progress" and not existing["started_at"]:
            fields.append("started_at = ?")
            values.append(now)
        if status == "completed" and not existing["completed_at"]:
            fields.append("completed_at = ?")
            values.append(now)
        if status == "verified":
            fields.append("verified_at = ?")
            values.append(verified_at or now)
    if date is not None:
        fields.append("date = ?")
        values.append(date)
    if scheduled_start_at is not None:
        fields.append("scheduled_start_at = ?")
        values.append(scheduled_start_at)
    if scheduled_end_at is not None:
        fields.append("scheduled_end_at = ?")
        values.append(scheduled_end_at)
    if assigned_user_id is not None:
        fields.append("assigned_user_id = ?")
        values.append(assigned_user_id)
    if robot_id is not None:
        fields.append("robot_id = ?")
        values.append(robot_id)
    if notes is not None:
        fields.append("notes = ?")
        values.append(notes)
    if verified_at is not None and status is None:
        fields.append("verified_at = ?")
        values.append(verified_at)
    if not fields:
        return _row_to_dict(existing)
    fields.append("updated_at = ?")
    values.append(now)
    values.extend([job_id, user_id])
    async for db in get_db():
        await db.execute(
            f"UPDATE jobs SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            tuple(values),
        )
        await db.commit()
    return await get_job(user_id, job_id)


async def update_work_order(
    organization_id: str,
    job_id: str,
    **kwargs,
) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute("SELECT user_id FROM jobs WHERE id = ? AND organization_id = ?", (job_id, organization_id))
        row = await cursor.fetchone()
        if not row:
            return None
    return await update_job(row["user_id"], job_id, **kwargs)


async def delete_job(user_id: str, job_id: str) -> bool:
    async for db in get_db():
        cursor = await db.execute("DELETE FROM jobs WHERE id = ? AND user_id = ?", (job_id, user_id))
        await db.commit()
        return cursor.rowcount > 0


async def create_job_run(
    organization_id: str,
    job_id: str,
    site_id: Optional[str],
    robot_id: Optional[str],
    technician_user_id: Optional[str],
    notes: str = "",
) -> dict:
    run_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        await db.execute(
            """INSERT INTO job_runs
               (id, organization_id, site_id, job_id, robot_id, technician_user_id, status, notes, started_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'started', ?, ?, ?, ?)""",
            (run_id, organization_id, site_id, job_id, robot_id, technician_user_id, notes, now, now, now),
        )
        await db.commit()
    return await get_job_run(organization_id, run_id) or {}


async def get_job_run(organization_id: str, run_id: str) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM job_runs WHERE organization_id = ? AND id = ?",
            (organization_id, run_id),
        )
        row = await cursor.fetchone()
        return _job_run_to_dict(row) if row else None


async def list_job_runs(organization_id: str, job_id: Optional[str] = None) -> list[dict]:
    async for db in get_db():
        where = "WHERE organization_id = ?"
        params: list[object] = [organization_id]
        if job_id:
            where += " AND job_id = ?"
            params.append(job_id)
        cursor = await db.execute(
            f"SELECT * FROM job_runs {where} ORDER BY created_at DESC",
            tuple(params),
        )
        rows = await cursor.fetchall()
        return [_job_run_to_dict(row) for row in rows]


async def update_job_run(
    organization_id: str,
    run_id: str,
    *,
    status: Optional[str] = None,
    notes: Optional[str] = None,
    actual_paint_gallons: Optional[float] = None,
    telemetry_summary: Optional[dict] = None,
) -> Optional[dict]:
    fields = []
    values: list[object] = []
    now = _now()
    if status is not None:
        fields.append("status = ?")
        values.append(status)
        if status == "completed":
            fields.append("completed_at = ?")
            values.append(now)
    if notes is not None:
        fields.append("notes = ?")
        values.append(notes)
    if actual_paint_gallons is not None:
        fields.append("actual_paint_gallons = ?")
        values.append(actual_paint_gallons)
    if telemetry_summary is not None:
        fields.append("telemetry_summary = ?")
        values.append(json.dumps(telemetry_summary))
    if not fields:
        return await get_job_run(organization_id, run_id)
    fields.append("updated_at = ?")
    values.append(now)
    values.extend([organization_id, run_id])
    async for db in get_db():
        await db.execute(
            f"UPDATE job_runs SET {', '.join(fields)} WHERE organization_id = ? AND id = ?",
            tuple(values),
        )
        await db.commit()
    return await get_job_run(organization_id, run_id)
