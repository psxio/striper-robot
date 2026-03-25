#!/usr/bin/env python3
"""Database backup script: checkpoint WAL, gzip, upload to S3.

Supports both SQLite (via file copy) and PostgreSQL (via pg_dump).
Retains the last N days of backups (configurable via BACKUP_RETENTION_DAYS).

Usage:
    python scripts/backup_db.py

Required env vars:
    S3_BUCKET, S3_REGION, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY
Optional:
    DATABASE_URL (Postgres), DATABASE_PATH (SQLite, default: backend/data/strype.db)
    S3_ENDPOINT_URL (for S3-compatible services)
    BACKUP_RETENTION_DAYS (default: 30)
"""

import gzip
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path


def _get_s3_client():
    """Create boto3 S3 client from environment variables."""
    import boto3
    kwargs = {
        "region_name": os.environ.get("S3_REGION", "us-east-1"),
        "aws_access_key_id": os.environ["S3_ACCESS_KEY_ID"],
        "aws_secret_access_key": os.environ["S3_SECRET_ACCESS_KEY"],
    }
    endpoint = os.environ.get("S3_ENDPOINT_URL")
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client("s3", **kwargs)


def _backup_sqlite(db_path: str, output_path: str) -> None:
    """Checkpoint WAL and create a consistent copy of the SQLite database."""
    if not Path(db_path).exists():
        print(f"ERROR: SQLite file not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    # Checkpoint to flush WAL to main database file
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()

    # Copy the database file (WAL is now flushed)
    shutil.copy2(db_path, output_path)
    print(f"SQLite backup created: {output_path} ({Path(output_path).stat().st_size:,} bytes)")


def _backup_postgres(database_url: str, output_path: str) -> None:
    """Run pg_dump and save output to a file."""
    result = subprocess.run(
        ["pg_dump", "--format=custom", "--file", output_path, database_url],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: pg_dump failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"PostgreSQL backup created: {output_path} ({Path(output_path).stat().st_size:,} bytes)")


def _gzip_file(input_path: str, output_path: str) -> None:
    """Gzip a file."""
    with open(input_path, "rb") as f_in:
        with gzip.open(output_path, "wb", compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out)
    print(f"Compressed: {Path(output_path).stat().st_size:,} bytes")


def _upload_to_s3(s3_client, bucket: str, local_path: str, s3_key: str) -> None:
    """Upload a file to S3."""
    s3_client.upload_file(local_path, bucket, s3_key)
    print(f"Uploaded to s3://{bucket}/{s3_key}")


def _cleanup_old_backups(s3_client, bucket: str, prefix: str, retention_days: int) -> None:
    """Delete backup objects older than retention_days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    paginator = s3_client.get_paginator("list_objects_v2")
    deleted = 0

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["LastModified"].replace(tzinfo=timezone.utc) < cutoff:
                s3_client.delete_object(Bucket=bucket, Key=obj["Key"])
                deleted += 1

    if deleted:
        print(f"Cleaned up {deleted} backup(s) older than {retention_days} days")


def main():
    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        print("ERROR: S3_BUCKET not set", file=sys.stderr)
        sys.exit(1)

    database_url = os.environ.get("DATABASE_URL", "")
    database_path = os.environ.get("DATABASE_PATH", "backend/data/strype.db")
    retention_days = int(os.environ.get("BACKUP_RETENTION_DAYS", "30"))
    is_postgres = database_url.startswith("postgres")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    prefix = "backups/strype"

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = os.path.join(tmpdir, "strype_backup")
        gz_path = os.path.join(tmpdir, f"strype-{timestamp}.db.gz")

        if is_postgres:
            _backup_postgres(database_url, raw_path)
            s3_key = f"{prefix}/strype-{timestamp}.pgdump.gz"
        else:
            _backup_sqlite(database_path, raw_path)
            s3_key = f"{prefix}/strype-{timestamp}.db.gz"

        _gzip_file(raw_path, gz_path)

        s3 = _get_s3_client()
        _upload_to_s3(s3, bucket, gz_path, s3_key)
        _cleanup_old_backups(s3, bucket, prefix, retention_days)

    print(f"Backup complete: {s3_key}")


if __name__ == "__main__":
    main()
