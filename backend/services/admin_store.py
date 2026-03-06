"""Admin persistence layer for platform management."""

from ..database import get_db


async def get_stats() -> dict:
    """Get platform-wide statistics."""
    async for db in get_db():
        stats = {}

        cursor = await db.execute("SELECT COUNT(*) FROM users")
        stats["users"] = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM lots")
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
               LEFT JOIN lots l ON l.user_id = u.id
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
