"""
Authentication dependencies for the monolith.
Supports Keycloak tokens via Auth Service during migration.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
import base64
import json

from ..core.config import settings
from ..services.auth_client import auth_client
from ..services.jwt_verifier import claims_to_user, jwt_verifier
from ..utils.logging import get_logger

logger = get_logger(__name__)
security = HTTPBearer(auto_error=False)


def _insecure_decode(token: str) -> Optional[Dict[str, Any]]:
    """UNVERIFIED token decode. Only used when AUTH_ALLOW_INSECURE_FALLBACK is on."""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1]
        padded = payload + "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
        return claims_to_user(claims)
    except Exception as exc:
        logger.debug("Insecure bearer decode failed", error=str(exc))
        return None


def _decode_bearer_payload(token: str) -> Optional[Dict[str, Any]]:
    """Verify the token signature against Keycloak JWKS and return the user.

    Falls back to an unverified decode only if AUTH_ALLOW_INSECURE_FALLBACK is
    explicitly enabled (emergency/dev use only).
    """
    claims = jwt_verifier.verify(token)
    if claims:
        return claims_to_user(claims)

    if settings.AUTH_ALLOW_INSECURE_FALLBACK:
        logger.warning("Using INSECURE unverified token decode (AUTH_ALLOW_INSECURE_FALLBACK=on)")
        return _insecure_decode(token)

    return None

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    """Get current user from token (optional)."""
    if not credentials:
        return None
    
    # Try to verify with Auth Service (now Keycloak-enabled)
    user_info = await auth_client.verify_token(credentials.credentials)
    if user_info and user_info.get("valid"):
        return user_info.get("user")

    # Fallback for direct Keycloak login flow used by the frontend.
    fallback_user = _decode_bearer_payload(credentials.credentials)
    if fallback_user:
        return fallback_user
    
    # If Auth Service fails, this is an optional dependency so return None
    return None

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """Get current user from token (required)."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Try to verify with Auth Service (now Keycloak-enabled)
    token_data = await auth_client.verify_token(credentials.credentials)
    if token_data and token_data.get("valid"):
        user = token_data.get("user")
        if user:
            return user

    fallback_user = _decode_bearer_payload(credentials.credentials)
    if fallback_user:
        return fallback_user
    
    # If Auth Service verification fails, raise error
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

async def get_admin_user(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get current user and verify admin role."""
    user_roles = current_user.get("roles", [])
    
    if "admin" not in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return current_user

def has_required_role(user: Dict[str, Any], required_role: str) -> bool:
    """
    Check if user has the required role.
    
    Args:
        user: Authenticated user
        required_role: Required role name
        
    Returns:
        bool: True if user has the required role
    """
    user_roles = user.get("roles", [])
    return required_role in user_roles

def require_role(required_role: str):
    """
    Dependency factory to require a specific role.
    
    Args:
        required_role: Required role name
        
    Returns:
        Dependency function that checks for the required role
    """
    async def role_dependency(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if not has_required_role(current_user, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}"
            )
        return current_user
    
    return role_dependency

# Common role dependencies
require_user_role = require_role("user")
require_admin_role = require_role("admin")

def check_user_ownership(resource_user_id: str, current_user: Dict[str, Any]) -> bool:
    """
    Check if the current user owns the resource.
    
    Args:
        resource_user_id: User ID of the resource owner
        current_user: Current authenticated user
        
    Returns:
        bool: True if user owns the resource or is admin
    """
    # Admin can access all resources
    if has_required_role(current_user, "admin"):
        return True
    
    # Users can only access their own resources
    return resource_user_id == current_user.get("id")

def require_ownership(resource_user_id: str):
    """
    Dependency factory to require resource ownership.
    
    Args:
        resource_user_id: User ID of the resource owner
        
    Returns:
        Dependency function that checks for ownership
    """
    async def ownership_dependency(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if not check_user_ownership(resource_user_id, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only access your own resources"
            )
        return current_user
    
    return ownership_dependency

# Legacy JWT verification (for backward compatibility)
async def verify_legacy_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify legacy JWT token."""
    try:
        # This would use the old JWT verification logic
        # Legacy JWT verification - implement as needed
        return None
    except Exception:
        return None
