"""
Request Logger Middleware
Logs every API request to api_request_logs in Supabase
"""

import time
import traceback as tb
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from ..database.session import get_db
from ..database.audit_models import ApiRequestLog, ErrorLog
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Paths to skip (high-frequency noise)
SKIP_PATHS = {"/health", "/metrics", "/favicon.ico"}


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Logs every request to api_request_logs."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Skip noisy paths
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        start = time.monotonic()
        status_code = 500
        error_message = None
        error_code = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            error_message = str(exc)
            error_code = type(exc).__name__
            raise
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)

            # Extract audit context set by AuditContextMiddleware
            audit_ctx = getattr(request.state, "audit_context", None)

            try:
                db = next(get_db())

                # Resolve tenant/user UUIDs from audit context strings
                tenant_uuid = None
                user_uuid = None
                session_uuid = None

                if audit_ctx:
                    from sqlalchemy import text
                    if audit_ctx.tenant_id and audit_ctx.tenant_id != "default":
                        row = db.execute(
                            text("SELECT id FROM tenants WHERE tenant_id = :tid LIMIT 1"),
                            {"tid": audit_ctx.tenant_id}
                        ).fetchone()
                        if row:
                            tenant_uuid = row[0]

                    if audit_ctx.user_id:
                        row = db.execute(
                            text("SELECT id FROM users WHERE user_id = :uid LIMIT 1"),
                            {"uid": audit_ctx.user_id}
                        ).fetchone()
                        if row:
                            user_uuid = row[0]

                auth_type = getattr(request.state, "auth_type", None) or "jwt"
                api_key_id = getattr(request.state, "api_key_id", None)

                record = ApiRequestLog(
                    request_id=getattr(request.state, "correlation_id", None),
                    correlation_id=getattr(request.state, "correlation_id", None),
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    tenant_id=tenant_uuid,
                    user_id=user_uuid,
                    ip_address=audit_ctx.ip_address if audit_ctx else None,
                    user_agent=request.headers.get("user-agent"),
                    api_key_id=api_key_id,
                    auth_type=auth_type,
                    error_message=error_message,
                    error_code=error_code,
                )
                db.add(record)
                db.commit()
                db.close()

            except Exception as log_err:
                logger.debug(f"RequestLoggerMiddleware: failed to write log: {log_err}")
