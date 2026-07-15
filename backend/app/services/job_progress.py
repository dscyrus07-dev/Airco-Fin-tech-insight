"""
Publish live job progress (stage + hygiene details) into Redis job.result_data.

Frontend polls /api/jobs/{id} and reads result_data.progress.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..core.config import settings
from ..models.job import JobUpdate
from ..utils.logging import get_logger

logger = get_logger(__name__)

KEY_PREFIX = "airco:job:"


def _merge_progress_payload(
    existing: Dict[str, Any],
    *,
    stage: str,
    message: str = "",
    hygiene: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    progress = dict(existing.get("progress") or {})
    progress["stage"] = stage
    progress["message"] = message or progress.get("message") or ""
    progress["updated_at"] = datetime.now(timezone.utc).isoformat()
    if hygiene is not None:
        progress["hygiene"] = hygiene
        progress["hygiene_complete"] = True
    if extra:
        progress.update(extra)
    merged = dict(existing)
    merged["progress"] = progress
    return merged


def publish_job_progress_sync(
    job_id: str,
    *,
    stage: str,
    message: str = "",
    hygiene: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Synchronous progress publish (safe from parser threads / sync code)."""
    if not job_id:
        return
    try:
        import redis

        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        key = f"{KEY_PREFIX}{job_id}"
        raw = client.get(key)
        if not raw:
            # Still write a minimal progress blob so UI can show something if job lands later
            payload = {
                "id": job_id,
                "type": "pdf_processing",
                "status": "running",
                "correlation_id": job_id,
                "input_data": {},
                "result_data": _merge_progress_payload({}, stage=stage, message=message, hygiene=hygiene, extra=extra),
            }
            client.setex(key, 86400, json.dumps(payload, default=str))
            return

        try:
            job = json.loads(raw)
        except Exception:
            return

        result_data = job.get("result_data") or {}
        if not isinstance(result_data, dict):
            result_data = {}
        job["result_data"] = _merge_progress_payload(
            result_data,
            stage=stage,
            message=message,
            hygiene=hygiene,
            extra=extra,
        )
        if job.get("status") == "pending":
            job["status"] = "running"
        client.setex(key, 86400, json.dumps(job, default=str))
    except Exception as exc:
        logger.debug("publish_job_progress_sync failed", job_id=job_id, error=str(exc))


async def publish_job_progress(
    job_id: str,
    *,
    stage: str,
    message: str = "",
    hygiene: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Async progress publish via Redis job store."""
    if not job_id:
        return
    try:
        from .redis_job_store import redis_job_store

        job = await redis_job_store.get_job(job_id)
        existing = dict(job.result_data) if job and isinstance(job.result_data, dict) else {}
        payload = _merge_progress_payload(
            existing,
            stage=stage,
            message=message,
            hygiene=hygiene,
            extra=extra,
        )
        await redis_job_store.update_job(job_id, JobUpdate(result_data=payload))
    except Exception as exc:
        # Fall back to sync path
        logger.debug("async progress publish failed; using sync", job_id=job_id, error=str(exc))
        publish_job_progress_sync(
            job_id,
            stage=stage,
            message=message,
            hygiene=hygiene,
            extra=extra,
        )


def hygiene_result_to_progress(result: Any) -> Dict[str, Any]:
    """Normalize HygieneCheckResult (or dict) for frontend display."""
    if result is None:
        return {}
    if isinstance(result, dict):
        return {
            "is_healthy": bool(result.get("is_healthy", result.get("Is Healthy", True))),
            "file_name": result.get("file_name") or result.get("File Name") or "",
            "page_count": result.get("page_count") or result.get("No of Pages") or 0,
            "bank_name": result.get("bank_name") or result.get("Bank Name") or "unknown",
            "format_id": result.get("format_id") or result.get("Format ID") or "",
            "transaction_count": result.get("transaction_count") or result.get("No of Transactions") or 0,
            "start_date": result.get("start_date") or result.get("Start Date") or "N/A",
            "end_date": result.get("end_date") or result.get("End Date") or "N/A",
            "issues": result.get("issues") or result.get("Issues") or [],
            "warnings": result.get("warnings") or result.get("Warnings") or [],
        }

    return {
        "is_healthy": bool(getattr(result, "is_healthy", True)),
        "file_name": getattr(result, "file_name", "") or "",
        "page_count": int(getattr(result, "page_count", 0) or 0),
        "bank_name": getattr(result, "bank_name", "unknown") or "unknown",
        "format_id": getattr(result, "format_id", "") or "",
        "transaction_count": int(getattr(result, "transaction_count", 0) or 0),
        "start_date": getattr(result, "start_date", None) or "N/A",
        "end_date": getattr(result, "end_date", None) or "N/A",
        "issues": list(getattr(result, "issues", None) or []),
        "warnings": list(getattr(result, "warnings", None) or []),
    }
