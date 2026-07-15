"""
Authentication dependencies for Auth Service.
"""

import logging
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any

from ..services.keycloak_validator import keycloak_validator
from ..models.user import User

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> User:
    """
    Verify Keycloak token and return current user.
    
    Args:
        credentials: HTTP Authorization credentials containing Bearer token
        
    Returns:
        User: Authenticated user information
        
    Raises:
        HTTPException: If token is invalid or missing
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Verify the Keycloak token
        payload = await keycloak_validator.verify_token(credentials.credentials)
        
        # Create user object from token payload
        user = User(
            id=payload.get('sub'),
            email=payload.get('email'),
            name=payload.get('name') or payload.get('preferred_username'),
            given_name=payload.get('given_name'),
            family_name=payload.get('family_name'),
            preferred_username=payload.get('preferred_username'),
            roles=payload.get('realm_access', {}).get('roles', []),
        )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {str(e)}",
        )


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> User | None:
    """
    Optional authentication - returns user if token is valid, None otherwise.
    
    Args:
        credentials: HTTP Authorization credentials containing Bearer token
        
    Returns:
        User | None: Authenticated user information or None
    """
    if not credentials:
        logger.debug("get_current_user_optional: no credentials provided")
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException as e:
        logger.warning(f"get_current_user_optional: token validation failed - {e.status_code}: {e.detail}")
        return None


def has_required_role(user: User, required_role: str) -> bool:
    """
    Check if user has the required role.
    
    Args:
        user: Authenticated user
        required_role: Required role name
        
    Returns:
        bool: True if user has the required role
    """
    return required_role in user.roles


def require_role(required_role: str):
    """
    Dependency factory to require a specific role.
    
    Args:
        required_role: Required role name
        
    Returns:
        Dependency function that checks for the required role
    """
    async def role_dependency(current_user: User = Depends(get_current_user)) -> User:
        if not has_required_role(current_user, required_role):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required role: {required_role}"
            )
        return current_user
    
    return role_dependency


# Common role dependencies
require_user_role = require_role("user")
require_admin_role = require_role("admin")
require_analyst_role = require_role("analyst")
