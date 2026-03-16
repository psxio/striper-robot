"""Admin persistence layer for platform management."""

from datetime import datetime, timezone

from ..database import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_stats() -> dict:
    """Get platform-wide statistics in a single snapshot transaction."""
    async for db in get_db():
        await db.execute("BEGIN DEFERRED")
        stats = {}

        cursor = await db.execute("SELECT COUNT(*) FROM users")
        stats["users"] = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM lots WHERE deleted_at IS NULL")
        stats["lots"] = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM jobs")
        stats["jobs"] = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM waitlist")
        stats["waitlist"] = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT plan, COUNT(*) as count FROM users GROUP BY plan"
        )
        rows = await cursor.fetchall()
        stats["users_by_plan"] = {row["plan"]: row["count"] for row in rows}

        # Robot fleet stats
        cursor = await db.execute("SELECT COUNT(*) FROM robots")
        stats["robot_count"] = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM robots WHERE status = 'available'")
        stats["robots_available"] = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM robot_assignments WHERE status NOT IN ('returned')"
        )
        stats["active_assignments"] = (await cursor.fetchone())[0]

        await db.execute("COMMIT")
        return stats


async def list_users(page: int = 1, limit: int = 50) -> tuple[list[dict], int]:
    """List all users with lot/job counts, paginated."""
    async for db in get_db():
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * limit
        cursor = await db.execute(
            """SELECT u.id, u.email, u.name, u.plan, u.is_admin,
                      u.created_at, u.updated_at,
                      COUNT(DISTINCT l.id) as lot_count,
                      COUNT(DISTINCT j.id) as job_count
               FROM users u
               LEFT JOIN lots l ON l.user_id = u.id AND l.deleted_at IS NULL
               LEFT JOIN jobs j ON j.user_id = u.id
               GROUP BY u.id
               ORDER BY u.created_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        users = [dict(row) for row in rows]
        return users, total


async def list_waitlist(page: int = 1, limit: int = 50) -> tuple[list[dict], int]:
    """List all waitlist entries, paginated."""
    async for db in get_db():
        cursor = await db.execute("SELECT COUNT(*) FROM waitlist")
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * limit
        cursor = await db.execute(
            "SELECT * FROM waitlist ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows], total


async def set_admin(user_id: str, is_admin: bool = True) -> bool:
    """Set a user's admin status."""
    async for db in get_db():
        cursor = await db.execute(
            "UPDATE users SET is_admin = ? WHERE id = ?",
            (1 if is_admin else 0, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def log_audit(admin_email: str, action: str, target: str = "", detail: str = "") -> None:
    """Record an admin action in the audit log."""
    async for db in get_db():
        await db.execute(
            "INSERT INTO audit_logs (admin_email, action, target, detail, created_at) VALUES (?, ?, ?, ?, ?)",
            (admin_email, action, target, detail, _now()),
        )
        await db.commit()


async def list_audit_logs(page: int = 1, limit: int = 50) -> tuple[list[dict], int]:
    """List audit log entries, paginated (newest first)."""
    async for db in get_db():
        cursor = await db.execute("SELECT COUNT(*) FROM audit_logs")
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * limit
        cursor = await db.execute(
            "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows], total
