"""Robot fleet management persistence layer using aiosqlite."""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..database import get_db


def _hash_api_key(key: str) -> str:
    """SHA-256 hash a robot API key for storage. Only the hash is persisted."""
    return hashlib.sha256(key.encode()).hexdigest()


def _hash_claim_code(code: str) -> str:
    """SHA-256 hash a claim code for storage."""
    return hashlib.sha256(code.encode()).hexdigest()


def _now() -> str:
    """Current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


class RobotAssignmentConflict(ValueError):
    """Raised when a robot assignment would violate active-assignment rules."""


async def _get_active_claim_for_robot(robot_id: str) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute(
            """SELECT rc.*, r.serial_number, r.firmware_version, r.maintenance_status,
                      r.issue_state, r.last_seen_at
               FROM robot_claims rc
               JOIN robots r ON r.id = rc.robot_id
               WHERE rc.robot_id = ? AND rc.status IN ('pending', 'claimed')
               ORDER BY rc.created_at DESC
               LIMIT 1""",
            (robot_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def _decorate_robot_with_claim(robot: dict) -> dict:
    claim = await _get_active_claim_for_robot(robot["id"])
    enriched = dict(robot)
    enriched["claim_status"] = claim["status"] if claim else None
    enriched["commissioning_status"] = claim["commissioning_status"] if claim else None
    enriched["claimed_by_user_id"] = claim["claimed_by_user_id"] if claim else None
    enriched["organization_id"] = claim["organization_id"] if claim else None
    enriched["commissioned_at"] = claim["commissioned_at"] if claim else None
    enriched["friendly_name"] = claim.get("friendly_name") if claim else ""
    enriched["deployment_notes"] = claim.get("deployment_notes") if claim else ""
    return enriched


async def create_robot(
    serial_number: str,
    hardware_version: str = "v1",
    firmware_version: Optional[str] = None,
    notes: str = "",
) -> dict:
    """Create a new robot and return its dict representation."""
    robot_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        await db.execute(
            """INSERT INTO robots (id, serial_number, status, hardware_version,
                                   firmware_version, notes, created_at, updated_at)
               VALUES (?, ?, 'available', ?, ?, ?, ?, ?)""",
            (robot_id, serial_number, hardware_version, firmware_version, notes, now, now),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM robots WHERE id = ?", (robot_id,))
        row = await cursor.fetchone()
        return dict(row)


async def list_robots(
    page: int = 1,
    limit: int = 50,
    status: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> tuple[list[dict], int]:
    """List robots with optional status filter, paginated."""
    async for db in get_db():
        where = ""
        params: list = []
        joins = ""
        if organization_id:
            joins = """
                JOIN robot_claims rc
                  ON rc.robot_id = robots.id
                 AND rc.organization_id = ?
                 AND rc.status = 'claimed'
            """
            params.append(organization_id)
        if status is not None:
            where = "WHERE robots.status = ?"
            params.append(status)

        cursor = await db.execute(
            f"SELECT COUNT(*) FROM robots {joins} {where}", tuple(params)
        )
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * limit
        cursor = await db.execute(
            f"SELECT robots.* FROM robots {joins} {where} ORDER BY robots.created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        rows = await cursor.fetchall()
        # Mask api_key in list responses
        result = []
        for row in rows:
            d = dict(row)
            if d.get("api_key"):
                d["has_api_key"] = True
                d["api_key_last4"] = d.get("api_key_last4") or d["api_key"][-4:]
                d["api_key"] = None
            else:
                d["has_api_key"] = False
                d["api_key_last4"] = None
            result.append(await _decorate_robot_with_claim(d))
        return result, total


async def get_robot(robot_id: str) -> Optional[dict]:
    """Get a single robot by ID."""
    async for db in get_db():
        cursor = await db.execute("SELECT * FROM robots WHERE id = ?", (robot_id,))
        row = await cursor.fetchone()
        return await _decorate_robot_with_claim(dict(row)) if row else None


async def get_robot_for_organization(organization_id: str, robot_id: str) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute(
            """SELECT r.*
               FROM robots r
               JOIN robot_claims rc ON rc.robot_id = r.id
               WHERE rc.organization_id = ? AND rc.status = 'claimed' AND r.id = ?
               ORDER BY rc.created_at DESC
               LIMIT 1""",
            (organization_id, robot_id),
        )
        row = await cursor.fetchone()
        return await _decorate_robot_with_claim(dict(row)) if row else None


async def get_claim_by_code(code: str) -> Optional[dict]:
    code_hash = _hash_claim_code(code)
    async for db in get_db():
        cursor = await db.execute(
            """SELECT rc.*, r.serial_number, r.firmware_version, r.maintenance_status,
                      r.issue_state, r.last_seen_at
               FROM robot_claims rc
               JOIN robots r ON r.id = rc.robot_id
               WHERE rc.claim_code_hash = ?
               LIMIT 1""",
            (code_hash,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_robot_claim(robot_id: str, created_by_user_id: str) -> tuple[dict, str]:
    robot = await get_robot(robot_id)
    if robot is None:
        raise ValueError("Robot not found")
    active_claim = await _get_active_claim_for_robot(robot_id)
    if active_claim and active_claim["status"] == "claimed":
        raise ValueError("Robot is already claimed")

    claim_id = str(uuid.uuid4())
    now = _now()
    raw_code = f"claim_{secrets.token_urlsafe(18)}"
    code_hash = _hash_claim_code(raw_code)

    async for db in get_db():
        await db.execute(
            """UPDATE robot_claims
               SET status = 'revoked', updated_at = ?
               WHERE robot_id = ? AND status = 'pending'""",
            (now, robot_id),
        )
        await db.execute(
            """INSERT INTO robot_claims
               (id, robot_id, claim_code_hash, status, commissioning_status, created_by_user_id, created_at, updated_at)
               VALUES (?, ?, ?, 'pending', 'unclaimed', ?, ?, ?)""",
            (claim_id, robot_id, code_hash, created_by_user_id, now, now),
        )
        await db.commit()

    claim = await get_claim_by_code(raw_code) or {}
    claim["claim_code"] = raw_code
    return claim, raw_code


async def claim_robot_for_organization(
    code: str,
    organization_id: str,
    user_id: str,
    *,
    friendly_name: str = "",
    deployment_notes: str = "",
) -> dict:
    now = _now()
    code_hash = _hash_claim_code(code)
    generated_key = None
    async for db in get_db():
        await db.execute("BEGIN IMMEDIATE")
        try:
            cursor = await db.execute(
                """SELECT * FROM robot_claims
                   WHERE claim_code_hash = ? AND status = 'pending'
                   LIMIT 1""",
                (code_hash,),
            )
            row = await cursor.fetchone()
            if not row:
                await db.execute("ROLLBACK")
                raise ValueError("Claim code is invalid or already used")
            claim = dict(row)

            cursor = await db.execute(
                """SELECT 1 FROM robot_claims
                   WHERE robot_id = ? AND status = 'claimed'
                   LIMIT 1""",
                (claim["robot_id"],),
            )
            if await cursor.fetchone():
                await db.execute("ROLLBACK")
                raise ValueError("Robot is already claimed")

            cursor = await db.execute("SELECT api_key FROM robots WHERE id = ?", (claim["robot_id"],))
            robot_row = await cursor.fetchone()
            if robot_row is None:
                await db.execute("ROLLBACK")
                raise ValueError("Robot not found")
            generated_key = None
            if not robot_row["api_key"]:
                generated_key = f"strk_{secrets.token_urlsafe(32)}"
                await db.execute(
                    "UPDATE robots SET api_key = ?, api_key_last4 = ?, updated_at = ? WHERE id = ?",
                    (_hash_api_key(generated_key), generated_key[-4:], now, claim["robot_id"]),
                )

            await db.execute(
                """UPDATE robot_claims
                   SET organization_id = ?, status = 'claimed', commissioning_status = 'commissioned',
                       friendly_name = ?, deployment_notes = ?, claimed_by_user_id = ?, claimed_at = ?,
                       commissioned_at = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    organization_id,
                    friendly_name,
                    deployment_notes,
                    user_id,
                    now,
                    now,
                    now,
                    claim["id"],
                ),
            )
            await db.execute("COMMIT")
        except ValueError:
            raise
        except Exception:
            await db.execute("ROLLBACK")
            raise

    claimed = await get_claim_by_code(code) or {}
    robot = await get_robot_for_organization(organization_id, claimed["robot_id"])
    if robot and generated_key is not None:
        robot["api_key"] = generated_key
    claimed["robot"] = robot
    if generated_key is not None:
        claimed["api_key"] = generated_key
    return claimed


