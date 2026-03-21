"""Organization and membership persistence helpers."""

import hashlib
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from ..database import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or f"org-{uuid.uuid4().hex[:8]}"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_organization(
    name: str,
    created_by_user_id: str,
    role: str = "owner",
    personal: bool = False,
) -> dict:
    org_id = str(uuid.uuid4())
    membership_id = str(uuid.uuid4())
    now = _now()
    base_slug = _slugify(name)
    slug = base_slug

    async for db in get_db():
        cursor = await db.execute("SELECT 1 FROM organizations WHERE slug = ?", (slug,))
        suffix = 1
        while await cursor.fetchone():
            suffix += 1
            slug = f"{base_slug}-{suffix}"
            cursor = await db.execute("SELECT 1 FROM organizations WHERE slug = ?", (slug,))

        await db.execute(
            """INSERT INTO organizations (id, name, slug, personal, created_by_user_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (org_id, name, slug, 1 if personal else 0, created_by_user_id, now, now),
        )
        await db.execute(
            """INSERT INTO memberships (id, organization_id, user_id, role, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'active', ?, ?)""",
            (membership_id, org_id, created_by_user_id, role, now, now),
        )
        await db.execute(
            "UPDATE users SET active_organization_id = ?, updated_at = ? WHERE id = ? AND active_organization_id IS NULL",
            (org_id, now, created_by_user_id),
        )
        await db.commit()

    org = await get_organization(org_id)
    return org or {}


async def ensure_personal_organization(user_id: str, email: str, name: str = "") -> str:
    async for db in get_db():
        cursor = await db.execute(
            """SELECT o.id
               FROM organizations o
               JOIN memberships m ON m.organization_id = o.id
               WHERE m.user_id = ? AND o.personal = 1
               ORDER BY o.created_at ASC
               LIMIT 1""",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row:
            await db.execute(
                "UPDATE users SET active_organization_id = COALESCE(active_organization_id, ?) WHERE id = ?",
                (row["id"], user_id),
            )
            await db.commit()
            return row["id"]

    base_name = name.strip() if name.strip() else email.split("@", 1)[0]
    org = await create_organization(f"{base_name} Workspace", user_id, personal=True)
    return org["id"]


async def get_organization(organization_id: str) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM organizations WHERE id = ?",
            (organization_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_membership(organization_id: str, user_id: str) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute(
            """SELECT m.*, o.name AS organization_name, o.slug AS organization_slug, o.personal
               FROM memberships m
               JOIN organizations o ON o.id = m.organization_id
               WHERE m.organization_id = ? AND m.user_id = ? AND m.status = 'active'""",
            (organization_id, user_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def list_user_organizations(user_id: str) -> list[dict]:
    async for db in get_db():
        cursor = await db.execute(
            """SELECT o.id, o.name, o.slug, o.personal, m.role, m.status
               FROM memberships m
               JOIN organizations o ON o.id = m.organization_id
               WHERE m.user_id = ? AND m.status = 'active'
               ORDER BY o.personal DESC, o.created_at ASC""",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def set_active_organization(user_id: str, organization_id: str) -> bool:
    membership = await get_membership(organization_id, user_id)
    if not membership:
        return False
    async for db in get_db():
        cursor = await db.execute(
            "UPDATE users SET active_organization_id = ?, updated_at = ? WHERE id = ?",
            (organization_id, _now(), user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def create_membership(organization_id: str, user_id: str, role: str) -> Optional[dict]:
    now = _now()
    async for db in get_db():
        cursor = await db.execute(
            "SELECT id FROM memberships WHERE organization_id = ? AND user_id = ?",
            (organization_id, user_id),
        )
        existing = await cursor.fetchone()
        if existing:
            await db.execute(
                """UPDATE memberships
                   SET role = ?, status = 'active', updated_at = ?
                   WHERE organization_id = ? AND user_id = ?""",
                (role, now, organization_id, user_id),
            )
        else:
            membership_id = str(uuid.uuid4())
            await db.execute(
                """INSERT INTO memberships
                   (id, organization_id, user_id, role, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'active', ?, ?)""",
                (membership_id, organization_id, user_id, role, now, now),
            )
        await db.commit()
    return await get_membership(organization_id, user_id)


async def list_memberships(organization_id: str) -> list[dict]:
    async for db in get_db():
        cursor = await db.execute(
            """SELECT m.organization_id, m.user_id, m.role, m.status, m.created_at, m.updated_at,
                      u.email, u.name
               FROM memberships m
               JOIN users u ON u.id = m.user_id
               WHERE m.organization_id = ?
               ORDER BY m.created_at ASC""",
            (organization_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_default_organization_id(user_id: str) -> Optional[str]:
    async for db in get_db():
        cursor = await db.execute(
            "SELECT active_organization_id FROM users WHERE id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row and row["active_organization_id"]:
            return row["active_organization_id"]
    orgs = await list_user_organizations(user_id)
    return orgs[0]["id"] if orgs else None


async def get_membership_by_user_id(organization_id: str, target_user_id: str) -> Optional[dict]:
    return await get_membership(organization_id, target_user_id)


async def list_pending_invites(organization_id: str) -> list[dict]:
    async for db in get_db():
        cursor = await db.execute(
            """SELECT * FROM organization_invites
               WHERE organization_id = ? AND status = 'pending'
               ORDER BY created_at DESC""",
            (organization_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    return []


async def get_invite(invite_id: str) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM organization_invites WHERE id = ?",
            (invite_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_invite(
    organization_id: str,
    invited_by_user_id: str,
    email: str,
    role: str,
    *,
    expire_days: int = 7,
) -> dict:
    email_normalized = email.strip().lower()
    now = _now()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=expire_days)).isoformat()
    invite_id = str(uuid.uuid4())
    raw_token = uuid.uuid4().hex + uuid.uuid4().hex
    token_hash = _hash_token(raw_token)

    async for db in get_db():
        cursor = await db.execute(
            """SELECT u.id
               FROM users u
               JOIN memberships m ON m.user_id = u.id
               WHERE m.organization_id = ? AND m.status = 'active' AND LOWER(u.email) = ?""",
            (organization_id, email_normalized),
        )
        if await cursor.fetchone():
            raise ValueError("User is already a member of this organization")
        await db.execute(
            """UPDATE organization_invites
               SET status = 'revoked', updated_at = ?
               WHERE organization_id = ? AND LOWER(email) = ? AND status = 'pending'""",
            (now, organization_id, email_normalized),
        )
        await db.execute(
            """INSERT INTO organization_invites
               (id, organization_id, email, role, token_hash, status, invited_by_user_id, expires_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)""",
            (invite_id, organization_id, email_normalized, role, token_hash, invited_by_user_id, expires_at, now, now),
        )
        await db.commit()

    invite = await get_invite(invite_id)
    if invite:
        invite["accept_token"] = raw_token
    return invite or {}


async def accept_invite(token: str, user_id: str, user_email: str) -> Optional[dict]:
    now = _now()
    token_hash = _hash_token(token)
    email_normalized = user_email.strip().lower()
    async for db in get_db():
        cursor = await db.execute(
            """SELECT * FROM organization_invites
               WHERE token_hash = ? AND status = 'pending' AND expires_at > ?""",
            (token_hash, now),
        )
        invite = await cursor.fetchone()
        if not invite:
            return None
        invite_data = dict(invite)
        if invite_data["email"].strip().lower() != email_normalized:
            raise ValueError("Invite email does not match the authenticated user")
        existing = await get_membership(invite_data["organization_id"], user_id)
        if existing:
            await db.execute(
                """UPDATE memberships
                   SET role = ?, status = 'active', updated_at = ?
                   WHERE organization_id = ? AND user_id = ?""",
                (invite_data["role"], now, invite_data["organization_id"], user_id),
            )
        else:
            membership_id = str(uuid.uuid4())
            await db.execute(
                """INSERT INTO memberships
                   (id, organization_id, user_id, role, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'active', ?, ?)""",
                (membership_id, invite_data["organization_id"], user_id, invite_data["role"], now, now),
            )
        await db.execute(
            """UPDATE organization_invites
               SET status = 'accepted', accepted_by_user_id = ?, accepted_at = ?, updated_at = ?
               WHERE id = ?""",
            (user_id, now, now, invite_data["id"]),
        )
        await db.execute(
            """UPDATE users
               SET active_organization_id = ?, updated_at = ?
               WHERE id = ?""",
            (invite_data["organization_id"], now, user_id),
        )
        await db.commit()
        return await get_invite(invite_data["id"])
    return None


async def count_active_owners(organization_id: str) -> int:
    async for db in get_db():
        cursor = await db.execute(
            """SELECT COUNT(*)
               FROM memberships
               WHERE organization_id = ? AND status = 'active' AND role = 'owner'""",
            (organization_id,),
        )
        return (await cursor.fetchone())[0]
    return 0


async def update_membership_role(
    organization_id: str,
    target_user_id: str,
    role: str,
) -> Optional[dict]:
    membership = await get_membership(organization_id, target_user_id)
    if not membership:
        return None
    if membership["role"] == "owner" and role != "owner":
        owner_count = await count_active_owners(organization_id)
        if owner_count <= 1:
            raise ValueError("Organization must retain at least one owner")
    async for db in get_db():
        await db.execute(
            """UPDATE memberships
               SET role = ?, updated_at = ?
               WHERE organization_id = ? AND user_id = ?""",
            (role, _now(), organization_id, target_user_id),
        )
        await db.commit()
    return await get_membership(organization_id, target_user_id)


async def remove_membership(organization_id: str, target_user_id: str) -> bool:
    membership = await get_membership(organization_id, target_user_id)
    if not membership:
        return False
    if membership["role"] == "owner":
        owner_count = await count_active_owners(organization_id)
        if owner_count <= 1:
            raise ValueError("Organization must retain at least one owner")
    now = _now()
    async for db in get_db():
        await db.execute(
            "DELETE FROM memberships WHERE organization_id = ? AND user_id = ?",
            (organization_id, target_user_id),
        )
        cursor = await db.execute(
            "SELECT active_organization_id FROM users WHERE id = ?",
            (target_user_id,),
        )
        row = await cursor.fetchone()
        if row and row["active_organization_id"] == organization_id:
            cursor = await db.execute(
                """SELECT organization_id
                   FROM memberships
                   WHERE user_id = ? AND status = 'active'
                   ORDER BY created_at ASC
                   LIMIT 1""",
                (target_user_id,),
            )
            replacement = await cursor.fetchone()
            await db.execute(
                "UPDATE users SET active_organization_id = ?, updated_at = ? WHERE id = ?",
                (replacement["organization_id"] if replacement else None, now, target_user_id),
            )
        await db.commit()
        return True
    return False
