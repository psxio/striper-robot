"""Lot persistence layer using aiosqlite with tenant isolation."""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..database import get_db
from ..models.schemas import LotCreate, LotUpdate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row) -> dict:
    """Convert a DB row to a frontend-shaped dict."""
    d = dict(row)
    return {
        "id": d["id"],
        "name": d["name"],
        "center": {"lat": d["center_lat"], "lng": d["center_lng"]},
        "zoom": d["zoom"],
        "features": json.loads(d["features"]) if d["features"] else [],
        "created": d["created_at"],
        "modified": d["updated_at"],
    }


async def list_lots(user_id: str, page: int = 1, limit: int = 50) -> tuple[list[dict], int]:
    """Return paginated lots for a given user."""
    async for db in get_db():
        cursor = await db.execute(
            "SELECT COUNT(*) FROM lots WHERE user_id = ?", (user_id,)
        )
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * limit
        cursor = await db.execute(
            "SELECT * FROM lots WHERE user_id = ? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows], total


async def count_lots(user_id: str) -> int:
    """Return the total number of lots for a user."""
    async for db in get_db():
        cursor = await db.execute(
            "SELECT COUNT(*) FROM lots WHERE user_id = ?", (user_id,)
        )
        return (await cursor.fetchone())[0]


async def create_lot(user_id: str, data: LotCreate) -> dict:
    """Create a new lot and return its dict representation."""
    lot_id = str(uuid.uuid4())
    now = _now()
    features_json = json.dumps(data.features)
    async for db in get_db():
        await db.execute(
            """INSERT INTO lots (id, user_id, name, center_lat, center_lng, zoom, features, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (lot_id, user_id, data.name, data.center.lat, data.center.lng,
             data.zoom, features_json, now, now),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM lots WHERE id = ?", (lot_id,))
        row = await cursor.fetchone()
        return _row_to_dict(row)


async def get_lot(user_id: str, lot_id: str) -> Optional[dict]:
    """Get a single lot, scoped to the given user."""
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM lots WHERE id = ? AND user_id = ?",
            (lot_id, user_id),
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def update_lot(user_id: str, lot_id: str, data: LotUpdate) -> Optional[dict]:
    """Update non-None fields of a lot. Returns None if not found."""
    existing = await get_lot(user_id, lot_id)
    if not existing:
        return None

    fields: list[str] = []
    values: list[object] = []

    if data.name is not None:
        fields.append("name = ?")
        values.append(data.name)
    if data.center is not None:
        fields.append("center_lat = ?")
        values.append(data.center.lat)
        fields.append("center_lng = ?")
        values.append(data.center.lng)
    if data.zoom is not None:
        fields.append("zoom = ?")
        values.append(data.zoom)
    if data.features is not None:
        fields.append("features = ?")
        values.append(json.dumps(data.features))

    if not fields:
        return existing

    fields.append("updated_at = ?")
    values.append(_now())
    values.append(lot_id)
    values.append(user_id)

    async for db in get_db():
        await db.execute(
            f"UPDATE lots SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            tuple(values),
        )
        await db.commit()

    return await get_lot(user_id, lot_id)


async def delete_lot(user_id: str, lot_id: str) -> bool:
    """Delete a lot. Returns True if it existed and was deleted."""
    async for db in get_db():
        cursor = await db.execute(
            "DELETE FROM lots WHERE id = ? AND user_id = ?",
            (lot_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def duplicate_lot(user_id: str, lot_id: str) -> Optional[dict]:
    """Duplicate a lot with ' (Copy)' appended to the name."""
    original = await get_lot(user_id, lot_id)
    if not original:
        return None

    new_id = str(uuid.uuid4())
    now = _now()
    features_json = json.dumps(original["features"])
    new_name = original["name"] + " (Copy)"

    async for db in get_db():
        await db.execute(
            """INSERT INTO lots (id, user_id, name, center_lat, center_lng, zoom, features, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (new_id, user_id, new_name, original["center"]["lat"],
             original["center"]["lng"], original["zoom"], features_json, now, now),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM lots WHERE id = ?", (new_id,))
        row = await cursor.fetchone()
        return _row_to_dict(row)
