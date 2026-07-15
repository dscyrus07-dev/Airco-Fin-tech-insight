"""
Keycloak token verification service for Auth Service.
"""

import json
import time
import httpx
import jwt
from typing import Dict, Any, Optional
from fastapi import HTTPException
from ..config import settings


class KeycloakTokenValidator:
    """Keycloak JWT token validation service."""
    
    def __init__(self):
        self.jwks_cache: Dict[str, Any] = {}
        self.jwks_cache_expiry: Optional[float] = None
        self.http_client = httpx.AsyncClient(timeout=10.0)
    
    async def get_jwks(self) -> Dict[str, Any]:
        """Get JSON Web Key Set from Keycloak."""
        # Check if cache is still valid (5 minutes)
        if (self.jwks_cache and self.jwks_cache_expiry and 
            self.jwks_cache_expiry > time.time()):
            return self.jwks_cache
        
        try:
            response = await self.http_client.get(settings.keycloak_jwks_url)
            response.raise_for_status()
            jwks = response.json()
            
            # Cache the JWKS
            self.jwks_cache = jwks
            self.jwks_cache_expiry = time.time() + 300  # 5 minutes
            
            return jwks
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=503, 
                detail=f"Failed to fetch JWKS from Keycloak: {str(e)}"
            )
    
    def get_key_from_jwks(self, token_header: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get public key from JWKS using key ID from token header."""
        kid = token_header.get('kid')
        if not kid:
            raise HTTPException(
                status_code=401, 
                detail="Token missing 'kid' header field"
            )
        
        jwks = self.jwks_cache
        if not jwks:
            raise HTTPException(
                status_code=503, 
                detail="JWKS not available"
            )
        
        for key in jwks.get('keys', []):
            if key.get('kid') == kid:
                return key
        
        raise HTTPException(
            status_code=401, 
            detail=f"Unable to find key with kid: {kid}"
        )
    
    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode Keycloak JWT token."""
        try:
            # Decode token header to get key ID
            unverified_header = jwt.get_unverified_header(token)
            
            # Get JWKS from Keycloak
            jwks = await self.get_jwks()
            
            # Find the matching key
            key = None
            for jwk in jwks.get('keys', []):
                if jwk.get('kid') == unverified_header.get('kid'):
                    key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
                    break
            
            if not key:
                raise HTTPException(
                    status_code=401, 
                    detail="Unable to find verification key"
                )
            
            # Verify and decode the token
            payload = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=settings.keycloak_issuer,
                options={
                    "verify_signature": True,
                    "verify_aud": False,
                    "verify_iss": True,
                    "verify_exp": True,
                    "verify_iat": True,
                }
            )
            
            # Validate required claims
            self._validate_required_claims(payload)
            self._validate_client_claims(payload)
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")
    
    def _validate_required_claims(self, payload: Dict[str, Any]) -> None:
        """Validate required claims in the token payload."""
        required_claims = ['sub', 'email', 'exp', 'iat']
        
        for claim in required_claims:
            if claim not in payload:
                raise HTTPException(
                    status_code=401, 
                    detail=f"Token missing required claim: {claim}"
                )
        
        # Validate token type (should be access token)
        if payload.get('typ') == 'refresh':
            raise HTTPException(
                status_code=401, 
                detail="Refresh tokens are not allowed for API access"
            )

    def _validate_client_claims(self, payload: Dict[str, Any]) -> None:
        """Accept standard Keycloak access-token client claims."""
        expected_client = settings.KEYCLOAK_CLIENT_ID
        audience = payload.get("aud")
        authorized_party = payload.get("azp")

        audience_values = audience if isinstance(audience, list) else [audience] if audience else []
        
        # For auth-service, accept tokens from both auth-service and frontend-app clients
        # This allows the auth-service to validate tokens from frontend login
        valid_clients = [expected_client, "frontend-app"]
        
        if any(client in audience_values for client in valid_clients) or authorized_party in valid_clients:
            return

        raise HTTPException(
            status_code=401,
            detail="Token was not issued for a valid client"
        )
    
    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()


# Global instance
keycloak_validator = KeycloakTokenValidator()
