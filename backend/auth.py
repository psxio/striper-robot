"""Authentication utilities: password hashing, JWT tokens, current user dependency."""

import uuid

import bcrypt
import jwt
from datetime import datetime, timedelta, timezone

from fastapi import Request, HTTPException

from .config import settings
from .database import get_db

_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: str, plan: str = "free") -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    jti = str(uuid.uuid4())
    payload = {"sub": user_id, "exp": expire, "jti": jti, "plan": plan}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Decode a JWT and return the full payload, or None if invalid/expired.

    PyJWT already rejects expired tokens (raises ExpiredSignatureError),
    so any token returned here is guaranteed to be within its exp window.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.PyJWTError:
        return None


async def is_token_blocked(jti: str) -> bool:
    """Check if a token JTI is in the blocklist.

    Only checks non-expired entries — expired blocklist rows are harmless
    but the cleanup loop purges them periodically.
    """
    async for db in get_db():
        cursor = await db.execute(
            "SELECT 1 FROM token_blocklist WHERE jti = ?", (jti,)
        )
        return await cursor.fetchone() is not None


async def block_token(jti: str, user_id: str, expires_at: str) -> None:
    """Add a token to the blocklist."""
    now = datetime.now(timezone.utc).isoformat()
    async for db in get_db():
        await db.execute(
            "INSERT INTO token_blocklist (jti, user_id, expires_at, created_at) VALUES (?, ?, ?, ?) ON CONFLICT(jti) DO NOTHING",
            (jti, user_id, expires_at, now),
        )
        await db.commit()


async def get_current_user(request: Request) -> dict:
    """FastAPI dependency that extracts and validates the current user from the
    Authorization header. Raises 401 on any failure."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Check token blocklist
    jti = payload.get("jti")
    if jti and await is_token_blocked(jti):
        raise HTTPException(status_code=401, detail="Token has been revoked")

    async for db in get_db():
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = await cursor.fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        # Store token info on user dict for logout
        user_dict = dict(user)
        user_dict["_token_jti"] = jti
        user_dict["_token_exp"] = payload.get("exp")
        return user_dict


async def require_active_billing(request: Request) -> dict:
    """FastAPI dependency that verifies the user has active billing.

    Free-tier users (no subscription) are always allowed.
    Paid-tier users must have an active subscription (not cancelled/past_due).
    Raises 403 if billing is inactive.
    """
    user = await get_current_user(request)
    from .services.billing_store import is_billing_active
    if not await is_billing_active(user["id"]):
        raise HTTPException(
            status_code=403,
            detail="Subscription inactive — please update your billing at /billing.html",
        )
    return user


async def get_admin_user(request: Request) -> dict:
    """FastAPI dependency that requires an admin user. Raises 403 if not admin."""
    user = await get_current_user(request)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
