"""
Authentication Middleware - Sets Audit Context Headers
Extracts user info from token and sets headers for AuditContextMiddleware
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp
import hashlib
import logging
import base64
import json

from ..core.config import settings
from ..services.auth_client import auth_client
from ..services.jwt_verifier import claims_to_user, jwt_verifier
from ..utils.logging import get_logger

logger = get_logger(__name__)

_AUDIT_HEADER_KEYS = {
    "x-tenant-id",
    "x-tenant-slug",
    "x-user-id",
    "x-user-email",
    "x-user-name",
    "x-user-role",
    "x-session-id",
    "x-auth-type",
    "x-api-key-id",
}


def _decode_bearer_payload(token: str):
    """Verify the token against Keycloak JWKS and return the user.

    Falls back to an unverified decode only when AUTH_ALLOW_INSECURE_FALLBACK
    is explicitly enabled (emergency/dev use only).
    """
    claims = jwt_verifier.verify(token)
    if claims:
        return claims_to_user(claims)

    if settings.AUTH_ALLOW_INSECURE_FALLBACK:
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return None
            payload = parts[1]
            padded = payload + "=" * (-len(payload) % 4)
            unsafe_claims = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
            logger.warning("AuthMiddleware using INSECURE unverified token decode")
            return claims_to_user(unsafe_claims)
        except Exception as exc:
            logger.debug("Insecure token decode failed", error=str(exc))
            return None

    return None


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract user info from token and set audit context headers.
    This runs before AuditContextMiddleware to ensure headers are available.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        api_key_header = request.headers.get("X-API-Key")

        # Platform API key path: resolve once, stash principal, set audit headers.
        # /api/v1/api-keys/* is JWT-only — never treat X-API-Key as sufficient there.
        if api_key_header and path.startswith("/api/v1/") and not path.startswith("/api/v1/api-keys"):
            # TODO: move SessionLocal to threadpool if API volume grows
            from ..database.session import SessionLocal
            from ..services.api_key_service import check_rate_limit, verify_key

            db = SessionLocal()
            try:
                record = verify_key(api_key_header, db)
                if record:
                    limit = record.rate_limit_per_minute or settings.API_KEY_RATE_LIMIT_DEFAULT
                    under_limit = await check_rate_limit(str(record.id), limit)
                    if not under_limit:
                        return JSONResponse(
                            status_code=429,
                            content={"detail": "Rate limit exceeded"},
                        )

                    owner_email = (getattr(record, "owner_email", None) or "").strip()
                    owner_name = (getattr(record, "owner_name", None) or "").strip()
                    principal = {
                        "id": record.user_id,
                        "email": owner_email,
                        "name": owner_name,
                        "preferred_username": owner_name,
                        "tenant_id": record.tenant_id or "default",
                        "auth_type": "api_key",
                        "scopes": record.scopes or [],
                        "roles": ["user"],
                        "api_key_id": str(record.id),
                        "key_prefix": record.key_prefix,
                    }
                    request.state.api_principal = principal
                    request.state.auth_type = "api_key"
                    request.state.api_key_id = str(record.id)

                    request.headers.__dict__["_list"] = [
                        (k, v)
                        for k, v in request.headers.items()
                        if k.lower() not in _AUDIT_HEADER_KEYS
                    ]
                    request.headers.__dict__["_list"].extend(
                        [
                            ("X-Tenant-ID", record.tenant_id or "default"),
                            ("X-Tenant-Slug", "default"),
                            ("X-User-ID", record.user_id or ""),
                            ("X-User-Email", owner_email),
                            ("X-User-Name", owner_name),
                            ("X-User-Role", "USER"),
                            ("X-Session-ID", ""),
                            ("X-Auth-Type", "api_key"),
                            ("X-Api-Key-Id", str(record.id)),
                        ]
                    )
                    logger.info(
                        "API key authenticated",
                        user_id=record.user_id,
                        key_prefix=record.key_prefix,
                        rate_limit=limit,
                        under_limit=under_limit,
                    )
            finally:
                db.close()

            return await call_next(request)

        # Existing JWT path
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None

        if token:
            user_info = None
            try:
                token_data = await auth_client.verify_token(token)
                if token_data and token_data.get("valid"):
                    user_info = token_data.get("user")
            except Exception as e:
                logger.debug("Auth service verification failed", error=str(e))

            if not user_info:
                user_info = _decode_bearer_payload(token)

            if user_info:
                request.state.auth_type = "jwt"
                request.state.api_key_id = None

                request.headers.__dict__["_list"] = [
                    (k, v)
                    for k, v in request.headers.items()
                    if k.lower() not in _AUDIT_HEADER_KEYS
                ]

                request.headers.__dict__["_list"].extend(
                    [
                        ("X-Tenant-ID", "default"),
                        ("X-Tenant-Slug", "default"),
                        ("X-User-ID", user_info.get("id", "")),
                        ("X-User-Email", user_info.get("email", "")),
                        ("X-User-Name", user_info.get("name", "")),
                        (
                            "X-User-Role",
                            "admin" if "admin" in user_info.get("roles", []) else "USER",
                        ),
                        ("X-Session-ID", hashlib.sha256(token.encode()).hexdigest()),
                        ("X-Auth-Type", "jwt"),
                    ]
                )

                logger.debug(f"Set audit context headers for user: {user_info.get('id')}")

        response = await call_next(request)
        return response
