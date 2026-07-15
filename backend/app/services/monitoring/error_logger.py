"""
Structured Error Logger
Writes exceptions to error_logs table in Supabase
Usage:
    from app.services.monitoring.error_logger import log_error
    log_error(exc, service="upload", job_id=job_id, request=request)
"""

import traceback as tb
from typing import Optional, Dict, Any

from ...database.audit_models import ErrorLog
from ...utils.logging import get_logger

logger = get_logger(__name__)


def log_error(
    exc: Exception,
    service: str,
    db=None,
    job_id: Optional[str] = None,
    request=None,
    audit_context=None,
    severity: str = "ERROR",
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Write a structured error to error_logs table.
    Never raises — silently logs if the DB write itself fails.
    """
    if db is None:
        try:
            from ...database.session import get_db
            db = next(get_db())
            _close_db = True
        except Exception:
            logger.error(f"[{service}] {type(exc).__name__}: {exc}")
            return
    else:
        _close_db = False

    try:
        frame = tb.extract_tb(exc.__traceback__)
        last_frame = frame[-1] if frame else None

        ip_address = None
        endpoint = None
        method = None
        request_id = None
        correlation_id = None

        if request is not None:
            endpoint = str(request.url.path) if hasattr(request, "url") else None
            method = request.method if hasattr(request, "method") else None
            request_id = getattr(getattr(request, "state", None), "correlation_id", None)
            correlation_id = request_id

        if audit_context is not None:
            ip_address = audit_context.ip_address
            if not correlation_id:
                correlation_id = getattr(audit_context, "job_id", None)

        # Resolve tenant/user UUIDs
        tenant_uuid = None
        user_uuid = None
        if audit_context:
            try:
                from sqlalchemy import text
                if audit_context.tenant_id and audit_context.tenant_id != "default":
                    row = db.execute(
                        text("SELECT id FROM tenants WHERE tenant_id = :tid LIMIT 1"),
                        {"tid": audit_context.tenant_id}
                    ).fetchone()
                    if row:
                        tenant_uuid = row[0]
                if audit_context.user_id:
                    row = db.execute(
                        text("SELECT id FROM users WHERE user_id = :uid LIMIT 1"),
                        {"uid": audit_context.user_id}
                    ).fetchone()
                    if row:
                        user_uuid = row[0]
            except Exception:
                pass

        record = ErrorLog(
            error_type=type(exc).__name__,
            error_message=str(exc)[:2000],
            traceback="".join(tb.format_exception(type(exc), exc, exc.__traceback__))[:5000],
            service=service,
            module=last_frame.filename if last_frame else None,
            function_name=last_frame.name if last_frame else None,
            line_number=last_frame.lineno if last_frame else None,
            tenant_id=tenant_uuid,
            user_id=user_uuid,
            job_id=job_id,
            request_id=request_id,
            correlation_id=correlation_id,
            endpoint=endpoint,
            method=method,
            ip_address=ip_address,
            severity=severity,
            extra_data=metadata or {},
        )
        db.add(record)
        db.commit()

    except Exception as write_err:
        logger.error(f"error_logger: failed to write error_log: {write_err}")
    finally:
        if _close_db:
            try:
                db.close()
            except Exception:
                pass