async def list_claimed_robots(organization_id: str) -> list[dict]:
    items, _ = await list_robots(page=1, limit=500, organization_id=organization_id)
    return items


async def user_can_access_robot(user_id: str, robot_id: str) -> bool:
    assignment = await get_user_robot(user_id)
    if assignment and assignment["robot_id"] == robot_id:
        return True
    async for db in get_db():
        cursor = await db.execute(
            """SELECT 1
               FROM robot_claims rc
               JOIN memberships m ON m.organization_id = rc.organization_id
               WHERE rc.robot_id = ? AND rc.status = 'claimed'
                 AND m.user_id = ? AND m.status = 'active'
               LIMIT 1""",
            (robot_id, user_id),
        )
        return await cursor.fetchone() is not None
    return False


async def update_robot(
    robot_id: str,
    status: Optional[str] = None,
    firmware_version: Optional[str] = None,
    notes: Optional[str] = None,
    maintenance_status: Optional[str] = None,
    battery_health_pct: Optional[int] = None,
    service_due_at: Optional[str] = None,
    last_successful_mission_at: Optional[str] = None,
    issue_state: Optional[str] = None,
) -> Optional[dict]:
    """Partial update of a robot. Returns updated dict or None if not found."""
    fields: list[str] = []
    values: list[object] = []

    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if firmware_version is not None:
        fields.append("firmware_version = ?")
        values.append(firmware_version)
    if notes is not None:
        fields.append("notes = ?")
        values.append(notes)
    if maintenance_status is not None:
        fields.append("maintenance_status = ?")
        values.append(maintenance_status)
    if battery_health_pct is not None:
        fields.append("battery_health_pct = ?")
        values.append(battery_health_pct)
    if service_due_at is not None:
        fields.append("service_due_at = ?")
        values.append(service_due_at)
    if last_successful_mission_at is not None:
        fields.append("last_successful_mission_at = ?")
        values.append(last_successful_mission_at)
    if issue_state is not None:
        fields.append("issue_state = ?")
        values.append(issue_state)

    if not fields:
        return await get_robot(robot_id)

    fields.append("updated_at = ?")
    values.append(_now())
    values.append(robot_id)

    async for db in get_db():
        cursor = await db.execute(
            f"UPDATE robots SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return None

    return await get_robot(robot_id)


async def assign_robot(robot_id: str, user_id: str) -> Optional[dict]:
    """Create a new active assignment atomically.

    A robot may only have one non-returned assignment at a time, and each user may
    only have one active robot assignment at a time.
    """
    assignment_id = str(uuid.uuid4())
    now = _now()

    async for db in get_db():
        await db.execute("BEGIN IMMEDIATE")
        try:
            cursor = await db.execute("SELECT * FROM robots WHERE id = ?", (robot_id,))
            robot = await cursor.fetchone()
            if robot is None:
                await db.execute("ROLLBACK")
                return None

            if robot["status"] == "retired":
                raise RobotAssignmentConflict("Cannot assign a retired robot")

            cursor = await db.execute(
                """SELECT id FROM robot_assignments
                   WHERE robot_id = ? AND status != 'returned'
                   LIMIT 1""",
                (robot_id,),
            )
            if await cursor.fetchone():
                raise RobotAssignmentConflict("Robot is already assigned")

            cursor = await db.execute(
                """SELECT id FROM robot_assignments
                   WHERE user_id = ? AND status != 'returned'
                   LIMIT 1""",
                (user_id,),
            )
            if await cursor.fetchone():
                raise RobotAssignmentConflict("User already has an active robot assignment")

            await db.execute(
                """INSERT INTO robot_assignments
                   (id, robot_id, user_id, status, created_at, updated_at)
                   VALUES (?, ?, ?, 'preparing', ?, ?)""",
                (assignment_id, robot_id, user_id, now, now),
            )
            await db.execute(
                "UPDATE robots SET status = 'assigned', updated_at = ? WHERE id = ?",
                (now, robot_id),
            )
            await db.execute("COMMIT")
        except RobotAssignmentConflict:
            await db.execute("ROLLBACK")
            raise
        except Exception:
            await db.execute("ROLLBACK")
            raise

        cursor = await db.execute(
            "SELECT * FROM robot_assignments WHERE id = ?", (assignment_id,)
        )
        row = await cursor.fetchone()
        return dict(row)


async def get_user_robot(user_id: str) -> Optional[dict]:
    """Get the active robot assignment for a user (status NOT 'returned').

    JOINs with robots to include serial_number.
    Returns dict or None.
    """
    async for db in get_db():
        cursor = await db.execute(
            """SELECT ra.*, r.serial_number
               FROM robot_assignments ra
               JOIN robots r ON r.id = ra.robot_id
               WHERE ra.user_id = ? AND ra.status != 'returned'
               ORDER BY ra.created_at DESC
               LIMIT 1""",
            (user_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_latest_robot_telemetry(robot_id: str) -> Optional[dict]:
    """Get the latest telemetry row for a robot."""
    async for db in get_db():
        cursor = await db.execute(
            """SELECT battery_pct, lat, lng, state, paint_level_pct, error_code, rssi, created_at
               FROM robot_telemetry
               WHERE robot_id = ?
               ORDER BY created_at DESC
               LIMIT 1""",
            (robot_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_assignment(
    assignment_id: str,
    status: Optional[str] = None,
    tracking_number: Optional[str] = None,
    return_tracking: Optional[str] = None,
) -> Optional[dict]:
    """Partial update of an assignment with automatic timestamp handling.

    When status='shipped', sets shipped_at=now.
    When status='active', sets delivered_at=now.
    When status='returned', sets returned_at=now and sets robot status back to 'available'.
    Returns updated dict or None if not found.
    """
    fields: list[str] = []
    values: list[object] = []
    now = _now()

    if status is not None:
        fields.append("status = ?")
        values.append(status)
        if status == "shipped":
            fields.append("shipped_at = ?")
            values.append(now)
        elif status == "active":
            fields.append("delivered_at = ?")
            values.append(now)
        elif status == "returned":
            fields.append("returned_at = ?")
            values.append(now)

    if tracking_number is not None:
        fields.append("tracking_number = ?")
        values.append(tracking_number)
    if return_tracking is not None:
        fields.append("return_tracking = ?")
        values.append(return_tracking)

    if not fields:
        async for db in get_db():
            cursor = await db.execute(
                "SELECT * FROM robot_assignments WHERE id = ?", (assignment_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    fields.append("updated_at = ?")
    values.append(now)
    values.append(assignment_id)

    async for db in get_db():
        cursor = await db.execute(
            f"UPDATE robot_assignments SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return None

        # If returned, set robot back to available
        if status == "returned":
            cursor = await db.execute(
                "SELECT robot_id FROM robot_assignments WHERE id = ?",
                (assignment_id,),
            )
            row = await cursor.fetchone()
            if row:
                await db.execute(
                    "UPDATE robots SET status = 'available', updated_at = ? WHERE id = ?",
                    (now, row["robot_id"]),
                )
                await db.commit()

        cursor = await db.execute(
            "SELECT * FROM robot_assignments WHERE id = ?", (assignment_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def list_assignments(
    page: int = 1, limit: int = 50, status: Optional[str] = None
) -> tuple[list[dict], int]:
    """List assignments with robot serial_number and user email, paginated."""
    async for db in get_db():
        where = ""
        params: list = []
        if status is not None:
            where = "WHERE ra.status = ?"
            params.append(status)

        cursor = await db.execute(
            f"SELECT COUNT(*) FROM robot_assignments ra {where}", tuple(params)
        )
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * limit
        cursor = await db.execute(
            f"""SELECT ra.*, r.serial_number, u.email
                FROM robot_assignments ra
                JOIN robots r ON r.id = ra.robot_id
                JOIN users u ON u.id = ra.user_id
                {where}
                ORDER BY ra.created_at DESC
                LIMIT ? OFFSET ?""",
            (*params, limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows], total


async def get_robot_history(robot_id: str) -> list[dict]:
    """Get all assignments for a robot, newest first. JOINs with users for email."""
    async for db in get_db():
        cursor = await db.execute(
            """SELECT ra.*, u.email
               FROM robot_assignments ra
               JOIN users u ON u.id = ra.user_id
               WHERE ra.robot_id = ?
               ORDER BY ra.created_at DESC""",
            (robot_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def generate_api_key(robot_id: str, *, allow_rotate: bool = False) -> Optional[str]:
    """Generate a new API key for a robot atomically.

    Returns the raw key, or None if robot not found.
    If allow_rotate is False, raises ValueError when robot already has a key.
    If allow_rotate is True, replaces the existing key.
    """
    key = f"strk_{secrets.token_urlsafe(32)}"
    key_hash = _hash_api_key(key)
    last4 = key[-4:]
    now = _now()
    async for db in get_db():
        await db.execute("BEGIN IMMEDIATE")
        try:
            cursor = await db.execute("SELECT api_key FROM robots WHERE id = ?", (robot_id,))
            row = await cursor.fetchone()
            if row is None:
                await db.execute("ROLLBACK")
                return None
            if row["api_key"] and not allow_rotate:
                await db.execute("ROLLBACK")
                raise ValueError("Robot already has an API key")
            await db.execute(
                "UPDATE robots SET api_key = ?, api_key_last4 = ?, updated_at = ? WHERE id = ?",
                (key_hash, last4, now, robot_id),
            )
            await db.execute("COMMIT")
        except ValueError:
            raise
        except Exception:
            await db.execute("ROLLBACK")
            raise
    return key


async def clear_api_key(robot_id: str) -> bool:
    """Revoke a robot's API key. Returns True if key was cleared."""
    now = _now()
    async for db in get_db():
        cursor = await db.execute(
            "UPDATE robots SET api_key = NULL, api_key_last4 = NULL, updated_at = ? WHERE id = ? AND api_key IS NOT NULL",
            (now, robot_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def return_robot(assignment_id: str) -> Optional[dict]:
    """Set an assignment status to 'returning'. Returns updated dict or None."""
    now = _now()
    async for db in get_db():
        cursor = await db.execute(
            "UPDATE robot_assignments SET status = 'returning', updated_at = ? WHERE id = ?",
            (now, assignment_id),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return None

        cursor = await db.execute(
            "SELECT * FROM robot_assignments WHERE id = ?", (assignment_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
