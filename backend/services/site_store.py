"""Site portfolio persistence built on top of organization-owned lot designs."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from ..database import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row) -> dict:
    data = dict(row)
    site = {
        "id": data["id"],
        "organization_id": data["organization_id"],
        "name": data["name"],
        "address": data.get("address") or "",
        "notes": data.get("notes") or "",
        "customer_type": data.get("customer_type") or "mixed",
        "status": data.get("status") or "active",
        "lot_id": data.get("lot_id"),
        "created_at": data["created_at"],
        "updated_at": data["updated_at"],
        "design_name": data.get("design_name"),
        "center": None,
        "zoom": data.get("zoom"),
    }
    if data.get("center_lat") is not None and data.get("center_lng") is not None:
        site["center"] = {"lat": data["center_lat"], "lng": data["center_lng"]}
    return site


async def list_sites(organization_id: str, page: int = 1, limit: int = 50) -> tuple[list[dict], int]:
    async for db in get_db():
        cursor = await db.execute(
            "SELECT COUNT(*) FROM sites WHERE organization_id = ?",
            (organization_id,),
        )
        total = (await cursor.fetchone())[0]
        offset = (page - 1) * limit
        cursor = await db.execute(
            """SELECT s.*, l.name AS design_name, l.center_lat, l.center_lng, l.zoom
               FROM sites s
               LEFT JOIN lots l ON l.id = s.lot_id
               WHERE s.organization_id = ?
               ORDER BY s.updated_at DESC
               LIMIT ? OFFSET ?""",
            (organization_id, limit, offset),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(row) for row in rows], total


async def get_site(organization_id: str, site_id: str) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute(
            """SELECT s.*, l.name AS design_name, l.center_lat, l.center_lng, l.zoom
               FROM sites s
               LEFT JOIN lots l ON l.id = s.lot_id
               WHERE s.organization_id = ? AND s.id = ?""",
            (organization_id, site_id),
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def create_site(
    organization_id: str,
    created_by_user_id: str,
    name: str,
    address: str = "",
    notes: str = "",
    customer_type: str = "mixed",
    lot_id: Optional[str] = None,
) -> dict:
    site_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        await db.execute(
            """INSERT INTO sites
               (id, organization_id, lot_id, name, address, notes, customer_type, created_by_user_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (site_id, organization_id, lot_id, name, address, notes, customer_type, created_by_user_id, now, now),
        )
        await db.commit()
    return await get_site(organization_id, site_id) or {}


async def update_site(
    organization_id: str,
    site_id: str,
    *,
    name: Optional[str] = None,
    address: Optional[str] = None,
    notes: Optional[str] = None,
    customer_type: Optional[str] = None,
    status: Optional[str] = None,
    lot_id: Optional[str] = None,
) -> Optional[dict]:
    fields = []
    values: list[object] = []
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if address is not None:
        fields.append("address = ?")
        values.append(address)
    if notes is not None:
        fields.append("notes = ?")
        values.append(notes)
    if customer_type is not None:
        fields.append("customer_type = ?")
        values.append(customer_type)
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if lot_id is not None:
        fields.append("lot_id = ?")
        values.append(lot_id)
    if not fields:
        return await get_site(organization_id, site_id)
    fields.append("updated_at = ?")
    values.append(_now())
    values.extend([organization_id, site_id])
    async for db in get_db():
        await db.execute(
            f"UPDATE sites SET {', '.join(fields)} WHERE organization_id = ? AND id = ?",
            tuple(values),
        )
        await db.commit()
    return await get_site(organization_id, site_id)


async def delete_site(organization_id: str, site_id: str) -> bool:
    async for db in get_db():
        cursor = await db.execute(
            "UPDATE sites SET status = 'archived', updated_at = ? WHERE organization_id = ? AND id = ?",
            (_now(), organization_id, site_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def ensure_site_for_lot(organization_id: str, created_by_user_id: str, lot: dict) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute(
            "SELECT id FROM sites WHERE lot_id = ?",
            (lot["id"],),
        )
        row = await cursor.fetchone()
        if row:
            return await get_site(organization_id, row["id"])
    return await create_site(
        organization_id=organization_id,
        created_by_user_id=created_by_user_id,
        name=lot["name"],
        lot_id=lot["id"],
    )


async def get_site_by_lot(lot_id: str) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute(
            """SELECT s.*, l.name AS design_name, l.center_lat, l.center_lng, l.zoom
               FROM sites s
               LEFT JOIN lots l ON l.id = s.lot_id
               WHERE s.lot_id = ?""",
            (lot_id,),
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None
