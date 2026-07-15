"""
Keycloak JWT verifier.

Verifies RS256 access tokens issued by Keycloak using the realm's JWKS
(public keys). This replaces the previous insecure base64 decode that trusted
unsigned token payloads.

- Signature is verified against the realm JWKS (cached with TTL, refreshed on
  unknown key id to support key rotation).
- Issuer is verified against the configured public Keycloak issuer.
- Expiry is always enforced.
- Audience is enforced only when KEYCLOAK_AUDIENCE is configured.
- Authorized party (azp / client id) is enforced when KEYCLOAK_ALLOWED_AZP is set.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

import httpx
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError

from ..core.config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class KeycloakJWTVerifier:
    """Verifies Keycloak access tokens against the realm JWKS."""

    def __init__(self) -> None:
        self._jwks: Dict[str, Dict[str, Any]] = {}  # kid -> JWK
        self._jwks_fetched_at: float = 0.0
        self._lock = threading.Lock()

    def _cache_valid(self) -> bool:
        return bool(self._jwks) and (
            time.monotonic() - self._jwks_fetched_at
        ) < settings.JWKS_CACHE_TTL_SECONDS

    def _fetch_jwks(self, force: bool = False) -> None:
        if not force and self._cache_valid():
            return
        with self._lock:
            if not force and self._cache_valid():
                return
            url = settings.keycloak_jwks_url
            resp = httpx.get(url, timeout=5.0)
            resp.raise_for_status()
            keys = resp.json().get("keys", [])
            self._jwks = {k["kid"]: k for k in keys if "kid" in k}
            self._jwks_fetched_at = time.monotonic()
            logger.info("Fetched Keycloak JWKS", url=url, key_count=len(self._jwks))

    def _get_key(self, kid: str) -> Optional[Dict[str, Any]]:
        key = self._jwks.get(kid)
        if key is None:
            # Key id not found: keys may have rotated; force one refresh.
            try:
                self._fetch_jwks(force=True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("JWKS refresh failed", error=str(exc))
                return None
            key = self._jwks.get(kid)
        return key

    def verify(self, token: str) -> Optional[Dict[str, Any]]:
        """Return verified claims, or None if the token is invalid."""
        try:
            self._fetch_jwks()
        except Exception as exc:  # noqa: BLE001
            logger.error("Unable to fetch Keycloak JWKS", error=str(exc))
            return None

        try:
            header = jwt.get_unverified_header(token)
        except JWTError as exc:
            logger.warning("Malformed JWT header", error=str(exc))
            return None

        kid = header.get("kid")
        if not kid:
            logger.warning("JWT missing 'kid' header")
            return None

        key = self._get_key(kid)
        if key is None:
            logger.warning("No matching JWKS key for token", kid=kid)
            return None

        audience = [a.strip() for a in settings.KEYCLOAK_AUDIENCE.split(",") if a.strip()]
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=settings.keycloak_issuer,
                audience=audience or None,
                options={"verify_aud": bool(audience)},
            )
        except ExpiredSignatureError:
            logger.info("Rejected expired token")
            return None
        except (JWTClaimsError, JWTError) as exc:
            logger.warning("JWT verification failed", error=str(exc))
            return None

        allowed_azp = [a.strip() for a in settings.KEYCLOAK_ALLOWED_AZP.split(",") if a.strip()]
        if allowed_azp:
            azp = claims.get("azp")
            if azp and azp not in allowed_azp:
                logger.warning("Token authorized party not allowed", azp=azp)
                return None

        return claims


def claims_to_user(claims: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map verified Keycloak claims to the internal user dict shape."""
    user_id = claims.get("sub") or claims.get("email")
    if not user_id:
        return None
    return {
        "id": user_id,
        "email": claims.get("email"),
        "name": claims.get("name") or claims.get("preferred_username") or claims.get("email"),
        "given_name": claims.get("given_name"),
        "family_name": claims.get("family_name"),
        "preferred_username": claims.get("preferred_username"),
        "roles": (claims.get("realm_access") or {}).get("roles", []),
    }


# Global verifier instance
jwt_verifier = KeycloakJWTVerifier()
