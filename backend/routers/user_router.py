"""User preferences, profile, and account management routes."""

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user, verify_password
from ..config import settings
from ..models.schemas import (
    UserPreferencesUpdate,
    UserResponse,
    UpdateProfileRequest,
    DeleteAccountRequest,
)
from ..services import user_store

router = APIRouter(prefix="/api/user", tags=["user"])


def _user_to_response(user: dict) -> UserResponse:
    """Convert a DB user dict to the API response shape."""
    map_state = None
    if user.get("map_lat") is not None and user.get("map_lng") is not None:
        map_state = {
            "lat": user["map_lat"],
            "lng": user["map_lng"],
            "zoom": user.get("map_zoom"),
        }
    plan = user["plan"] or "free"
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"] or "",
        plan=plan,
        active_lot_id=user.get("active_lot_id"),
        map_state=map_state,
        limits=settings.PLAN_LIMITS.get(plan),
    )


@router.put("/preferences", response_model=UserResponse)
async def update_preferences(
    body: UserPreferencesUpdate, user: dict = Depends(get_current_user)
):
    updated = await user_store.update_preferences(
        user["id"],
        active_lot_id=body.active_lot_id,
        map_state=body.map_state,
    )
    return _user_to_response(updated)


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest, user: dict = Depends(get_current_user)
):
    """Update user name and/or email."""
    if body.email is not None and body.email != user["email"]:
        existing = await user_store.get_user_by_email(body.email)
        if existing:
            raise HTTPException(status_code=409, detail="Email already in use")

    updated = await user_store.update_profile(
        user["id"], name=body.name, email=body.email
    )
    return _user_to_response(updated)


@router.delete("/account")
async def delete_account(
    body: DeleteAccountRequest, user: dict = Depends(get_current_user)
):
    """Delete the current user's account. Requires password confirmation."""
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect password")
    await user_store.delete_user(user["id"])
    return {"ok": True}
