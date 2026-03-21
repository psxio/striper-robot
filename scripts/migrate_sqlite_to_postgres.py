#!/usr/bin/env python
"""One-time migration utility from SQLite to PostgreSQL."""

from __future__ import annotations

import argparse
import asyncio
import os
import sqlite3
from pathlib import Path

import asyncpg


TABLE_ORDER = [
    "users",
    "organizations",
    "memberships",
    "organization_invites",
    "lots",
    "sites",
    "subscriptions",
    "password_resets",
    "login_attempts",
    "token_blocklist",
    "webhook_events",
    "audit_logs",
    "robots",
    "robot_assignments",
    "recurring_schedules",
    "job_estimates",
    "jobs",
    "refresh_tokens",
    "job_runs",
    "media_assets",
    "job_reports",
    "maintenance_events",
    "service_checklists",
    "consumables_inventory",
    "consumable_usage",
    "waitlist",
    "robot_telemetry",
    "organization_audit_logs",
]


def _postgres_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _sqlite_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return [row[1] for row in rows]


def _load_rows(connection: sqlite3.Connection, table: str) -> list[tuple]:
    return connection.execute(f"SELECT * FROM {table}").fetchall()


async def _copy_table(connection: sqlite3.Connection, pg: asyncpg.Connection, table: str) -> int:
    columns = _sqlite_columns(connection, table)
    rows = _load_rows(connection, table)
    if not rows:
        return 0
    column_list = ", ".join(columns)
    placeholders = ", ".join(f"${index}" for index in range(1, len(columns) + 1))
    await pg.executemany(
        f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})",
        rows,
    )
    return len(rows)


async def _reset_sequences(pg: asyncpg.Connection) -> None:
    for table, column in [
        ("waitlist", "id"),
        ("audit_logs", "id"),
        ("robot_telemetry", "id"),
        ("organization_audit_logs", "id"),
    ]:
        await pg.execute(
            f"SELECT setval(pg_get_serial_sequence('{table}', '{column}'), COALESCE((SELECT MAX({column}) FROM {table}), 1), true)"
        )


async def migrate(sqlite_path: Path, database_url: str) -> None:
    os.environ["DATABASE_URL"] = database_url
    from backend.postgres_runtime import run_migrations

    run_migrations()
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row
    pg = await asyncpg.connect(_postgres_url(database_url))
    try:
        async with pg.transaction():
            for table in reversed(TABLE_ORDER):
                await pg.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE')
            for table in TABLE_ORDER:
                count = await _copy_table(sqlite_conn, pg, table)
                print(f"{table}: {count} row(s)")
            await _reset_sequences(pg)
    finally:
        sqlite_conn.close()
        await pg.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate the Strype SQLite database to PostgreSQL.")
    parser.add_argument("--sqlite-path", default="backend/data/strype.db", help="Path to the source SQLite database")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""), help="Target PostgreSQL DATABASE_URL")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if not args.database_url:
        raise SystemExit("--database-url or DATABASE_URL is required")
    asyncio.run(migrate(Path(args.sqlite_path), args.database_url))
