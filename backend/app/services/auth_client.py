"""
Auth client — verifies JWTs via Keycloak JWKS.

Optional remote auth-service HTTP path is only used when AUTH_SERVICE_URL is set
to a non-localhost URL (microservices mode). Monolith deploys skip that hop.
"""

from typing import Optional, Dict, Any
from urllib.parse import urlparse

import httpx

from ..core.config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


def _is_remote_auth_service(url: str) -> bool:
    """True only when AUTH_SERVICE_URL points at a real remote service."""
    raw = (url or "").strip()
    if not raw:
        return False
    try:
        host = (urlparse(raw).hostname or "").lower()
    except Exception:
        return False
    return host not in {"", "localhost", "127.0.0.1", "::1"}


class AuthClient:
    """Token verification via Keycloak JWKS (optional remote auth-service)."""

    def __init__(self):
        self.base_url = (settings.AUTH_SERVICE_URL or "").strip()
        self.timeout = 3.0
        self._use_remote = _is_remote_auth_service(self.base_url)

    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT. Prefer local JWKS; optionally try remote auth-service first."""
        if self._use_remote:
            remote = await self._remote_verify_token(token)
            if remote is not None:
                return remote
        return await self._jwks_verify_token(token)

    async def _remote_verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Optional HTTP verify against a dedicated auth microservice."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url.rstrip('/')}/auth/verify-token",
                    headers={"Authorization": f"Bearer {token}"},
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.debug(
                        "Token verified via auth-service",
                        user=(result.get("user") or {}).get("email"),
                    )
                    return result
                if response.status_code == 401:
                    logger.warning("Auth service returned 401 for token verification")
                    return None
                logger.warning(
                    "Auth service token verification failed",
                    status=response.status_code,
                )
                return None
        except Exception as e:
            logger.debug("Auth service unreachable; using JWKS", error=str(e))
            return None

    async def _jwks_verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify token directly via Keycloak JWKS."""
        try:
            from .jwt_verifier import jwt_verifier, claims_to_user

            claims = jwt_verifier.verify(token)
            if claims:
                user = claims_to_user(claims)
                return {"valid": True, "user": user} if user else None
            return None
        except Exception as e:
            logger.debug("JWKS token verification failed", error=str(e))
            return None

    async def get_user_info(self, token: str) -> Optional[Dict[str, Any]]:
        """Resolve user from token (JWKS). Remote /auth/me only if configured."""
        if self._use_remote:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        f"{self.base_url.rstrip('/')}/auth/me",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if response.status_code == 200:
                        return response.json()
            except Exception as e:
                logger.debug("Auth service /me unreachable; using JWKS", error=str(e))

        verified = await self._jwks_verify_token(token)
        if verified and verified.get("valid"):
            return verified.get("user")
        return None


# Global auth client instance
auth_client = AuthClient()
