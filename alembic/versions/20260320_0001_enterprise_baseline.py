"""Enterprise production baseline."""

from alembic import op

revision = "20260320_0001"
down_revision = None
branch_labels = None
depends_on = None


TABLE_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT DEFAULT '',
        plan TEXT DEFAULT 'free',
        active_lot_id TEXT,
        active_organization_id TEXT,
        map_lat DOUBLE PRECISION,
        map_lng DOUBLE PRECISION,
        map_zoom INTEGER,
        is_admin BOOLEAN DEFAULT FALSE,
        stripe_customer_id TEXT,
        company_name TEXT DEFAULT '',
        phone TEXT DEFAULT '',
        email_verified BOOLEAN DEFAULT FALSE,
        verification_token TEXT,
        verification_expires_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS organizations (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        personal BOOLEAN DEFAULT FALSE,
        created_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS memberships (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (organization_id, user_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS organization_invites (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        email TEXT NOT NULL,
        role TEXT NOT NULL,
        token_hash TEXT UNIQUE NOT NULL,
        status TEXT DEFAULT 'pending',
        invited_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
        accepted_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
        expires_at TEXT NOT NULL,
        accepted_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS lots (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        organization_id TEXT REFERENCES organizations(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        center_lat DOUBLE PRECISION NOT NULL,
        center_lng DOUBLE PRECISION NOT NULL,
        zoom INTEGER DEFAULT 18,
        features TEXT DEFAULT '[]',
        deleted_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sites (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        lot_id TEXT UNIQUE REFERENCES lots(id) ON DELETE SET NULL,
        name TEXT NOT NULL,
        address TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        customer_type TEXT DEFAULT 'mixed',
        status TEXT DEFAULT 'active',
        created_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS quotes (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        site_id TEXT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
        created_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
        title TEXT NOT NULL,
        cadence TEXT DEFAULT 'one-time',
        scope TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        status TEXT DEFAULT 'draft',
        proposed_price DOUBLE PRECISION DEFAULT 0,
        total_line_length_ft DOUBLE PRECISION DEFAULT 0,
        paint_gallons DOUBLE PRECISION DEFAULT 0,
        estimated_runtime_min INTEGER DEFAULT 0,
        estimated_cost DOUBLE PRECISION DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        organization_id TEXT REFERENCES organizations(id) ON DELETE CASCADE,
        site_id TEXT REFERENCES sites(id) ON DELETE SET NULL,
        lot_id TEXT NOT NULL REFERENCES lots(id) ON DELETE CASCADE,
        quote_id TEXT REFERENCES quotes(id) ON DELETE SET NULL,
        date TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        time_preference TEXT DEFAULT 'morning',
        scheduled_start_at TEXT,
        scheduled_end_at TEXT,
        assigned_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
        robot_id TEXT,
        recurring_schedule_id TEXT,
        started_at TEXT,
        completed_at TEXT,
        verified_at TEXT,
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS subscriptions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        stripe_customer_id TEXT,
        stripe_subscription_id TEXT,
        plan TEXT NOT NULL,
        status TEXT NOT NULL,
        current_period_end TEXT,
        cancel_at_period_end BOOLEAN DEFAULT FALSE,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS password_resets (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS waitlist (
        id BIGSERIAL PRIMARY KEY,
        email TEXT NOT NULL,
        source TEXT DEFAULT 'landing',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS login_attempts (
        email TEXT PRIMARY KEY,
        attempts INTEGER DEFAULT 0,
        locked_until TEXT,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS token_blocklist (
        jti TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS webhook_events (
        event_id TEXT PRIMARY KEY,
        processed_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id BIGSERIAL PRIMARY KEY,
        admin_email TEXT NOT NULL,
        action TEXT NOT NULL,
        target TEXT,
        detail TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS organization_audit_logs (
        id BIGSERIAL PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        actor_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
        action TEXT NOT NULL,
        target_type TEXT DEFAULT '',
        target_id TEXT DEFAULT '',
        detail_json TEXT DEFAULT '{}',
        created_at TEXT NOT NULL
    )
    """,
    """
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
    """,
    """
    CREATE TABLE IF NOT EXISTS robot_assignments (
        id TEXT PRIMARY KEY,
        robot_id TEXT NOT NULL REFERENCES robots(id) ON DELETE CASCADE,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS recurring_schedules (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        organization_id TEXT REFERENCES organizations(id) ON DELETE CASCADE,
        site_id TEXT REFERENCES sites(id) ON DELETE SET NULL,
        lot_id TEXT NOT NULL REFERENCES lots(id) ON DELETE CASCADE,
        frequency TEXT NOT NULL,
        day_of_week INTEGER,
        day_of_month INTEGER,
        time_preference TEXT DEFAULT 'morning',
        active BOOLEAN DEFAULT TRUE,
        next_run TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS job_estimates (
        id TEXT PRIMARY KEY,
        job_id TEXT UNIQUE NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        total_line_length_ft DOUBLE PRECISION,
        paint_gallons DOUBLE PRECISION,
        estimated_runtime_min INTEGER,
        estimated_cost DOUBLE PRECISION,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS robot_telemetry (
        id BIGSERIAL PRIMARY KEY,
        robot_id TEXT NOT NULL REFERENCES robots(id) ON DELETE CASCADE,
        battery_pct INTEGER,
        lat DOUBLE PRECISION,
        lng DOUBLE PRECISION,
        state TEXT,
        paint_level_pct INTEGER,
        error_code TEXT,
        rssi INTEGER,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS refresh_tokens (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS job_runs (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        site_id TEXT REFERENCES sites(id) ON DELETE SET NULL,
        job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        robot_id TEXT REFERENCES robots(id) ON DELETE SET NULL,
        technician_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
        status TEXT DEFAULT 'started',
        notes TEXT DEFAULT '',
        telemetry_summary TEXT DEFAULT '{}',
        actual_paint_gallons DOUBLE PRECISION,
        started_at TEXT,
        completed_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS media_assets (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        site_id TEXT REFERENCES sites(id) ON DELETE SET NULL,
        job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL,
        job_run_id TEXT REFERENCES job_runs(id) ON DELETE SET NULL,
        report_id TEXT,
        asset_type TEXT NOT NULL,
        filename TEXT NOT NULL,
        storage_backend TEXT DEFAULT 'local',
        storage_key TEXT NOT NULL,
        content_type TEXT DEFAULT 'application/octet-stream',
        size_bytes BIGINT DEFAULT 0,
        uploaded_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS job_reports (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        site_id TEXT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
        job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        job_run_id TEXT REFERENCES job_runs(id) ON DELETE SET NULL,
        status TEXT DEFAULT 'generated',
        report_json TEXT NOT NULL,
        pdf_asset_id TEXT REFERENCES media_assets(id) ON DELETE SET NULL,
        generated_at TEXT NOT NULL,
        created_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS maintenance_events (
        id TEXT PRIMARY KEY,
        robot_id TEXT NOT NULL REFERENCES robots(id) ON DELETE CASCADE,
        organization_id TEXT REFERENCES organizations(id) ON DELETE SET NULL,
        event_type TEXT NOT NULL,
        summary TEXT NOT NULL,
        details TEXT DEFAULT '',
        completed_at TEXT,
        created_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS service_checklists (
        id TEXT PRIMARY KEY,
        robot_id TEXT NOT NULL REFERENCES robots(id) ON DELETE CASCADE,
        organization_id TEXT REFERENCES organizations(id) ON DELETE SET NULL,
        name TEXT NOT NULL,
        checklist_json TEXT DEFAULT '[]',
        completed_at TEXT,
        created_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS consumables_inventory (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        sku TEXT NOT NULL,
        name TEXT NOT NULL,
        unit TEXT DEFAULT 'unit',
        on_hand DOUBLE PRECISION DEFAULT 0,
        reorder_level DOUBLE PRECISION DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS consumable_usage (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        consumable_item_id TEXT NOT NULL REFERENCES consumables_inventory(id) ON DELETE CASCADE,
        job_run_id TEXT REFERENCES job_runs(id) ON DELETE SET NULL,
        quantity DOUBLE PRECISION NOT NULL,
        notes TEXT DEFAULT '',
        created_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL
    )
    """,
]

INDEX_STATEMENTS = [
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
    "CREATE INDEX IF NOT EXISTS idx_sites_org ON sites(organization_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_quotes_org ON quotes(organization_id, site_id)",
    "CREATE INDEX IF NOT EXISTS idx_job_runs_job ON job_runs(job_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_media_assets_job ON media_assets(job_id, job_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_reports_job ON job_reports(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_maintenance_robot ON maintenance_events(robot_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_consumables_org ON consumables_inventory(organization_id)",
    "CREATE INDEX IF NOT EXISTS idx_invites_org_status ON organization_invites(organization_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_invites_token ON organization_invites(token_hash)",
    "CREATE INDEX IF NOT EXISTS idx_org_audit_org_created ON organization_audit_logs(organization_id, created_at)",
]


def upgrade() -> None:
    for statement in TABLE_STATEMENTS:
        op.execute(statement)
    for statement in INDEX_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in reversed(INDEX_STATEMENTS):
        index_name = statement.split(" IF NOT EXISTS ")[1].split(" ON ")[0]
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
    for table in [
        "consumable_usage",
        "consumables_inventory",
        "service_checklists",
        "maintenance_events",
        "job_reports",
        "media_assets",
        "job_runs",
        "refresh_tokens",
        "robot_telemetry",
        "job_estimates",
        "recurring_schedules",
        "robot_assignments",
        "robots",
        "organization_audit_logs",
        "audit_logs",
        "webhook_events",
        "token_blocklist",
        "login_attempts",
        "waitlist",
        "password_resets",
        "subscriptions",
        "jobs",
        "quotes",
        "sites",
        "lots",
        "organization_invites",
        "memberships",
        "organizations",
        "users",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table}")
