"""Customer-facing robot endpoints — assignment status and connectivity."""

import logging

from fastapi import APIRouter, Depends

from ..auth import get_current_user
from ..services import robot_store

router = APIRouter(prefix="/api/robots", tags=["robots"])
logger = logging.getLogger("strype.robots")


@router.get("")
async def get_my_robot(user: dict = Depends(get_current_user)):
    """Get the current user's assigned robot and assignment status."""
    assignment = await robot_store.get_user_robot(user["id"])
    return {"assignment": assignment}


@router.get("/status")
async def robot_status(user: dict = Depends(get_current_user)):
    """Robot connectivity and health status placeholder."""
    assignment = await robot_store.get_user_robot(user["id"])
    if not assignment:
        return {"status": "no_robot", "message": "No robot assigned to your account"}
    return {
        "status": assignment.get("status", "unknown"),
        "robot_id": assignment.get("robot_id"),
        "serial_number": assignment.get("serial_number"),
        "assigned_at": assignment.get("created_at"),
    }
