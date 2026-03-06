"""Admin routes: stats, user management, waitlist management."""

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from ..auth import get_admin_user
from ..services import admin_store, user_store
from ..services.billing_store import set_user_plan

router = APIRouter(prefix="/api/admin", tags=["admin"])


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


class SetPlanRequest(BaseModel):
    plan: str


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
    return {"ok": True}
