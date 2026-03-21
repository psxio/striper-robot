"""Organization-scoped media asset persistence and downloads."""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..config import settings
from ..database import get_db
from . import storage_service


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row) -> dict:
    return dict(row)


def _bucket_for_asset_type(asset_type: str) -> Optional[str]:
    if asset_type == "report_pdf":
        return settings.S3_REPORTS_BUCKET or settings.S3_PRIVATE_BUCKET or settings.S3_BUCKET
    return settings.S3_PRIVATE_BUCKET or settings.S3_BUCKET


async def create_media_asset(
    organization_id: str,
    uploaded_by_user_id: str,
    asset_type: str,
    filename: str,
    content: bytes,
    *,
    content_type: str = "application/octet-stream",
    site_id: Optional[str] = None,
    job_id: Optional[str] = None,
    job_run_id: Optional[str] = None,
    report_id: Optional[str] = None,
) -> dict:
    asset_id = str(uuid.uuid4())
    now = _now()
    saved = await storage_service.save_bytes(
        content,
        filename,
        content_type=content_type,
        key_prefix=os.path.join(organization_id, asset_type),
        bucket=_bucket_for_asset_type(asset_type),
    )
    async for db in get_db():
        await db.execute(
            """INSERT INTO media_assets
               (id, organization_id, site_id, job_id, job_run_id, report_id, asset_type, filename,
                storage_backend, storage_key, content_type, size_bytes, uploaded_by_user_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                asset_id,
                organization_id,
                site_id,
                job_id,
                job_run_id,
                report_id,
                asset_type,
                filename,
                settings.OBJECT_STORAGE_BACKEND,
                saved["storage_key"],
                content_type,
                saved["size_bytes"],
                uploaded_by_user_id,
                now,
            ),
        )
        await db.commit()
    return await get_media_asset(organization_id, asset_id) or {}


async def get_media_asset(organization_id: str, asset_id: str) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM media_assets WHERE organization_id = ? AND id = ?",
            (organization_id, asset_id),
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def list_media_assets(
    organization_id: str,
    *,
    site_id: Optional[str] = None,
    job_id: Optional[str] = None,
    job_run_id: Optional[str] = None,
    report_id: Optional[str] = None,
    asset_type: Optional[str] = None,
) -> list[dict]:
    async for db in get_db():
        where = "WHERE organization_id = ?"
        params: list[object] = [organization_id]
        if site_id:
            where += " AND site_id = ?"
            params.append(site_id)
        if job_id:
            where += " AND job_id = ?"
            params.append(job_id)
        if job_run_id:
            where += " AND job_run_id = ?"
            params.append(job_run_id)
        if report_id:
            where += " AND report_id = ?"
            params.append(report_id)
        if asset_type:
            where += " AND asset_type = ?"
            params.append(asset_type)
        cursor = await db.execute(
            f"SELECT * FROM media_assets {where} ORDER BY created_at DESC",
            tuple(params),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(row) for row in rows]


async def read_media_asset(organization_id: str, asset_id: str) -> tuple[dict, bytes] | tuple[None, None]:
    asset = await get_media_asset(organization_id, asset_id)
    if not asset:
        return None, None
    content = await storage_service.read_bytes(
        asset["storage_key"],
        bucket=_bucket_for_asset_type(asset["asset_type"]),
    )
    return asset, content
