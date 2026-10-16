"""Hard-delete of statement-derived data past the retention window.

The file-history sweeper already removes S3 objects and marks user_file_records
deleted. This module removes the audit/extraction rows that carry statement
content or object keys, and stale files in the temp directory.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict

from sqlalchemy import delete

from ..core.config import settings
from ..database.audit_models import (
    ApiRequestLog,
    DownloadLog,
    ErrorLog,
    JobEvent,
    ProcessingJob,
    RawTransaction,
    ReportGenerationLog,
    StatementMetadata,
)
from ..database.session import SessionLocal
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Children first; each entry is (model, timestamp column name).
_PURGE_ORDER = (
    (RawTransaction, "created_at"),
    (JobEvent, "created_at"),
    (ReportGenerationLog, "created_at"),
    (DownloadLog, "created_at"),
    (StatementMetadata, "created_at"),
    (ProcessingJob, "created_at"),
    (ApiRequestLog, "request_at"),
    (ErrorLog, "occurred_at"),
)


def purge_database(retention_days: int | None = None) -> Dict[str, int]:
    """Delete rows older than the retention window. Returns table -> rows removed."""
    days = retention_days if retention_days is not None else settings.DATA_RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    removed: Dict[str, int] = {}
    db = SessionLocal()
    try:
        for model, column in _PURGE_ORDER:
            col = getattr(model, column)
            try:
                result = db.execute(delete(model).where(col < cutoff))
                db.commit()
                removed[model.__tablename__] = int(result.rowcount or 0)
            except Exception as exc:  # one table failing must not stop the rest
                db.rollback()
                removed[model.__tablename__] = -1
                logger.warning("Retention DB purge failed", table=model.__tablename__, error=type(exc).__name__)
    finally:
        db.close()
    return removed


def purge_temp_dir(max_age_hours: int | None = None) -> int:
    """Remove staged uploads / generated reports older than the temp-file age limit."""
    hours = max_age_hours if max_age_hours is not None else settings.TEMP_FILE_MAX_AGE_HOURS
    root = os.path.abspath(settings.TEMP_DIR)
    if not os.path.isdir(root):
        return 0
    cutoff = time.time() - hours * 3600
    deleted = 0
    for entry in os.scandir(root):
        try:
            if entry.is_file(follow_symlinks=False) and entry.stat().st_mtime < cutoff:
                os.unlink(entry.path)
                deleted += 1
        except OSError:
            continue
    return deleted
