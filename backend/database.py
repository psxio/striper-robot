"""Database initialization and connection management using aiosqlite."""

import logging
import os
import re
from datetime import datetime, timezone

import aiosqlite

from .config import settings
from .postgres_runtime import check_connection, get_postgres_db, is_postgres, run_migrations

logger = logging.getLogger("strype.database")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "workspace"


async def _sqlite_get_db():
    """Async generator for database connections (for FastAPI Depends)."""
    db = await aiosqlite.connect(settings.DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=5000")
    try:
        yield db
    finally:
        await db.close()


async def _sqlite_init_db():
    """Create tables if they don't exist and backfill commercial-core data."""
    os.makedirs(os.path.dirname(settings.DATABASE_PATH) or ".", exist_ok=True)
    async with aiosqlite.connect(settings.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA busy_timeout=5000")
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
                active_organization_id TEXT,
                map_lat REAL,
                map_lng REAL,
                map_zoom INTEGER,
                is_admin INTEGER DEFAULT 0,
                stripe_customer_id TEXT,
                company_name TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                email_verified INTEGER DEFAULT 0,
                verification_token TEXT,
                verification_expires_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                personal INTEGER DEFAULT 0,
                created_by_user_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (created_by_user_id) REFERENCES users(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS memberships (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (organization_id, user_id),
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS organization_invites (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                email TEXT NOT NULL,
                role TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                status TEXT DEFAULT 'pending',
                invited_by_user_id TEXT NOT NULL,
                accepted_by_user_id TEXT,
                accepted_at TEXT,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (invited_by_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (accepted_by_user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS organization_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id TEXT NOT NULL,
                actor_user_id TEXT,
                action TEXT NOT NULL,
                target_type TEXT,
                target_id TEXT,
                detail_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS lots (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                organization_id TEXT,
                name TEXT NOT NULL,
                center_lat REAL NOT NULL,
                center_lng REAL NOT NULL,
                zoom INTEGER DEFAULT 18,
                features TEXT DEFAULT '[]',
                deleted_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS sites (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                lot_id TEXT UNIQUE,
                name TEXT NOT NULL,
                address TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                customer_type TEXT DEFAULT 'mixed',
                status TEXT DEFAULT 'active',
                created_by_user_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (lot_id) REFERENCES lots(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by_user_id) REFERENCES users(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS quotes (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                site_id TEXT NOT NULL,
                created_by_user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                cadence TEXT DEFAULT 'one-time',
                scope TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                status TEXT DEFAULT 'draft',
                proposed_price REAL DEFAULT 0,
                total_line_length_ft REAL DEFAULT 0,
                paint_gallons REAL DEFAULT 0,
                estimated_runtime_min INTEGER DEFAULT 0,
                estimated_cost REAL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
                FOREIGN KEY (created_by_user_id) REFERENCES users(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                organization_id TEXT,
                site_id TEXT,
                lot_id TEXT NOT NULL,
                quote_id TEXT,
                date TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                time_preference TEXT DEFAULT 'morning',
                scheduled_start_at TEXT,
                scheduled_end_at TEXT,
                assigned_user_id TEXT,
                robot_id TEXT,
                recurring_schedule_id TEXT,
                started_at TEXT,
                completed_at TEXT,
                verified_at TEXT,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE SET NULL,
                FOREIGN KEY (lot_id) REFERENCES lots(id) ON DELETE CASCADE,
                FOREIGN KEY (quote_id) REFERENCES quotes(id) ON DELETE SET NULL,
                FOREIGN KEY (assigned_user_id) REFERENCES users(id) ON DELETE SET NULL
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
                cancel_at_period_end INTEGER DEFAULT 0,
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

        await db.execute("""
            CREATE TABLE IF NOT EXISTS robots (
                id TEXT PRIMARY KEY,
                serial_number TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'available',
                hardware_version TEXT DEFAULT 'v1',
                firmware_version TEXT,
                api_key TEXT,
                api_key_last4 TEXT,
                last_seen_at TEXT,
                last_battery_pct INTEGER,
                last_state TEXT,
                maintenance_status TEXT DEFAULT 'ready',
                battery_health_pct INTEGER,
                service_due_at TEXT,
                last_successful_mission_at TEXT,
                issue_state TEXT DEFAULT '',
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
                organization_id TEXT,
                site_id TEXT,
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
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE SET NULL,
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

        await db.execute("""
            CREATE TABLE IF NOT EXISTS job_runs (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                site_id TEXT,
                job_id TEXT NOT NULL,
                robot_id TEXT,
                technician_user_id TEXT,
                status TEXT DEFAULT 'started',
                notes TEXT DEFAULT '',
                telemetry_summary TEXT DEFAULT '{}',
                actual_paint_gallons REAL,
                started_at TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE SET NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
                FOREIGN KEY (robot_id) REFERENCES robots(id) ON DELETE SET NULL,
                FOREIGN KEY (technician_user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS media_assets (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                site_id TEXT,
                job_id TEXT,
                job_run_id TEXT,
                report_id TEXT,
                asset_type TEXT NOT NULL,
                filename TEXT NOT NULL,
                storage_backend TEXT DEFAULT 'local',
                storage_key TEXT NOT NULL,
                content_type TEXT DEFAULT 'application/octet-stream',
                size_bytes INTEGER DEFAULT 0,
                uploaded_by_user_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE SET NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL,
                FOREIGN KEY (job_run_id) REFERENCES job_runs(id) ON DELETE SET NULL,
                FOREIGN KEY (uploaded_by_user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS job_reports (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                site_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                job_run_id TEXT,
                status TEXT DEFAULT 'generated',
                report_json TEXT NOT NULL,
                pdf_asset_id TEXT,
                generated_at TEXT NOT NULL,
                created_by_user_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
                FOREIGN KEY (job_run_id) REFERENCES job_runs(id) ON DELETE SET NULL,
                FOREIGN KEY (pdf_asset_id) REFERENCES media_assets(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS maintenance_events (
                id TEXT PRIMARY KEY,
                robot_id TEXT NOT NULL,
                organization_id TEXT,
                event_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                details TEXT DEFAULT '',
                completed_at TEXT,
                created_by_user_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (robot_id) REFERENCES robots(id) ON DELETE CASCADE,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS service_checklists (
                id TEXT PRIMARY KEY,
                robot_id TEXT NOT NULL,
                organization_id TEXT,
                name TEXT NOT NULL,
                checklist_json TEXT DEFAULT '[]',
                completed_at TEXT,
                created_by_user_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (robot_id) REFERENCES robots(id) ON DELETE CASCADE,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS consumables_inventory (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                sku TEXT NOT NULL,
                name TEXT NOT NULL,
                unit TEXT DEFAULT 'unit',
                on_hand REAL DEFAULT 0,
                reorder_level REAL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS consumable_usage (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                consumable_item_id TEXT NOT NULL,
                job_run_id TEXT,
                quantity REAL NOT NULL,
                notes TEXT DEFAULT '',
                created_by_user_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (consumable_item_id) REFERENCES consumables_inventory(id) ON DELETE CASCADE,
                FOREIGN KEY (job_run_id) REFERENCES job_runs(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_lots_user ON lots(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_lots_org ON lots(organization_id)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_org ON jobs(organization_id, site_id)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_lot ON jobs(lot_id)",
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
            "CREATE INDEX IF NOT EXISTS idx_subs_user ON subscriptions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_subs_stripe ON subscriptions(stripe_subscription_id)",
            "CREATE INDEX IF NOT EXISTS idx_resets_token ON password_resets(token_hash)",
            "CREATE INDEX IF NOT EXISTS idx_blocklist_expires ON token_blocklist(expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_user_lot ON jobs(user_id, lot_id)",
            "CREATE INDEX IF NOT EXISTS idx_telemetry_robot ON robot_telemetry(robot_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_assignments_user ON robot_assignments(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_assignments_robot ON robot_assignments(robot_id)",
            "CREATE INDEX IF NOT EXISTS idx_schedules_user ON recurring_schedules(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_schedules_next ON recurring_schedules(active, next_run)",
            "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_assignments_robot_status ON robot_assignments(robot_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_memberships_user ON memberships(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_memberships_org ON memberships(organization_id)",
            "CREATE INDEX IF NOT EXISTS idx_org_invites_org ON organization_invites(organization_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_org_invites_email ON organization_invites(email, status)",
            "CREATE INDEX IF NOT EXISTS idx_org_invites_token ON organization_invites(token_hash)",
            "CREATE INDEX IF NOT EXISTS idx_org_audit_org ON organization_audit_logs(organization_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_sites_org ON sites(organization_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_quotes_org ON quotes(organization_id, site_id)",
            "CREATE INDEX IF NOT EXISTS idx_job_runs_job ON job_runs(job_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_media_assets_job ON media_assets(job_id, job_run_id)",
            "CREATE INDEX IF NOT EXISTS idx_reports_job ON job_reports(job_id)",
            "CREATE INDEX IF NOT EXISTS idx_maintenance_robot ON maintenance_events(robot_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_consumables_org ON consumables_inventory(organization_id)",
            "CREATE INDEX IF NOT EXISTS idx_lots_user_deleted ON lots(user_id, deleted_at)",
        ]
        for statement in indexes:
            await db.execute(statement)

        now = datetime.now(timezone.utc).isoformat()
        await db.execute("DELETE FROM password_resets WHERE expires_at < ?", (now,))
        await db.execute("DELETE FROM token_blocklist WHERE expires_at < ?", (now,))

        alters = [
            ("users", "active_organization_id TEXT"),
            ("users", "company_name TEXT DEFAULT ''"),
            ("users", "phone TEXT DEFAULT ''"),
            ("users", "email_verified INTEGER DEFAULT 0"),
            ("users", "verification_token TEXT"),
            ("users", "verification_expires_at TEXT"),
            ("lots", "organization_id TEXT"),
            ("lots", "deleted_at TEXT"),
            ("jobs", "organization_id TEXT"),
            ("jobs", "site_id TEXT"),
            ("jobs", "quote_id TEXT"),
            ("jobs", "time_preference TEXT DEFAULT 'morning'"),
            ("jobs", "scheduled_start_at TEXT"),
            ("jobs", "scheduled_end_at TEXT"),
            ("jobs", "assigned_user_id TEXT"),
            ("jobs", "started_at TEXT"),
            ("jobs", "completed_at TEXT"),
            ("jobs", "robot_id TEXT"),
            ("jobs", "recurring_schedule_id TEXT"),
            ("jobs", "verified_at TEXT"),
            ("jobs", "notes TEXT DEFAULT ''"),
            ("subscriptions", "cancel_at_period_end INTEGER DEFAULT 0"),
            ("robots", "api_key_last4 TEXT"),
            ("robots", "maintenance_status TEXT DEFAULT 'ready'"),
            ("robots", "battery_health_pct INTEGER"),
            ("robots", "service_due_at TEXT"),
            ("robots", "last_successful_mission_at TEXT"),
            ("robots", "issue_state TEXT DEFAULT ''"),
            ("recurring_schedules", "organization_id TEXT"),
            ("recurring_schedules", "site_id TEXT"),
        ]
        for table, col_def in alters:
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
            except aiosqlite.OperationalError:
                pass

        # Backfill personal organizations and active organization pointers.
        cursor = await db.execute("SELECT id, email, name, active_organization_id FROM users")
        users = await cursor.fetchall()
        for user in users:
            cursor = await db.execute(
                "SELECT organization_id FROM memberships WHERE user_id = ? ORDER BY created_at ASC LIMIT 1",
                (user["id"],),
            )
            membership = await cursor.fetchone()
            org_id = membership["organization_id"] if membership else None
            if not org_id:
                base_name = (user["name"] or user["email"].split("@", 1)[0]).strip() or "Workspace"
                slug_base = _slugify(f"{base_name}-workspace")
                slug = slug_base
                counter = 1
                while True:
                    cursor = await db.execute("SELECT 1 FROM organizations WHERE slug = ?", (slug,))
                    if not await cursor.fetchone():
                        break
                    counter += 1
                    slug = f"{slug_base}-{counter}"
                org_id = f"org_{user['id'].replace('-', '')[:24]}"
                membership_id = f"mem_{user['id'].replace('-', '')[:24]}"
                await db.execute(
                    """INSERT OR IGNORE INTO organizations
                       (id, name, slug, personal, created_by_user_id, created_at, updated_at)
                       VALUES (?, ?, ?, 1, ?, ?, ?)""",
                    (org_id, f"{base_name} Workspace", slug, user["id"], now, now),
                )
                await db.execute(
                    """INSERT OR IGNORE INTO memberships
                       (id, organization_id, user_id, role, status, created_at, updated_at)
                       VALUES (?, ?, ?, 'owner', 'active', ?, ?)""",
                    (membership_id, org_id, user["id"], now, now),
                )
            if org_id and not user["active_organization_id"]:
                await db.execute(
                    "UPDATE users SET active_organization_id = ? WHERE id = ?",
                    (org_id, user["id"]),
                )

        await db.execute(
            """UPDATE lots
               SET organization_id = (
                   SELECT u.active_organization_id FROM users u WHERE u.id = lots.user_id
               )
               WHERE organization_id IS NULL"""
        )

        cursor = await db.execute(
            "SELECT id, organization_id, user_id, name, created_at, updated_at FROM lots WHERE organization_id IS NOT NULL"
        )
        lots = await cursor.fetchall()
        for lot in lots:
            cursor = await db.execute("SELECT id FROM sites WHERE lot_id = ?", (lot["id"],))
            if await cursor.fetchone():
                continue
            site_id = f"site_{lot['id'].replace('-', '')[:24]}"
            await db.execute(
                """INSERT OR IGNORE INTO sites
                   (id, organization_id, lot_id, name, created_by_user_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (site_id, lot["organization_id"], lot["id"], lot["name"], lot["user_id"], lot["created_at"], lot["updated_at"]),
            )

        await db.execute(
            """UPDATE jobs
               SET organization_id = (
                   SELECT l.organization_id FROM lots l WHERE l.id = jobs.lot_id
               )
               WHERE organization_id IS NULL"""
        )
        await db.execute(
            """UPDATE jobs
               SET site_id = (
                   SELECT s.id FROM sites s WHERE s.lot_id = jobs.lot_id
               )
               WHERE site_id IS NULL"""
        )
        await db.execute(
            """UPDATE recurring_schedules
               SET organization_id = (
                   SELECT l.organization_id FROM lots l WHERE l.id = recurring_schedules.lot_id
               )
               WHERE organization_id IS NULL"""
        )
        await db.execute(
            """UPDATE recurring_schedules
               SET site_id = (
                   SELECT s.id FROM sites s WHERE s.lot_id = recurring_schedules.lot_id
               )
               WHERE site_id IS NULL"""
        )

        await db.commit()


async def get_db():
    """Async generator for database connections."""
    if is_postgres():
        async for db in get_postgres_db():
            yield db
        return
    async for db in _sqlite_get_db():
        yield db


async def init_db():
    """Initialize the configured database backend."""
    if is_postgres():
        run_migrations()
        await check_connection()
        logger.info("PostgreSQL migrations applied successfully")
        return
    await _sqlite_init_db()
