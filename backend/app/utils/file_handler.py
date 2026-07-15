import os
import uuid
import logging
import tempfile
import time
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def _is_transient_minio_error(exc: Exception) -> bool:
    transient_names = {
        "ConnectionResetError",
        "ConnectionClosedError",
        "EndpointConnectionError",
        "ReadTimeoutError",
        "ConnectTimeoutError",
    }
    return isinstance(exc, (ConnectionResetError, TimeoutError)) or exc.__class__.__name__ in transient_names


def get_temp_dir() -> str:
    """Get or create temporary directory for file processing."""
    temp_dir = os.path.abspath(settings.TEMP_DIR)
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def save_temp_file(content: bytes, extension: str = ".pdf") -> str:
    """Save bytes content to a uniquely named temp file. Returns file path."""
    temp_dir = get_temp_dir()
    filename = f"{uuid.uuid4().hex}{extension}"
    file_path = os.path.join(temp_dir, filename)

    with open(file_path, "wb") as f:
        f.write(content)

    logger.info(f"Temp file saved: {filename} ({len(content)} bytes)")
    return file_path


def cleanup_file(file_path: str) -> None:
    """Safely delete a file."""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up: {os.path.basename(file_path)}")
    except OSError as e:
        logger.warning(f"Failed to clean up {file_path}: {e}")


def cleanup_files(*file_paths: str) -> None:
    """Safely delete multiple files."""
    for path in file_paths:
        if path:
            cleanup_file(path)


def _s3_client():
    """Shared S3 client for MinIO or Supabase S3 protocol."""
    import boto3
    from botocore.client import Config as BotoConfig

    return boto3.client(
        "s3",
        endpoint_url=settings.MINIO_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": getattr(settings, "S3_ADDRESSING_STYLE", "path") or "path"},
        ),
        region_name=getattr(settings, "S3_REGION", None) or "us-east-1",
    )


def upload_to_minio(local_path: str, bucket: str, object_key: str = None) -> bool:
    """
    Upload a local file to object storage (MinIO / Supabase S3).
    Returns True on success, False on any failure (non-blocking).
    """
    try:
        client = _s3_client()

        # Local MinIO may auto-create buckets; Supabase buckets are pre-created.
        if not getattr(settings, "S3_SKIP_CREATE_BUCKET", False):
            try:
                client.head_bucket(Bucket=bucket)
            except Exception:
                client.create_bucket(Bucket=bucket)
                logger.info("Created storage bucket: %s", bucket)

        if object_key is None:
            object_key = os.path.basename(local_path)

        _, ext = os.path.splitext(local_path)
        content_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if ext.lower() == ".xlsx"
            else "application/pdf"
        )

        for attempt in range(3):
            try:
                client.upload_file(
                    local_path, bucket, object_key,
                    ExtraArgs={"ContentType": content_type},
                )
                logger.info("Storage upload OK: %s → %s/%s", local_path, bucket, object_key)
                return True
            except Exception as exc:
                if attempt < 2 and _is_transient_minio_error(exc):
                    logger.warning(
                        "Storage upload transient failure; retrying",
                        extra={
                            "bucket": bucket,
                            "object_key": object_key,
                            "attempt": attempt + 1,
                            "error": str(exc),
                        },
                    )
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise

    except Exception as e:
        logger.warning("Storage upload failed (non-fatal): %s", str(e))
        return False


def delete_from_minio(bucket: str, object_key: str) -> bool:
    """
    Delete an object from storage.
    Returns True on success, False on any failure (non-blocking).
    """
    if not bucket or not object_key:
        return False

    try:
        client = _s3_client()
        client.delete_object(Bucket=bucket, Key=object_key)
        logger.info("Storage delete OK: %s/%s", bucket, object_key)
        return True

    except Exception as e:
        logger.warning("Storage delete failed (non-fatal): %s", str(e))
        return False


def download_from_minio(bucket: str, object_key: str, local_path: str = None) -> Optional[str]:
    """
    Download an object from storage to a local file.
    Returns the local file path on success, None on failure.
    """
    if not bucket or not object_key:
        return None

    try:
        client = _s3_client()

        if local_path is None:
            temp_dir = get_temp_dir()
            local_path = os.path.join(temp_dir, os.path.basename(object_key))

        for attempt in range(3):
            try:
                client.download_file(bucket, object_key, local_path)
                logger.info("Storage download OK: %s/%s → %s", bucket, object_key, local_path)
                return local_path
            except Exception as exc:
                if attempt < 2 and _is_transient_minio_error(exc):
                    logger.warning(
                        "Storage download transient failure; retrying",
                        extra={
                            "bucket": bucket,
                            "object_key": object_key,
                            "attempt": attempt + 1,
                            "error": str(exc),
                        },
                    )
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise

    except Exception as e:
        logger.warning("Storage download failed: %s", str(e))
        return None

