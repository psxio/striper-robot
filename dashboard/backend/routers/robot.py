"""Robot control and status endpoints."""

from fastapi import APIRouter

from ..models.schemas import GeoPoint, RobotStatus
from ..services.ros_bridge import ros_bridge

router = APIRouter(prefix="/api/robot", tags=["robot"])


@router.get("/status", response_model=RobotStatus)
async def get_status():
    return ros_bridge.get_status()


@router.post("/estop")
async def estop():
    return await ros_bridge.estop()


@router.post("/release-estop")
async def release_estop():
    return await ros_bridge.release_estop()


@router.get("/position", response_model=GeoPoint)
async def get_position():
    status = ros_bridge.get_status()
    if status.position:
        return status.position
    return GeoPoint(lat=0.0, lng=0.0)
