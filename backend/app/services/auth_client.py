"""
Auth Service client for monolith to communicate with Auth Service.
"""

import httpx
from typing import Optional, Dict, Any
from fastapi import HTTPException

from ..core.config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)

class AuthClient:
    """Client for communicating with Auth Service."""
    
    def __init__(self):
        self.base_url = settings.AUTH_SERVICE_URL or "http://localhost:8001"
        self.timeout = 10.0
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token with Auth Service."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/auth/verify-token",
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info("Token verified successfully via auth-service", user=result.get("user", {}).get("email"))
                    return result
                elif response.status_code == 401:
                    logger.warning("Auth service returned 401 for token verification")
                    return None
                else:
                    logger.error("Token verification failed", status=response.status_code, detail=response.text)
                    return None
                    
        except Exception as e:
            logger.error("Auth service connection failed", error=str(e))
            # During migration, fall back to legacy verification
            return await self._legacy_verify_token(token)
    
    async def _legacy_verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify token directly via Keycloak JWKS when auth-service is unreachable."""
        try:
            from .jwt_verifier import jwt_verifier, claims_to_user
            claims = jwt_verifier.verify(token)
            if claims:
                user = claims_to_user(claims)
                return {"valid": True, "user": user} if user else None
            return None
        except Exception as e:
            logger.debug("JWKS token verification failed in legacy fallback", error=str(e))
            return None
    
    async def get_user_info(self, token: str) -> Optional[Dict[str, Any]]:
        """Get user information from Auth Service."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/auth/me",
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return None
                    
        except Exception as e:
            logger.error("Failed to get user info", error=str(e))
            return None

# Global auth client instance
auth_client = AuthClient()
