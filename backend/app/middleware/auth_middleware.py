"""
Authentication Middleware - Sets Audit Context Headers
Extracts user info from token and sets headers for AuditContextMiddleware
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
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
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
        
        if token:
            # Try to verify with Auth Service
            user_info = None
            try:
                token_data = await auth_client.verify_token(token)
                if token_data and token_data.get("valid"):
                    user_info = token_data.get("user")
            except Exception as e:
                logger.debug("Auth service verification failed", error=str(e))
            
            # Fallback to local decode
            if not user_info:
                user_info = _decode_bearer_payload(token)
            
            # Set audit context headers if user is authenticated
            if user_info:
                request.headers.__dict__["_list"] = [
                    (k, v) for k, v in request.headers.items()
                    if k.lower() not in ["x-tenant-id", "x-tenant-slug", "x-user-id", 
                                        "x-user-email", "x-user-name", "x-user-role",
                                        "x-session-id"]
                ]
                
                # Add user context headers
                request.headers.__dict__["_list"].extend([
                    ("X-Tenant-ID", "default"),
                    ("X-Tenant-Slug", "default"),
                    ("X-User-ID", user_info.get("id", "")),
                    ("X-User-Email", user_info.get("email", "")),
                    ("X-User-Name", user_info.get("name", "")),
                    ("X-User-Role", "admin" if "admin" in user_info.get("roles", []) else "USER"),
                    ("X-Session-ID", hashlib.sha256(token.encode()).hexdigest()),
                ])
                
                logger.debug(f"Set audit context headers for user: {user_info.get('id')}")
        
        # Process request
        response = await call_next(request)
        
        return response
