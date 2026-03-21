"""Operational fleet, maintenance, and consumables persistence."""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..database import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_maintenance_event(
    robot_id: str,
    organization_id: Optional[str],
    created_by_user_id: str,
    event_type: str,
    summary: str,
    details: str = "",
    completed_at: Optional[str] = None,
) -> dict:
    event_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        await db.execute(
            """INSERT INTO maintenance_events
               (id, robot_id, organization_id, event_type, summary, details, completed_at, created_by_user_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id, robot_id, organization_id, event_type, summary, details, completed_at, created_by_user_id, now),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM maintenance_events WHERE id = ?", (event_id,))
        row = await cursor.fetchone()
        return dict(row) if row else {}


async def list_maintenance_events(robot_id: Optional[str] = None) -> list[dict]:
    async for db in get_db():
        where = ""
        params: list[object] = []
        if robot_id:
            where = "WHERE robot_id = ?"
            params.append(robot_id)
        cursor = await db.execute(
            f"SELECT * FROM maintenance_events {where} ORDER BY created_at DESC",
            tuple(params),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def create_service_checklist(
    robot_id: str,
    organization_id: Optional[str],
    created_by_user_id: str,
    name: str,
    checklist_items: list[str],
    completed_at: Optional[str] = None,
) -> dict:
    checklist_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        await db.execute(
            """INSERT INTO service_checklists
               (id, robot_id, organization_id, name, checklist_json, completed_at, created_by_user_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (checklist_id, robot_id, organization_id, name, json.dumps(checklist_items), completed_at, created_by_user_id, now),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM service_checklists WHERE id = ?", (checklist_id,))
        row = await cursor.fetchone()
        data = dict(row) if row else {}
        data["checklist_items"] = json.loads(data.pop("checklist_json", "[]"))
        return data


async def list_service_checklists(robot_id: Optional[str] = None) -> list[dict]:
    async for db in get_db():
        where = ""
        params: list[object] = []
        if robot_id:
            where = "WHERE robot_id = ?"
            params.append(robot_id)
        cursor = await db.execute(
            f"SELECT * FROM service_checklists {where} ORDER BY created_at DESC",
            tuple(params),
        )
        rows = await cursor.fetchall()
        items = []
        for row in rows:
            data = dict(row)
            data["checklist_items"] = json.loads(data.pop("checklist_json", "[]"))
            items.append(data)
        return items


async def create_consumable_item(
    organization_id: str,
    sku: str,
    name: str,
    unit: str,
    on_hand: float,
    reorder_level: float,
) -> dict:
    item_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        await db.execute(
            """INSERT INTO consumables_inventory
               (id, organization_id, sku, name, unit, on_hand, reorder_level, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (item_id, organization_id, sku, name, unit, on_hand, reorder_level, now, now),
        )
        await db.commit()
    return await get_consumable_item(organization_id, item_id) or {}


async def get_consumable_item(organization_id: str, item_id: str) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM consumables_inventory WHERE organization_id = ? AND id = ?",
            (organization_id, item_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def list_consumable_items(organization_id: str) -> list[dict]:
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM consumables_inventory WHERE organization_id = ? ORDER BY updated_at DESC",
            (organization_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_consumable_item(
    organization_id: str,
    item_id: str,
    *,
    name: Optional[str] = None,
    unit: Optional[str] = None,
    on_hand: Optional[float] = None,
    reorder_level: Optional[float] = None,
) -> Optional[dict]:
    fields = []
    values: list[object] = []
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if unit is not None:
        fields.append("unit = ?")
        values.append(unit)
    if on_hand is not None:
        fields.append("on_hand = ?")
        values.append(on_hand)
    if reorder_level is not None:
        fields.append("reorder_level = ?")
        values.append(reorder_level)
    if not fields:
        return await get_consumable_item(organization_id, item_id)
    fields.append("updated_at = ?")
    values.append(_now())
    values.extend([organization_id, item_id])
    async for db in get_db():
        await db.execute(
            f"UPDATE consumables_inventory SET {', '.join(fields)} WHERE organization_id = ? AND id = ?",
            tuple(values),
        )
        await db.commit()
    return await get_consumable_item(organization_id, item_id)


async def create_consumable_usage(
    organization_id: str,
    consumable_item_id: str,
    created_by_user_id: str,
    quantity: float,
    *,
    job_run_id: Optional[str] = None,
    notes: str = "",
) -> dict:
    usage_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        await db.execute("BEGIN IMMEDIATE")
        try:
            cursor = await db.execute(
                "SELECT on_hand FROM consumables_inventory WHERE organization_id = ? AND id = ?",
                (organization_id, consumable_item_id),
            )
            row = await cursor.fetchone()
            if not row:
                await db.execute("ROLLBACK")
                return {}
            await db.execute(
                """INSERT INTO consumable_usage
                   (id, organization_id, consumable_item_id, job_run_id, quantity, notes, created_by_user_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (usage_id, organization_id, consumable_item_id, job_run_id, quantity, notes, created_by_user_id, now),
            )
            await db.execute(
                "UPDATE consumables_inventory SET on_hand = ?, updated_at = ? WHERE organization_id = ? AND id = ?",
                (max((row["on_hand"] or 0) - quantity, 0), now, organization_id, consumable_item_id),
            )
            await db.execute("COMMIT")
        except Exception:
            await db.execute("ROLLBACK")
            raise
        cursor = await db.execute("SELECT * FROM consumable_usage WHERE id = ?", (usage_id,))
        row = await cursor.fetchone()
        return dict(row) if row else {}


async def list_consumable_usage(
    organization_id: str,
    *,
    job_run_id: Optional[str] = None,
) -> list[dict]:
    async for db in get_db():
        where = "WHERE organization_id = ?"
        params: list[object] = [organization_id]
        if job_run_id:
            where += " AND job_run_id = ?"
            params.append(job_run_id)
        cursor = await db.execute(
            f"SELECT * FROM consumable_usage {where} ORDER BY created_at DESC",
            tuple(params),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
