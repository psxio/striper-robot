"""Object storage abstraction with local-disk default and optional S3 backend."""

import os
import uuid
from pathlib import Path
from typing import Optional

from ..config import settings


def _media_root() -> Path:
    root = Path(settings.MEDIA_STORAGE_PATH)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


async def save_bytes(
    content: bytes,
    filename: str,
    content_type: str = "application/octet-stream",
    key_prefix: str = "uploads",
    bucket: Optional[str] = None,
) -> dict:
    """Persist an uploaded object and return storage metadata."""
    ext = Path(filename).suffix
    key = f"{key_prefix}/{uuid.uuid4().hex}{ext}"

    if settings.OBJECT_STORAGE_BACKEND == "s3":
        try:
            import boto3

            client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL or None,
                aws_access_key_id=settings.S3_ACCESS_KEY_ID or None,
                aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY or None,
                region_name=settings.S3_REGION or None,
            )
            client.put_object(
                Bucket=bucket or settings.S3_PRIVATE_BUCKET or settings.S3_BUCKET,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
            return {"storage_backend": "s3", "storage_key": key, "size_bytes": len(content)}
        except ImportError as exc:
            raise RuntimeError("boto3 is required for s3 storage backend") from exc

    path = _media_root() / key
    _ensure_parent(path)
    path.write_bytes(content)
    return {"storage_backend": "local", "storage_key": key, "size_bytes": len(content)}


async def read_bytes(storage_key: str, *, bucket: Optional[str] = None) -> bytes:
    if settings.OBJECT_STORAGE_BACKEND == "s3":
        try:
            import boto3

            client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL or None,
                aws_access_key_id=settings.S3_ACCESS_KEY_ID or None,
                aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY or None,
                region_name=settings.S3_REGION or None,
            )
            obj = client.get_object(
                Bucket=bucket or settings.S3_PRIVATE_BUCKET or settings.S3_BUCKET,
                Key=storage_key,
            )
            return obj["Body"].read()
        except ImportError as exc:
            raise RuntimeError("boto3 is required for s3 storage backend") from exc

    path = _media_root() / storage_key
    return path.read_bytes()


async def delete_object(storage_key: str, *, bucket: Optional[str] = None) -> None:
    if settings.OBJECT_STORAGE_BACKEND == "s3":
        try:
            import boto3

            client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL or None,
                aws_access_key_id=settings.S3_ACCESS_KEY_ID or None,
                aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY or None,
                region_name=settings.S3_REGION or None,
            )
            client.delete_object(
                Bucket=bucket or settings.S3_PRIVATE_BUCKET or settings.S3_BUCKET,
                Key=storage_key,
            )
            return
        except ImportError as exc:
            raise RuntimeError("boto3 is required for s3 storage backend") from exc

    path = _media_root() / storage_key
    if path.exists():
        path.unlink()


def guess_filename(storage_key: str, original_filename: Optional[str] = None) -> str:
    if original_filename:
        return original_filename
    return os.path.basename(storage_key) or "download.bin"


async def check_storage_health() -> dict:
    """Validate that the configured object storage backend is reachable."""
    if settings.OBJECT_STORAGE_BACKEND == "s3":
        try:
            import boto3

            client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL or None,
                aws_access_key_id=settings.S3_ACCESS_KEY_ID or None,
                aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY or None,
                region_name=settings.S3_REGION or None,
            )
            bucket = settings.S3_PRIVATE_BUCKET or settings.S3_BUCKET
            if not bucket:
                raise RuntimeError("S3_PRIVATE_BUCKET is not configured")
            client.head_bucket(Bucket=bucket)
            report_bucket = settings.S3_REPORTS_BUCKET or bucket
            if report_bucket != bucket:
                client.head_bucket(Bucket=report_bucket)
            return {"backend": "s3", "bucket": bucket, "status": "ok"}
        except ImportError as exc:
            raise RuntimeError("boto3 is required for s3 storage backend") from exc

    root = _media_root()
    if not root.exists():
        raise RuntimeError("Local media storage path is not available")
    return {"backend": "local", "path": str(root), "status": "ok"}
