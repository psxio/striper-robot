"""User persistence layer using aiosqlite."""

import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from ..database import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_token(token: str) -> str:
    """Hash a reset token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


async def create_user(email: str, password_hash: str, name: str = "") -> dict:
    """Create a new user and return its dict representation."""
    user_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        await db.execute(
            """INSERT INTO users (id, email, password_hash, name, plan, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'free', ?, ?)""",
            (user_id, email, password_hash, name, now, now),
        )
        await db.commit()
    from .organization_store import ensure_personal_organization

    await ensure_personal_organization(user_id, email, name)
    user = await get_user_by_id(user_id)
    return user or {}


async def get_user_by_email(email: str) -> Optional[dict]:
    """Look up a user by email address."""
    async for db in get_db():
        cursor = await db.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_user_by_id(user_id: str) -> Optional[dict]:
    """Look up a user by ID."""
    async for db in get_db():
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_preferences(
    user_id: str,
    active_lot_id: Optional[str] = None,
    map_state: Optional[dict] = None,
) -> Optional[dict]:
    """Update user preferences (active lot and/or map state)."""
    fields: list[str] = []
    values: list[object] = []

    if active_lot_id is not None:
        fields.append("active_lot_id = ?")
        values.append(active_lot_id)

    if map_state is not None:
        if "lat" in map_state:
            fields.append("map_lat = ?")
            values.append(map_state["lat"])
        if "lng" in map_state:
            fields.append("map_lng = ?")
            values.append(map_state["lng"])
        if "zoom" in map_state:
            fields.append("map_zoom = ?")
            values.append(map_state["zoom"])

    if not fields:
        return await get_user_by_id(user_id)

    fields.append("updated_at = ?")
    values.append(_now())
    values.append(user_id)

    async for db in get_db():
        await db.execute(
            f"UPDATE users SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        await db.commit()

    return await get_user_by_id(user_id)


async def update_password(user_id: str, password_hash: str) -> bool:
    """Update a user's password hash."""
    async for db in get_db():
        cursor = await db.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (password_hash, _now(), user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def update_profile(
    user_id: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    company_name: Optional[str] = None,
    phone: Optional[str] = None,
) -> Optional[dict]:
    """Update user profile fields."""
    fields: list[str] = []
    values: list[object] = []

    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if email is not None:
        fields.append("email = ?")
        values.append(email)
        # Reset email verification when address changes
        fields.append("email_verified = ?")
        values.append(0)
        fields.append("verification_token = ?")
        values.append(None)
        fields.append("verification_expires_at = ?")
        values.append(None)
    if company_name is not None:
        fields.append("company_name = ?")
        values.append(company_name)
    if phone is not None:
        fields.append("phone = ?")
        values.append(phone)

    if not fields:
        return await get_user_by_id(user_id)

    fields.append("updated_at = ?")
    values.append(_now())
    values.append(user_id)

    async for db in get_db():
        await db.execute(
            f"UPDATE users SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        await db.commit()

    return await get_user_by_id(user_id)


async def delete_user(user_id: str) -> bool:
    """Delete a user and all associated data (cascaded by FK)."""
    async for db in get_db():
        await db.execute("BEGIN IMMEDIATE")
        try:
            # Personal workspaces should disappear with the user. Shared workspaces
            # keep operating, so we null out creator references before deletion.
            await db.execute(
                "DELETE FROM organizations WHERE created_by_user_id = ? AND personal = 1",
                (user_id,),
            )
            await db.execute(
                "UPDATE organizations SET created_by_user_id = NULL WHERE created_by_user_id = ?",
                (user_id,),
            )
            await db.execute(
                "UPDATE sites SET created_by_user_id = NULL WHERE created_by_user_id = ?",
                (user_id,),
            )
            await db.execute(
                "UPDATE quotes SET created_by_user_id = NULL WHERE created_by_user_id = ?",
                (user_id,),
            )
            await db.execute(
                "UPDATE job_reports SET created_by_user_id = NULL WHERE created_by_user_id = ?",
                (user_id,),
            )
            await db.execute(
                "UPDATE maintenance_events SET created_by_user_id = NULL WHERE created_by_user_id = ?",
                (user_id,),
            )
            await db.execute(
                "UPDATE service_checklists SET created_by_user_id = NULL WHERE created_by_user_id = ?",
                (user_id,),
            )
            await db.execute(
                "UPDATE consumable_usage SET created_by_user_id = NULL WHERE created_by_user_id = ?",
                (user_id,),
            )
            cursor = await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
            await db.execute("COMMIT")
            return cursor.rowcount > 0
        except Exception:
            await db.execute("ROLLBACK")
            raise


# --- Password Reset Tokens ---

async def create_reset_token(user_id: str) -> str:
    """Create a password reset token valid for 1 hour. Returns the raw token."""
    token = str(uuid.uuid4())
    token_hash = _hash_token(token)
    reset_id = str(uuid.uuid4())
    now = _now()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    async for db in get_db():
        # Delete any existing tokens for this user
        await db.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
        await db.execute(
            """INSERT INTO password_resets (id, user_id, token_hash, expires_at, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (reset_id, user_id, token_hash, expires_at, now),
        )
        await db.commit()

    return token


# --- Login Attempt Lockout ---

_MAX_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15


async def check_login_lockout(email: str) -> Optional[str]:
    """Check if an email is locked out. Returns locked_until ISO string if locked, else None."""
    now = datetime.now(timezone.utc).isoformat()
    async for db in get_db():
        cursor = await db.execute(
            "SELECT locked_until FROM login_attempts WHERE email = ? AND locked_until > ?",
            (email, now),
        )
        row = await cursor.fetchone()
        return row["locked_until"] if row else None


async def record_failed_login(email: str) -> None:
    """Record a failed login attempt. Locks the account after MAX_ATTEMPTS failures."""
    now = _now()
    async for db in get_db():
        cursor = await db.execute(
            "SELECT attempts FROM login_attempts WHERE email = ?", (email,)
        )
        row = await cursor.fetchone()
        attempts = (row["attempts"] + 1) if row else 1
        locked_until = None
        if attempts >= _MAX_ATTEMPTS:
            locked_until = (
                datetime.now(timezone.utc) + timedelta(minutes=_LOCKOUT_MINUTES)
            ).isoformat()
        if row:
            await db.execute(
                "UPDATE login_attempts SET attempts = ?, locked_until = ?, updated_at = ? WHERE email = ?",
                (attempts, locked_until, now, email),
            )
        else:
            await db.execute(
                "INSERT INTO login_attempts (email, attempts, locked_until, updated_at) VALUES (?, ?, ?, ?)",
                (email, attempts, locked_until, now),
            )
        await db.commit()


async def clear_login_attempts(email: str) -> None:
    """Clear login attempts after a successful login."""
    async for db in get_db():
        await db.execute("DELETE FROM login_attempts WHERE email = ?", (email,))
        await db.commit()


async def validate_reset_token(token: str) -> Optional[str]:
    """Validate a reset token and return the user_id if valid. Deletes the token."""
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc).isoformat()

    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM password_resets WHERE token_hash = ? AND expires_at > ?",
            (token_hash, now),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        user_id = row["user_id"]
        # Delete the used token
        await db.execute("DELETE FROM password_resets WHERE id = ?", (row["id"],))
        await db.commit()
        return user_id


# --- Refresh Tokens ---

async def create_refresh_token(user_id: str, expire_days: int = 7) -> str:
    """Create a refresh token for a user. Returns the raw token."""
    token = str(uuid.uuid4())
    token_hash = _hash_token(token)
    token_id = str(uuid.uuid4())
    now = _now()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=expire_days)).isoformat()

    async for db in get_db():
        await db.execute(
            """INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (token_id, user_id, token_hash, expires_at, now),
        )
        await db.commit()

    return token


async def validate_refresh_token(token: str) -> Optional[str]:
    """Validate a refresh token and return the user_id if valid. Deletes the used token."""
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc).isoformat()

    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM refresh_tokens WHERE token_hash = ? AND expires_at > ?",
            (token_hash, now),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        user_id = row["user_id"]
        # Delete the used token (rotation — caller should issue a new one)
        await db.execute("DELETE FROM refresh_tokens WHERE id = ?", (row["id"],))
        await db.commit()
        return user_id


async def delete_user_refresh_tokens(user_id: str) -> None:
    """Delete all refresh tokens for a user (e.g. on logout)."""
    async for db in get_db():
        await db.execute("DELETE FROM refresh_tokens WHERE user_id = ?", (user_id,))
        await db.commit()


# --- Email Verification ---

async def create_verification_token(user_id: str) -> str:
    """Generate an email verification token and store its hash on the user. Returns the raw token."""
    token = str(uuid.uuid4())
    token_hash = _hash_token(token)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

    async for db in get_db():
        await db.execute(
            "UPDATE users SET verification_token = ?, verification_expires_at = ?, updated_at = ? WHERE id = ?",
            (token_hash, expires_at, _now(), user_id),
        )
        await db.commit()

    return token


async def verify_email_token(token: str) -> Optional[str]:
    """Validate a verification token and mark the user as verified. Returns user_id or None."""
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc).isoformat()

    async for db in get_db():
        cursor = await db.execute(
            "SELECT id FROM users WHERE verification_token = ? AND verification_expires_at > ?",
            (token_hash, now),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        user_id = row["id"]
        await db.execute(
            "UPDATE users SET email_verified = 1, verification_token = NULL, verification_expires_at = NULL, updated_at = ? WHERE id = ?",
            (_now(), user_id),
        )
        await db.commit()
        return user_id
