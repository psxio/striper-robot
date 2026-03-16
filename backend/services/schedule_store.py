"""Recurring schedule persistence layer using aiosqlite with tenant isolation."""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from ..database import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def calculate_next_run(
    frequency: str,
    day_of_week: Optional[int] = None,
    day_of_month: Optional[int] = None,
) -> str:
    """Calculate the next run date from today.

    For weekly/biweekly: find the next occurrence of day_of_week (0=Mon..6=Sun).
    For monthly: find the next occurrence of day_of_month (1-28).
    Returns ISO date string (YYYY-MM-DD).
    """
    today = datetime.now(timezone.utc).date()

    if frequency in ("weekly", "biweekly"):
        # day_of_week: 0=Mon..6=Sun (matches Python's weekday())
        current_weekday = today.weekday()
        days_ahead = day_of_week - current_weekday
        if days_ahead <= 0:
            # Target day already happened this week (or is today), go to next week
            days_ahead += 7
        if frequency == "biweekly" and days_ahead <= 7:
            # For biweekly, if the next occurrence is within a week, push it
            # out another week (so it's 8-14 days away)
            days_ahead += 7
        next_date = today + timedelta(days=days_ahead)
        return next_date.isoformat()

    if frequency == "monthly":
        # Find the next occurrence of day_of_month
        if today.day < day_of_month:
            # Still upcoming this month
            next_date = today.replace(day=day_of_month)
        else:
            # Already passed this month, go to next month
            if today.month == 12:
                next_date = today.replace(year=today.year + 1, month=1, day=day_of_month)
            else:
                next_date = today.replace(month=today.month + 1, day=day_of_month)
        return next_date.isoformat()

    raise ValueError(f"Unknown frequency: {frequency}")


async def create_schedule(
    user_id: str,
    lot_id: str,
    frequency: str,
    day_of_week: Optional[int] = None,
    day_of_month: Optional[int] = None,
    time_preference: str = "morning",
) -> dict:
    """Create a new recurring schedule and return its dict representation."""
    schedule_id = str(uuid.uuid4())
    now = _now()
    next_run = calculate_next_run(frequency, day_of_week, day_of_month)

    async for db in get_db():
        await db.execute(
            """INSERT INTO recurring_schedules
               (id, user_id, lot_id, frequency, day_of_week, day_of_month,
                time_preference, active, next_run, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)""",
            (schedule_id, user_id, lot_id, frequency, day_of_week,
             day_of_month, time_preference, next_run, now, now),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM recurring_schedules WHERE id = ?", (schedule_id,)
        )
        row = await cursor.fetchone()
        return dict(row)


async def list_schedules(
    user_id: str, page: int = 1, limit: int = 50
) -> tuple[list[dict], int]:
    """Return paginated active schedules for a given user."""
    async for db in get_db():
        cursor = await db.execute(
            "SELECT COUNT(*) FROM recurring_schedules WHERE user_id = ? AND active = 1",
            (user_id,),
        )
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * limit
        cursor = await db.execute(
            """SELECT * FROM recurring_schedules
               WHERE user_id = ? AND active = 1
               ORDER BY next_run ASC
               LIMIT ? OFFSET ?""",
            (user_id, limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows], total


async def get_schedule(user_id: str, schedule_id: str) -> Optional[dict]:
    """Get a single schedule by ID, scoped to the given user."""
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM recurring_schedules WHERE id = ? AND user_id = ?",
            (schedule_id, user_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_schedule(
    user_id: str,
    schedule_id: str,
    frequency: Optional[str] = None,
    day_of_week: Optional[int] = None,
    day_of_month: Optional[int] = None,
    time_preference: Optional[str] = None,
    active: Optional[int] = None,
) -> Optional[dict]:
    """Partial update of a schedule. Recalculates next_run if frequency or day changes.

    Returns updated dict or None if not found.
    """
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM recurring_schedules WHERE id = ? AND user_id = ?",
            (schedule_id, user_id),
        )
        existing = await cursor.fetchone()
        if not existing:
            return None

    existing_dict = dict(existing)
    fields: list[str] = []
    values: list[object] = []

    recalc_needed = False

    if frequency is not None:
        fields.append("frequency = ?")
        values.append(frequency)
        recalc_needed = True

    if day_of_week is not None:
        fields.append("day_of_week = ?")
        values.append(day_of_week)
        recalc_needed = True

    if day_of_month is not None:
        fields.append("day_of_month = ?")
        values.append(day_of_month)
        recalc_needed = True

    if time_preference is not None:
        fields.append("time_preference = ?")
        values.append(time_preference)

    if active is not None:
        fields.append("active = ?")
        values.append(active)

    # Recalculate next_run if frequency or day fields changed
    if recalc_needed:
        new_freq = frequency if frequency is not None else existing_dict["frequency"]
        new_dow = day_of_week if day_of_week is not None else existing_dict["day_of_week"]
        new_dom = day_of_month if day_of_month is not None else existing_dict["day_of_month"]
        next_run = calculate_next_run(new_freq, new_dow, new_dom)
        fields.append("next_run = ?")
        values.append(next_run)

    if not fields:
        return existing_dict

    fields.append("updated_at = ?")
    values.append(_now())
    values.append(schedule_id)
    values.append(user_id)

    async for db in get_db():
        await db.execute(
            f"UPDATE recurring_schedules SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            tuple(values),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM recurring_schedules WHERE id = ? AND user_id = ?",
            (schedule_id, user_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def delete_schedule(user_id: str, schedule_id: str) -> bool:
    """Soft-delete a schedule by setting active=0. Returns True if found."""
    async for db in get_db():
        cursor = await db.execute(
            "UPDATE recurring_schedules SET active = 0, updated_at = ? WHERE id = ? AND user_id = ? AND active = 1",
            (_now(), schedule_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_due_schedules() -> list[dict]:
    """Return all active schedules where next_run <= today (date comparison)."""
    today_str = datetime.now(timezone.utc).date().isoformat()
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM recurring_schedules WHERE active = 1 AND next_run <= ?",
            (today_str,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def advance_schedule(schedule_id: str) -> Optional[dict]:
    """Calculate and set the next next_run based on the schedule's frequency.

    Returns updated dict or None if not found.
    """
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM recurring_schedules WHERE id = ?", (schedule_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None

    schedule = dict(row)
    next_run = calculate_next_run(
        schedule["frequency"],
        schedule["day_of_week"],
        schedule["day_of_month"],
    )

    async for db in get_db():
        await db.execute(
            "UPDATE recurring_schedules SET next_run = ?, updated_at = ? WHERE id = ?",
            (next_run, _now(), schedule_id),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM recurring_schedules WHERE id = ?", (schedule_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def deactivate_lot_schedules(lot_id: str) -> None:
    """Set active=0 for all schedules on a given lot. For when a lot is deleted."""
    async for db in get_db():
        await db.execute(
            "UPDATE recurring_schedules SET active = 0, updated_at = ? WHERE lot_id = ? AND active = 1",
            (_now(), lot_id),
        )
        await db.commit()
