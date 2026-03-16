"""User preferences, profile, and account management routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from ..auth import get_current_user, verify_password
from ..database import get_db
from ..models.schemas import (
    UserPreferencesUpdate,
    UserResponse,
    UpdateProfileRequest,
    DeleteAccountRequest,
)
from ..services import user_store
from ..shared import user_to_response

router = APIRouter(prefix="/api/user", tags=["user"])
logger = logging.getLogger("strype.user")


@router.put("/preferences", response_model=UserResponse)
async def update_preferences(
    body: UserPreferencesUpdate, user: dict = Depends(get_current_user)
):
    # Validate active_lot_id belongs to user and is not deleted
    if body.active_lot_id is not None:
        from ..services import lot_store
        lot = await lot_store.get_lot(user["id"], body.active_lot_id)
        if not lot:
            raise HTTPException(status_code=404, detail="Lot not found")

    updated = await user_store.update_preferences(
        user["id"],
        active_lot_id=body.active_lot_id,
        map_state=body.map_state.model_dump() if body.map_state else None,
    )
    return user_to_response(updated)


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest, user: dict = Depends(get_current_user)
):
    """Update user name and/or email."""
    if body.email is not None and body.email != user["email"]:
        existing = await user_store.get_user_by_email(body.email)
        if existing and existing["id"] != user["id"]:
            raise HTTPException(status_code=409, detail="Email already in use")

    updated = await user_store.update_profile(
        user["id"], name=body.name, email=body.email,
        company_name=body.company_name, phone=body.phone,
    )
    return user_to_response(updated)


@router.delete("/account")
async def delete_account(
    body: DeleteAccountRequest, user: dict = Depends(get_current_user)
):
    """Delete the current user's account. Requires password confirmation."""
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect password")
    await user_store.delete_user(user["id"])
    logger.info("Account deleted: %s", user["email"])
    return {"ok": True}


@router.get("/export")
async def export_data(user: dict = Depends(get_current_user)):
    """GDPR data export — download all user data as JSON."""
    user_id = user["id"]
    export = {
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user.get("name", ""),
            "plan": user.get("plan", "free"),
            "created_at": user.get("created_at"),
            "updated_at": user.get("updated_at"),
        },
        "lots": [],
        "jobs": [],
        "subscriptions": [],
        "schedules": [],
    }
    async for db in get_db():
        cursor = await db.execute(
            "SELECT id, name, center_lat, center_lng, zoom, features, created_at, updated_at, deleted_at FROM lots WHERE user_id = ?",
            (user_id,),
        )
        export["lots"] = [dict(r) for r in await cursor.fetchall()]

        cursor = await db.execute(
            "SELECT id, lot_id, date, status, created_at, updated_at FROM jobs WHERE user_id = ?",
            (user_id,),
        )
        export["jobs"] = [dict(r) for r in await cursor.fetchall()]

        cursor = await db.execute(
            "SELECT id, plan, status, current_period_end, created_at, updated_at FROM subscriptions WHERE user_id = ?",
            (user_id,),
        )
        export["subscriptions"] = [dict(r) for r in await cursor.fetchall()]

        cursor = await db.execute(
            "SELECT id, lot_id, frequency, day_of_week, day_of_month, time_preference, active, next_run, created_at, updated_at FROM recurring_schedules WHERE user_id = ?",
            (user_id,),
        )
        export["schedules"] = [dict(r) for r in await cursor.fetchall()]

    return JSONResponse(
        content=export,
        headers={"Content-Disposition": "attachment; filename=strype-data-export.json"},
    )
