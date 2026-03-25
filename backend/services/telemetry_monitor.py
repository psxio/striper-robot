"""Background telemetry monitoring: offline robot alerts and low paint alerts.

Runs every 10 minutes. Checks for:
- Robots with no heartbeat in >2 hours → send_connectivity_lost_email
- Robots with latest paint_level_pct < 15% → send_low_paint_alert_email

Uses in-memory dedup sets to avoid spamming the same alert on every tick.
The sets reset on process restart (acceptable: one extra alert per restart).
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from ..database import get_db
from . import email_service

logger = logging.getLogger("strype.telemetry_monitor")

# In-memory dedup: robot IDs that have already been alerted this cycle
_alerted_offline: set[str] = set()
_alerted_low_paint: set[str] = set()

OFFLINE_THRESHOLD_HOURS = 2
LOW_PAINT_THRESHOLD_PCT = 15
MONITOR_INTERVAL_SECONDS = 600  # 10 minutes


async def _resolve_alert_recipients(robot_id: str) -> list[dict]:
    """Resolve the email addresses to notify for a given robot.

    Resolution chain: robot → robot_claims (org) → memberships (owner/admin) → users (email).
    Fallback: robot → robot_assignments (user) → users (email).
    """
    async for db in get_db():
        # Primary path: claimed robots → org owners/admins
        cursor = await db.execute(
            """SELECT DISTINCT u.email, u.name
               FROM robot_claims rc
               JOIN memberships m ON m.organization_id = rc.organization_id AND m.status = 'active'
               JOIN users u ON u.id = m.user_id
               WHERE rc.robot_id = ? AND rc.status = 'claimed'
                 AND m.role IN ('owner', 'admin')""",
            (robot_id,),
        )
        rows = await cursor.fetchall()
        if rows:
            return [{"email": r["email"], "name": r["name"]} for r in rows]

        # Fallback: assigned robots → assigned user
        cursor = await db.execute(
            """SELECT u.email, u.name
               FROM robot_assignments ra
               JOIN users u ON u.id = ra.user_id
               WHERE ra.robot_id = ? AND ra.status != 'returned'
               ORDER BY ra.created_at DESC LIMIT 1""",
            (robot_id,),
        )
        row = await cursor.fetchone()
        if row:
            return [{"email": row["email"], "name": row["name"]}]

        return []


async def check_offline_robots(threshold_hours: int = OFFLINE_THRESHOLD_HOURS) -> int:
    """Check for robots that haven't sent a heartbeat recently. Returns count of alerts sent."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=threshold_hours)).isoformat()
    alerts_sent = 0

    async for db in get_db():
        cursor = await db.execute(
            """SELECT id, serial_number, last_seen_at
               FROM robots
               WHERE last_seen_at IS NOT NULL AND last_seen_at < ?""",
            (cutoff,),
        )
        offline_robots = await cursor.fetchall()

    for robot in offline_robots:
        robot_id = robot["id"]

        # Skip if already alerted
        if robot_id in _alerted_offline:
            continue

        recipients = await _resolve_alert_recipients(robot_id)
        for r in recipients:
            await email_service.send_connectivity_lost_email(
                r["email"], robot["serial_number"], robot["last_seen_at"],
            )
        if recipients:
            _alerted_offline.add(robot_id)
            alerts_sent += 1
            logger.info("Offline alert sent for robot %s (%s)", robot["serial_number"], robot_id)

    # Clear robots that have come back online
    async for db in get_db():
        for robot_id in list(_alerted_offline):
            cursor = await db.execute(
                "SELECT last_seen_at FROM robots WHERE id = ?", (robot_id,)
            )
            row = await cursor.fetchone()
            if row and row["last_seen_at"] and row["last_seen_at"] >= cutoff:
                _alerted_offline.discard(robot_id)

    return alerts_sent


async def check_low_paint(threshold_pct: int = LOW_PAINT_THRESHOLD_PCT) -> int:
    """Check for robots with low paint levels. Returns count of alerts sent."""
    alerts_sent = 0

    async for db in get_db():
        # Get latest telemetry per robot with low paint
        cursor = await db.execute(
            """SELECT r.id, r.serial_number, t.paint_level_pct
               FROM robots r
               JOIN robot_telemetry t ON t.robot_id = r.id
               WHERE t.paint_level_pct IS NOT NULL
                 AND t.paint_level_pct < ?
                 AND t.created_at = (
                     SELECT MAX(t2.created_at)
                     FROM robot_telemetry t2
                     WHERE t2.robot_id = r.id
                 )""",
            (threshold_pct,),
        )
        low_paint_robots = await cursor.fetchall()

    for robot in low_paint_robots:
        robot_id = robot["id"]

        # Skip if already alerted for this level
        if robot_id in _alerted_low_paint:
            continue

        recipients = await _resolve_alert_recipients(robot_id)
        for r in recipients:
            await email_service.send_low_paint_alert_email(
                r["email"], robot["serial_number"], robot["paint_level_pct"],
            )
        if recipients:
            _alerted_low_paint.add(robot_id)
            alerts_sent += 1
            logger.info(
                "Low paint alert sent for robot %s (%d%%)",
                robot["serial_number"], robot["paint_level_pct"],
            )

    # Clear robots that have been refilled (paint above threshold)
    async for db in get_db():
        for robot_id in list(_alerted_low_paint):
            cursor = await db.execute(
                """SELECT paint_level_pct FROM robot_telemetry
                   WHERE robot_id = ? ORDER BY created_at DESC LIMIT 1""",
                (robot_id,),
            )
            row = await cursor.fetchone()
            if row and row["paint_level_pct"] is not None and row["paint_level_pct"] >= threshold_pct:
                _alerted_low_paint.discard(robot_id)

    return alerts_sent


async def run_telemetry_monitor_loop() -> None:
    """Run the telemetry monitoring loop every 10 minutes."""
    logger.info("Telemetry monitor loop started (interval=%ds)", MONITOR_INTERVAL_SECONDS)
    while True:
        try:
            await asyncio.sleep(MONITOR_INTERVAL_SECONDS)
            offline_count = await check_offline_robots()
            paint_count = await check_low_paint()
            if offline_count or paint_count:
                logger.info(
                    "Telemetry monitor tick: %d offline alert(s), %d low paint alert(s)",
                    offline_count, paint_count,
                )
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Telemetry monitor tick failed")
