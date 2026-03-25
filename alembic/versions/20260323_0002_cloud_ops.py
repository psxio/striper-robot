"""Add cloud site scan and simulation tables."""

from alembic import op

revision = "20260323_0002"
down_revision = "20260320_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS site_scans (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            site_id TEXT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            lot_id TEXT REFERENCES lots(id) ON DELETE SET NULL,
            source_media_asset_id TEXT REFERENCES media_assets(id) ON DELETE SET NULL,
            scan_type TEXT NOT NULL,
            notes TEXT DEFAULT '',
            summary_json TEXT DEFAULT '{}',
            geometry_snapshot_json TEXT DEFAULT '[]',
            captured_at TEXT NOT NULL,
            created_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS simulation_runs (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            site_id TEXT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            scan_id TEXT REFERENCES site_scans(id) ON DELETE SET NULL,
            work_order_id TEXT REFERENCES jobs(id) ON DELETE SET NULL,
            robot_id TEXT REFERENCES robots(id) ON DELETE SET NULL,
            status TEXT DEFAULT 'ready',
            mode TEXT DEFAULT 'preview',
            notes TEXT DEFAULT '',
            config_json TEXT DEFAULT '{}',
            result_json TEXT DEFAULT '{}',
            created_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_site_scans_site ON site_scans(site_id, captured_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_simulation_runs_site ON simulation_runs(site_id, created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_simulation_runs_site")
    op.execute("DROP INDEX IF EXISTS idx_site_scans_site")
    op.execute("DROP TABLE IF EXISTS simulation_runs")
    op.execute("DROP TABLE IF EXISTS site_scans")
