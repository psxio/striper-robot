"""Shared utilities used across multiple routers."""

from .config import settings
from .models.schemas import UserResponse


def user_to_response(user: dict) -> UserResponse:
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
        email_verified=bool(user.get("email_verified", 0)),
    )
