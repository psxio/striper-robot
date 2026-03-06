"""Authentication routes: register, login, current user."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import hash_password, verify_password, create_access_token, get_current_user
from ..config import settings
from ..models.schemas import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    UserResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
)
from ..rate_limit import limiter
from ..services import user_store
from ..shared import user_to_response

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("strype.auth")


@router.post("/register", response_model=AuthResponse, status_code=201)
@limiter.limit("3/minute")
async def register(request: Request, body: RegisterRequest):
    existing = await user_store.get_user_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    password_hash = hash_password(body.password)
    user = await user_store.create_user(body.email, password_hash, body.name)
    token = create_access_token(user["id"])
    logger.info("User registered: %s", body.email)
    return AuthResponse(token=token, user=user_to_response(user))


@router.post("/login", response_model=AuthResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest):
    user = await user_store.get_user_by_email(body.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Auto-assign admin if ADMIN_EMAIL matches
    if settings.ADMIN_EMAIL and user["email"] == settings.ADMIN_EMAIL and not user.get("is_admin"):
        from ..services.admin_store import set_admin
        await set_admin(user["id"], True)
        user["is_admin"] = 1

    token = create_access_token(user["id"])
    logger.info("User logged in: %s", body.email)
    return AuthResponse(token=token, user=user_to_response(user))


@router.get("/me", response_model=UserResponse)
async def me(user: dict = Depends(get_current_user)):
    return user_to_response(user)


@router.post("/forgot-password")
@limiter.limit("5/minute")
async def forgot_password(request: Request, body: ForgotPasswordRequest):
    """Request a password reset token. Always returns ok to prevent email enumeration."""
    user = await user_store.get_user_by_email(body.email)
    result = {"ok": True}
    if user:
        token = await user_store.create_reset_token(user["id"])
        # In dev mode, include token in response for testing
        env = getattr(settings, "ENV", None) or "dev"
        if env == "dev":
            result["token"] = token
    return result


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest):
    """Reset password using a valid reset token."""
    user_id = await user_store.validate_reset_token(body.token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    new_hash = hash_password(body.new_password)
    await user_store.update_password(user_id, new_hash)
    logger.info("Password reset completed for user %s", user_id)
    return {"ok": True}


@router.put("/password")
async def change_password(
    body: ChangePasswordRequest, user: dict = Depends(get_current_user)
):
    """Change password for authenticated user."""
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    new_hash = hash_password(body.new_password)
    await user_store.update_password(user["id"], new_hash)
    return {"ok": True}
