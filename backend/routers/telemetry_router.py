"""Robot telemetry endpoints: heartbeat ingestion and telemetry queries."""

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..auth import get_current_user, get_admin_user
from ..database import get_db
from ..models.schemas import TelemetryHeartbeat, TelemetryResponse
from ..rate_limit import limiter
from ..services import robot_store
from ..services.robot_store import _hash_api_key

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])
logger = logging.getLogger("strype.telemetry")


@router.post("/heartbeat")
@limiter.limit("60/minute")
async def heartbeat(request: Request, body: TelemetryHeartbeat):
    """Robot POSTs its current status. Authenticated via X-Robot-Key header."""
    api_key = request.headers.get("X-Robot-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-Robot-Key header")

    # Look up robot by hashed api_key
    key_hash = _hash_api_key(api_key)
    async for db in get_db():
        cursor = await db.execute(
            "SELECT id FROM robots WHERE api_key = ?", (key_hash,)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid robot key")

        robot_id = row["id"]
        now = datetime.now(timezone.utc).isoformat()

        # Insert telemetry record
        await db.execute(
            """INSERT INTO robot_telemetry
               (robot_id, battery_pct, lat, lng, state, paint_level_pct, error_code, rssi, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                robot_id,
                body.battery_pct,
                body.lat,
                body.lng,
                body.state,
                body.paint_level_pct,
                body.error_code,
                body.rssi,
                now,
            ),
        )

        # Update robot summary fields
        await db.execute(
            "UPDATE robots SET last_seen_at = ?, last_battery_pct = ?, last_state = ? WHERE id = ?",
            (now, body.battery_pct, body.state, robot_id),
        )
        await db.commit()

    logger.debug("Heartbeat received from robot %s", robot_id)
    return {"ok": True}


async def _check_robot_access(robot_id: str, user: dict) -> None:
    """Verify the user has access to the given robot. Admins can access any robot."""
    if user.get("is_admin"):
        return
    assignment = await robot_store.get_user_robot(user["id"])
    if not assignment or assignment["robot_id"] != robot_id:
        raise HTTPException(status_code=403, detail="Not authorized for this robot")


@router.get("/robot/{robot_id}/latest", response_model=TelemetryResponse)
async def get_latest_telemetry(
    robot_id: str, user: dict = Depends(get_current_user)
):
    """Get the most recent telemetry entry for a robot."""
    await _check_robot_access(robot_id, user)

    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM robot_telemetry WHERE robot_id = ? ORDER BY created_at DESC LIMIT 1",
            (robot_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No telemetry found")
        return dict(row)


@router.get("/robot/{robot_id}/history")
async def get_telemetry_history(
    robot_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    user: dict = Depends(get_current_user),
):
    """Get telemetry history for a robot within the given time window (max 7 days)."""
    await _check_robot_access(robot_id, user)

    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    async for db in get_db():
        cursor = await db.execute(
            """SELECT * FROM robot_telemetry
               WHERE robot_id = ? AND created_at >= ?
               ORDER BY created_at DESC
               LIMIT 1000""",
            (robot_id, since),
        )
        rows = await cursor.fetchall()
        return {"items": [dict(r) for r in rows], "robot_id": robot_id}
