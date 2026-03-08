"""Admin routes: stats, user management, waitlist management."""

import csv
import io
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from ..auth import get_admin_user
from ..models.schemas import (
    SetPlanRequest, RobotCreate, RobotUpdate, AssignRobotRequest, AssignmentUpdate,
)
from ..services import admin_store, user_store, waitlist_store
from ..services import robot_store
from ..services.billing_store import set_user_plan

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger("strype.admin")


@router.get("/stats")
async def stats(admin: dict = Depends(get_admin_user)):
    """Get platform-wide statistics."""
    return await admin_store.get_stats()


@router.get("/users")
async def list_users(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    admin: dict = Depends(get_admin_user),
):
    """List all users with lot/job counts."""
    items, total = await admin_store.list_users(page=page, limit=limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.get("/waitlist")
async def list_waitlist(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    format: str = Query(default="json"),
    admin: dict = Depends(get_admin_user),
):
    """List all waitlist entries. Use format=csv for CSV export."""
    # CSV exports get all entries regardless of pagination params
    if format == "csv":
        items, total = await admin_store.list_waitlist(page=1, limit=100000)
    else:
        items, total = await admin_store.list_waitlist(page=page, limit=limit)

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "email", "source", "created_at"])
        for item in items:
            writer.writerow([item["id"], item["email"], item["source"], item["created_at"]])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=waitlist.csv"},
        )

    return {"items": items, "total": total, "page": page, "limit": limit}


@router.put("/users/{user_id}/plan")
async def set_plan(
    user_id: str,
    body: SetPlanRequest,
    admin: dict = Depends(get_admin_user),
):
    """Set a user's plan (admin override)."""
    user = await user_store.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await set_user_plan(user_id, body.plan)
    await admin_store.log_audit(admin["email"], "set_plan", user_id, body.plan)
    logger.info("Admin %s changed user %s plan to %s", admin["email"], user_id, body.plan)
    return {"ok": True, "plan": body.plan}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: dict = Depends(get_admin_user),
):
    """Delete a user (admin override)."""
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    deleted = await user_store.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    await admin_store.log_audit(admin["email"], "delete_user", user_id)
    logger.info("Admin %s deleted user %s", admin["email"], user_id)
    return {"ok": True}


@router.get("/audit-log")
async def list_audit_log(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    admin: dict = Depends(get_admin_user),
):
    """List admin audit log entries."""
    items, total = await admin_store.list_audit_logs(page=page, limit=limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.delete("/waitlist/{entry_id}")
async def delete_waitlist_entry(
    entry_id: int,
    admin: dict = Depends(get_admin_user),
):
    """Delete a waitlist entry."""
    deleted = await waitlist_store.delete_waitlist_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")
    await admin_store.log_audit(admin["email"], "delete_waitlist", str(entry_id))
    return {"ok": True}


# --- Robot Fleet Management ---


@router.get("/robots")
async def list_robots(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    status: str = Query(default=None),
    admin: dict = Depends(get_admin_user),
):
    """List all robots with optional status filter."""
    items, total = await robot_store.list_robots(page=page, limit=limit, status=status)
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.post("/robots", status_code=201)
async def create_robot(body: RobotCreate, admin: dict = Depends(get_admin_user)):
    """Add a robot to the fleet."""
    robot = await robot_store.create_robot(
        serial_number=body.serial_number,
        hardware_version=body.hardware_version,
        firmware_version=body.firmware_version,
        notes=body.notes,
    )
    await admin_store.log_audit(admin["email"], "create_robot", robot["id"], body.serial_number)
    return robot


@router.put("/robots/{robot_id}")
async def update_robot(
    robot_id: str, body: RobotUpdate, admin: dict = Depends(get_admin_user)
):
    """Update a robot's status, firmware, or notes."""
    robot = await robot_store.update_robot(
        robot_id, status=body.status, firmware_version=body.firmware_version, notes=body.notes
    )
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found")
    await admin_store.log_audit(admin["email"], "update_robot", robot_id)
    return robot


@router.get("/robots/{robot_id}/history")
async def robot_history(robot_id: str, admin: dict = Depends(get_admin_user)):
    """Get assignment history for a robot."""
    robot = await robot_store.get_robot(robot_id)
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found")
    history = await robot_store.get_robot_history(robot_id)
    return {"robot_id": robot_id, "assignments": history}


@router.post("/robots/assign", status_code=201)
async def assign_robot(body: AssignRobotRequest, admin: dict = Depends(get_admin_user)):
    """Assign a robot to a user."""
    robot = await robot_store.get_robot(body.robot_id)
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found")
    if robot["status"] == "retired":
        raise HTTPException(status_code=400, detail="Cannot assign a retired robot")
    if robot["status"] == "assigned":
        raise HTTPException(status_code=400, detail="Robot is already assigned")

    user = await user_store.get_user_by_id(body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    assignment = await robot_store.assign_robot(body.robot_id, body.user_id)
    await admin_store.log_audit(
        admin["email"], "assign_robot", body.robot_id, f"user={body.user_id}"
    )
    return assignment


@router.put("/robots/assignments/{assignment_id}")
async def update_assignment(
    assignment_id: str, body: AssignmentUpdate, admin: dict = Depends(get_admin_user)
):
    """Update an assignment (tracking, status)."""
    assignment = await robot_store.update_assignment(
        assignment_id,
        status=body.status,
        tracking_number=body.tracking_number,
        return_tracking=body.return_tracking,
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    await admin_store.log_audit(admin["email"], "update_assignment", assignment_id)
    return assignment


@router.get("/assignments")
async def list_assignments(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    status: str = Query(default=None),
    admin: dict = Depends(get_admin_user),
):
    """List all robot assignments."""
    items, total = await robot_store.list_assignments(page=page, limit=limit, status=status)
    return {"items": items, "total": total, "page": page, "limit": limit}
