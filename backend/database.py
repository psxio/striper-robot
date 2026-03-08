"""Database initialization and connection management using aiosqlite."""

import os
from datetime import datetime, timezone

import aiosqlite

from .config import settings


async def get_db():
    """Async generator for database connections (for FastAPI Depends)."""
    db = await aiosqlite.connect(settings.DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    """Create tables if they don't exist."""
    os.makedirs(os.path.dirname(settings.DATABASE_PATH) or ".", exist_ok=True)
    async with aiosqlite.connect(settings.DATABASE_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT DEFAULT '',
                plan TEXT DEFAULT 'free',
                active_lot_id TEXT,
                map_lat REAL,
                map_lng REAL,
                map_zoom INTEGER,
                is_admin INTEGER DEFAULT 0,
                stripe_customer_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS lots (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                center_lat REAL NOT NULL,
                center_lng REAL NOT NULL,
                zoom INTEGER DEFAULT 18,
                features TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                lot_id TEXT NOT NULL,
                date TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (lot_id) REFERENCES lots(id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                plan TEXT NOT NULL,
                status TEXT NOT NULL,
                current_period_end TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS password_resets (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS waitlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                source TEXT DEFAULT 'landing',
                created_at TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                email TEXT PRIMARY KEY,
                attempts INTEGER DEFAULT 0,
                locked_until TEXT,
                updated_at TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS token_blocklist (
                jti TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS webhook_events (
                event_id TEXT PRIMARY KEY,
                processed_at TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_email TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT,
                detail TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # --- RaaS tables ---

        await db.execute("""
            CREATE TABLE IF NOT EXISTS robots (
                id TEXT PRIMARY KEY,
                serial_number TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'available',
                hardware_version TEXT DEFAULT 'v1',
                firmware_version TEXT,
                api_key TEXT,
                last_seen_at TEXT,
                last_battery_pct INTEGER,
                last_state TEXT,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS robot_assignments (
                id TEXT PRIMARY KEY,
                robot_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                status TEXT DEFAULT 'preparing',
                tracking_number TEXT,
                shipped_at TEXT,
                delivered_at TEXT,
                return_tracking TEXT,
                returned_at TEXT,
                label_url TEXT,
                return_label_url TEXT,
                ship_to_address TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (robot_id) REFERENCES robots(id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS recurring_schedules (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                lot_id TEXT NOT NULL,
                frequency TEXT NOT NULL,
                day_of_week INTEGER,
                day_of_month INTEGER,
                time_preference TEXT DEFAULT 'morning',
                active INTEGER DEFAULT 1,
                next_run TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (lot_id) REFERENCES lots(id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS job_estimates (
                id TEXT PRIMARY KEY,
                job_id TEXT UNIQUE NOT NULL,
                total_line_length_ft REAL,
                paint_gallons REAL,
                estimated_runtime_min INTEGER,
                estimated_cost REAL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS robot_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                robot_id TEXT NOT NULL,
                battery_pct INTEGER,
                lat REAL,
                lng REAL,
                state TEXT,
                paint_level_pct INTEGER,
                error_code TEXT,
                rssi INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (robot_id) REFERENCES robots(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # --- Indexes ---

        await db.execute("CREATE INDEX IF NOT EXISTS idx_lots_user ON lots(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_lot ON jobs(lot_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_subs_user ON subscriptions(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_subs_stripe ON subscriptions(stripe_subscription_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_resets_token ON password_resets(token_hash)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_blocklist_expires ON token_blocklist(expires_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user_lot ON jobs(user_id, lot_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_robot ON robot_telemetry(robot_id, created_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_assignments_user ON robot_assignments(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_assignments_robot ON robot_assignments(robot_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_schedules_user ON recurring_schedules(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_schedules_next ON recurring_schedules(active, next_run)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id)")

        # Cleanup expired password reset tokens and blocklist entries
        now = datetime.now(timezone.utc).isoformat()
        await db.execute("DELETE FROM password_resets WHERE expires_at < ?", (now,))
        await db.execute("DELETE FROM token_blocklist WHERE expires_at < ?", (now,))

        # Add soft-delete column to lots (idempotent)
        try:
            await db.execute("ALTER TABLE lots ADD COLUMN deleted_at TEXT")
        except Exception:
            pass

        # Index on deleted_at must come after the column is added
        await db.execute("CREATE INDEX IF NOT EXISTS idx_lots_user_deleted ON lots(user_id, deleted_at)")

        # --- Idempotent ALTER TABLE for RaaS columns ---
        _alters = [
            ("jobs", "time_preference TEXT DEFAULT 'morning'"),
            ("jobs", "started_at TEXT"),
            ("jobs", "completed_at TEXT"),
            ("jobs", "robot_id TEXT"),
            ("jobs", "recurring_schedule_id TEXT"),
            ("users", "company_name TEXT DEFAULT ''"),
            ("users", "phone TEXT DEFAULT ''"),
            ("users", "email_verified INTEGER DEFAULT 0"),
            ("users", "verification_token TEXT"),
            ("users", "verification_expires_at TEXT"),
            ("subscriptions", "cancel_at_period_end INTEGER DEFAULT 0"),
        ]
        for table, col_def in _alters:
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
            except Exception:
                pass

        await db.commit()
