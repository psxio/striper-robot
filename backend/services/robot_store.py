"""Robot fleet management persistence layer using aiosqlite."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from ..database import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RobotAssignmentConflict(ValueError):
    """Raised when a robot assignment would violate active-assignment rules."""


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
    page: int = 1, limit: int = 50, status: Optional[str] = None
) -> tuple[list[dict], int]:
    """List robots with optional status filter, paginated."""
    async for db in get_db():
        where = ""
        params: list = []
        if status is not None:
            where = "WHERE status = ?"
            params.append(status)

        cursor = await db.execute(
            f"SELECT COUNT(*) FROM robots {where}", tuple(params)
        )
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * limit
        cursor = await db.execute(
            f"SELECT * FROM robots {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows], total


async def get_robot(robot_id: str) -> Optional[dict]:
    """Get a single robot by ID."""
    async for db in get_db():
        cursor = await db.execute("SELECT * FROM robots WHERE id = ?", (robot_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_robot(
    robot_id: str,
    status: Optional[str] = None,
    firmware_version: Optional[str] = None,
    notes: Optional[str] = None,
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
