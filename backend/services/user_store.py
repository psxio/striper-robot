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
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row)


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
        cursor = await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()
        return cursor.rowcount > 0


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
