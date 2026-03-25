"""Customer-facing robot endpoints — assignment status and connectivity."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from ..auth import get_current_user
from ..services import job_store, robot_store

router = APIRouter(prefix="/api/robots", tags=["robots"])
logger = logging.getLogger("strype.robots")

# Threshold for considering a robot "online" based on last telemetry heartbeat
CONNECTIVITY_TIMEOUT_MINUTES = 15


def _connectivity_status(last_seen_at: str | None) -> str:
    """Classify telemetry freshness for the customer status card."""
    if not last_seen_at:
        return "unknown"
    try:
        seen_at = datetime.fromisoformat(last_seen_at)
    except ValueError:
        return "unknown"
    if seen_at.tzinfo is None:
        seen_at = seen_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - seen_at <= timedelta(minutes=CONNECTIVITY_TIMEOUT_MINUTES):
        return "online"
    return "offline"


@router.get("")
async def get_my_robot(user: dict = Depends(get_current_user)):
    """Get the current user's assigned robot and assignment status."""
    assignment = await robot_store.get_user_robot(user["id"])
    claimed = []
    if user.get("active_organization_id"):
        claimed = await robot_store.list_claimed_robots(user["active_organization_id"])
    return {"assignment": assignment, "organization_robots": claimed}


@router.get("/status")
async def robot_status(user: dict = Depends(get_current_user)):
    """Return assignment, telemetry, and job context for the current user's robot."""
    if user.get("active_organization_id"):
        claimed = await robot_store.list_claimed_robots(user["active_organization_id"])
        if claimed:
            robot = claimed[0]
            telemetry = await robot_store.get_latest_robot_telemetry(robot["id"])
            return {
                "status": robot.get("claim_status") or robot.get("status") or "claimed",
                "robot_id": robot["id"],
                "serial_number": robot.get("serial_number"),
                "friendly_name": robot.get("friendly_name") or robot.get("serial_number"),
                "commissioned_at": robot.get("commissioned_at"),
                "connectivity": _connectivity_status(telemetry.get("created_at") if telemetry else robot.get("last_seen_at")),
                "current_job": None,
                "last_seen_at": telemetry.get("created_at") if telemetry else robot.get("last_seen_at"),
                "battery_pct": telemetry.get("battery_pct") if telemetry else robot.get("last_battery_pct"),
                "paint_level_pct": telemetry.get("paint_level_pct") if telemetry else None,
                "last_state": telemetry.get("state") if telemetry else robot.get("last_state"),
                "error_code": telemetry.get("error_code") if telemetry else None,
                "rssi": telemetry.get("rssi") if telemetry else None,
                "location": {
                    "lat": telemetry.get("lat"),
                    "lng": telemetry.get("lng"),
                } if telemetry and telemetry.get("lat") is not None and telemetry.get("lng") is not None else None,
            }

    assignment = await robot_store.get_user_robot(user["id"])
    if not assignment:
        return {"status": "no_robot", "message": "No robot assigned to your account"}

    telemetry = await robot_store.get_latest_robot_telemetry(assignment["robot_id"])
    current_job = await job_store.get_priority_job(user["id"])

    response = {
        "status": assignment.get("status", "unknown"),
        "robot_id": assignment.get("robot_id"),
        "serial_number": assignment.get("serial_number"),
        "assigned_at": assignment.get("created_at"),
        "tracking_number": assignment.get("tracking_number"),
        "shipped_at": assignment.get("shipped_at"),
        "delivered_at": assignment.get("delivered_at"),
        "return_tracking": assignment.get("return_tracking"),
        "connectivity": _connectivity_status(telemetry.get("created_at") if telemetry else None),
        "current_job": current_job,
    }
    if telemetry:
        response.update({
            "last_seen_at": telemetry.get("created_at"),
            "battery_pct": telemetry.get("battery_pct"),
            "paint_level_pct": telemetry.get("paint_level_pct"),
            "last_state": telemetry.get("state"),
            "error_code": telemetry.get("error_code"),
            "rssi": telemetry.get("rssi"),
            "location": {
                "lat": telemetry.get("lat"),
                "lng": telemetry.get("lng"),
            } if telemetry.get("lat") is not None and telemetry.get("lng") is not None else None,
        })
    else:
        response.update({
            "last_seen_at": None,
            "battery_pct": None,
            "paint_level_pct": None,
            "last_state": None,
            "error_code": None,
            "rssi": None,
            "location": None,
        })
    return response
