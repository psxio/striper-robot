"""Organization-scoped audit logging helpers."""

import json
from datetime import datetime, timezone
from typing import Optional

from ..database import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def log_event(
    organization_id: str,
    action: str,
    *,
    actor_user_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    detail: Optional[dict] = None,
) -> None:
    async for db in get_db():
        await db.execute(
            """INSERT INTO organization_audit_logs
               (organization_id, actor_user_id, action, target_type, target_id, detail_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                organization_id,
                actor_user_id,
                action,
                target_type,
                target_id,
                json.dumps(detail or {}),
                _now(),
            ),
        )
        await db.commit()


async def list_events(organization_id: str, limit: int = 100) -> list[dict]:
    async for db in get_db():
        cursor = await db.execute(
            """SELECT * FROM organization_audit_logs
               WHERE organization_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (organization_id, limit),
        )
        rows = await cursor.fetchall()
        items = []
        for row in rows:
            data = dict(row)
            data["detail"] = json.loads(data.pop("detail_json", "{}") or "{}")
            items.append(data)
        return items
    return []
