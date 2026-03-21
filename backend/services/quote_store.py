"""Quote persistence and generation helpers."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from ..database import get_db
from . import estimate_store


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_quote(
    organization_id: str,
    site_id: str,
    created_by_user_id: str,
    title: str,
    cadence: str,
    scope: str,
    notes: str,
    proposed_price: Optional[float],
    features: list[dict],
) -> dict:
    estimate = estimate_store.calculate_estimate(features)
    quote_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        await db.execute(
            """INSERT INTO quotes
               (id, organization_id, site_id, created_by_user_id, title, cadence, scope, notes, status,
                proposed_price, total_line_length_ft, paint_gallons, estimated_runtime_min, estimated_cost,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?)""",
            (
                quote_id,
                organization_id,
                site_id,
                created_by_user_id,
                title,
                cadence,
                scope,
                notes,
                proposed_price if proposed_price is not None else estimate["estimated_cost"],
                estimate["total_line_length_ft"],
                estimate["paint_gallons"],
                estimate["estimated_runtime_min"],
                estimate["estimated_cost"],
                now,
                now,
            ),
        )
        await db.commit()
    return await get_quote(organization_id, quote_id) or {}


async def list_quotes(organization_id: str, site_id: Optional[str] = None) -> list[dict]:
    async for db in get_db():
        where = "WHERE q.organization_id = ?"
        params: list[object] = [organization_id]
        if site_id:
            where += " AND q.site_id = ?"
            params.append(site_id)
        cursor = await db.execute(
            f"""SELECT q.*, s.name AS site_name
                FROM quotes q
                JOIN sites s ON s.id = q.site_id
                {where}
                ORDER BY q.updated_at DESC""",
            tuple(params),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_quote(organization_id: str, quote_id: str) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute(
            """SELECT q.*, s.name AS site_name
               FROM quotes q
               JOIN sites s ON s.id = q.site_id
               WHERE q.organization_id = ? AND q.id = ?""",
            (organization_id, quote_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_quote(
    organization_id: str,
    quote_id: str,
    *,
    title: Optional[str] = None,
    cadence: Optional[str] = None,
    scope: Optional[str] = None,
    notes: Optional[str] = None,
    proposed_price: Optional[float] = None,
    status: Optional[str] = None,
) -> Optional[dict]:
    fields = []
    values: list[object] = []
    if title is not None:
        fields.append("title = ?")
        values.append(title)
    if cadence is not None:
        fields.append("cadence = ?")
        values.append(cadence)
    if scope is not None:
        fields.append("scope = ?")
        values.append(scope)
    if notes is not None:
        fields.append("notes = ?")
        values.append(notes)
    if proposed_price is not None:
        fields.append("proposed_price = ?")
        values.append(proposed_price)
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if not fields:
        return await get_quote(organization_id, quote_id)
    fields.append("updated_at = ?")
    values.append(_now())
    values.extend([organization_id, quote_id])
    async for db in get_db():
        await db.execute(
            f"UPDATE quotes SET {', '.join(fields)} WHERE organization_id = ? AND id = ?",
            tuple(values),
        )
        await db.commit()
    return await get_quote(organization_id, quote_id)
