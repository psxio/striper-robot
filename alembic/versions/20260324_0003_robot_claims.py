"""Add robot claim and commissioning tables."""

from alembic import op

revision = "20260324_0003"
down_revision = "20260323_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS robot_claims (
            id TEXT PRIMARY KEY,
            robot_id TEXT NOT NULL REFERENCES robots(id) ON DELETE CASCADE,
            organization_id TEXT REFERENCES organizations(id) ON DELETE SET NULL,
            claim_code_hash TEXT NOT NULL UNIQUE,
            status TEXT DEFAULT 'pending',
            commissioning_status TEXT DEFAULT 'unclaimed',
            friendly_name TEXT DEFAULT '',
            deployment_notes TEXT DEFAULT '',
            created_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            claimed_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            claimed_at TEXT,
            commissioned_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_robot_claims_robot ON robot_claims(robot_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_robot_claims_org ON robot_claims(organization_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_robot_claims_code ON robot_claims(claim_code_hash)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_robot_claims_code")
    op.execute("DROP INDEX IF EXISTS idx_robot_claims_org")
    op.execute("DROP INDEX IF EXISTS idx_robot_claims_robot")
    op.execute("DROP TABLE IF EXISTS robot_claims")
