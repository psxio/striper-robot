"""Authentication routes: register, login, current user, refresh, email verification."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from ..auth import hash_password, verify_password, create_access_token, get_current_user, block_token
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


class VerifyEmailRequest(BaseModel):
    token: str


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

    # Generate email verification token
    verification_token = await user_store.create_verification_token(user["id"])

    # Send welcome + verification email (best effort)
    try:
        from ..services.email_service import send_welcome_email
        await send_welcome_email(body.email, body.name)
    except Exception:
        logger.warning("Failed to send welcome email to %s", body.email)

    try:
        from ..services.email_service import send_verification_email
        frontend_url = settings.FRONTEND_URL or "http://localhost:8000"
        await send_verification_email(body.email, verification_token, frontend_url)
    except Exception:
        logger.warning("Failed to send verification email to %s", body.email)

    return AuthResponse(token=token, user=user_to_response(user))


@router.post("/login", response_model=AuthResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest):
    # Check lockout before anything else
    locked_until = await user_store.check_login_lockout(body.email)
    if locked_until:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")

    user = await user_store.get_user_by_email(body.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(body.password, user["password_hash"]):
        await user_store.record_failed_login(body.email)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Successful login — clear any failed attempts
    await user_store.clear_login_attempts(body.email)

    # Auto-assign admin if ADMIN_EMAIL matches
    if settings.ADMIN_EMAIL and user["email"] == settings.ADMIN_EMAIL and not user.get("is_admin"):
        from ..services.admin_store import set_admin
        await set_admin(user["id"], True)
        user["is_admin"] = 1

    token = create_access_token(user["id"])
    logger.info("User logged in: %s", body.email)

    # Issue refresh token as httpOnly cookie
    refresh_token = await user_store.create_refresh_token(
        user["id"], expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    auth_resp = AuthResponse(token=token, user=user_to_response(user))
    response = Response(
        content=auth_resp.model_dump_json(),
        media_type="application/json",
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        secure=settings.ENV != "dev",
    )
    return response


@router.get("/me", response_model=UserResponse)
async def me(user: dict = Depends(get_current_user)):
    return user_to_response(user)


@router.post("/logout")
async def logout(user: dict = Depends(get_current_user)):
    """Invalidate the current access token and all refresh tokens."""
    jti = user.get("_token_jti")
    exp = user.get("_token_exp")
    if jti and exp:
        from datetime import datetime, timezone
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()
        await block_token(jti, user["id"], expires_at)

    # Also revoke all refresh tokens for this user
    await user_store.delete_user_refresh_tokens(user["id"])

    response = Response(content='{"ok":true}', media_type="application/json")
    response.delete_cookie("refresh_token")
    return response


@router.post("/forgot-password")
@limiter.limit("5/minute")
async def forgot_password(request: Request, body: ForgotPasswordRequest):
    """Request a password reset token. Always returns ok to prevent email enumeration."""
    user = await user_store.get_user_by_email(body.email)
    result = {"ok": True}
    if user:
        token = await user_store.create_reset_token(user["id"])
        # Send reset email
        from ..services.email_service import send_password_reset_email
        frontend_url = settings.FRONTEND_URL or str(request.base_url).rstrip("/")
        await send_password_reset_email(body.email, token, frontend_url)
        # In dev mode, also include token in response for testing
        if settings.ENV == "dev":
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


@router.post("/refresh")
async def refresh_token(request: Request):
    """Issue a new access token using a valid refresh token cookie. Rotates the refresh token."""
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")

    user_id = await user_store.validate_refresh_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = await user_store.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    new_access = create_access_token(user_id)
    new_refresh = await user_store.create_refresh_token(
        user_id, expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    response = Response(
        content='{"token":"' + new_access + '"}',
        media_type="application/json",
    )
    response.set_cookie(
        "refresh_token",
        new_refresh,
        httponly=True,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        secure=settings.ENV != "dev",
    )
    return response


@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequest):
    """Verify a user's email address using the verification token."""
    user_id = await user_store.verify_email_token(body.token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    logger.info("Email verified for user %s", user_id)
    return {"ok": True}


@router.post("/resend-verification")
@limiter.limit("3/minute")
async def resend_verification(request: Request, user: dict = Depends(get_current_user)):
    """Resend the email verification link. Rate-limited."""
    if user.get("email_verified"):
        raise HTTPException(status_code=400, detail="Email already verified")

    token = await user_store.create_verification_token(user["id"])

    try:
        from ..services.email_service import send_verification_email
        frontend_url = settings.FRONTEND_URL or str(request.base_url).rstrip("/")
        await send_verification_email(user["email"], token, frontend_url)
    except Exception:
        logger.warning("Failed to send verification email to %s", user["email"])

    result = {"ok": True}
    if settings.ENV == "dev":
        result["token"] = token
    return result
