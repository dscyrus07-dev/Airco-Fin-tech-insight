"""
Authentication routes for Auth Service.
"""

import httpx
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from ..config import settings
from ..models.user import User, UserInfo, TokenValidationResponse, UserLogin
from ..dependencies.auth import get_current_user, get_current_user_optional, require_user_role
from ..services.keycloak_validator import keycloak_validator
from ..utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


async def _request_keycloak_tokens(grant_type: str, payload: dict[str, str]) -> dict:
    token_url = f"{settings.KEYCLOAK_INTERNAL_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"

    form_data = {
        "grant_type": grant_type,
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        **payload,
    }

    if settings.KEYCLOAK_CLIENT_SECRET and not settings.KEYCLOAK_CLIENT_SECRET.startswith("<"):
        form_data["client_secret"] = settings.KEYCLOAK_CLIENT_SECRET

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            token_url,
            data=form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code != 200:
        try:
            error_detail = response.json()
        except Exception:
            error_detail = response.text

        logger.warning(
            "Keycloak token request failed",
            grant_type=grant_type,
            status_code=response.status_code,
        )
        raise HTTPException(
            status_code=401,
            detail=error_detail.get("error_description") if isinstance(error_detail, dict) and error_detail.get("error_description") else "Invalid credentials. Please try again.",
        )

    return response.json()

@router.get("/verify-token", response_model=TokenValidationResponse)
async def verify_token(current_user: Optional[User] = Depends(get_current_user_optional)):
    """Verify if token is valid and return user info."""
    if current_user:
        logger.info(f"Token verified OK for user: {current_user.email}")
        return TokenValidationResponse(
            valid=True,
            user=UserInfo(
                id=current_user.id,
                email=current_user.email,
                name=current_user.name,
                given_name=current_user.given_name,
                family_name=current_user.family_name,
                preferred_username=current_user.preferred_username,
                roles=current_user.roles
            )
        )
    else:
        logger.warning("verify-token called but no valid token was extracted from request")
        return TokenValidationResponse(
            valid=False,
            error="No valid token provided"
        )


@router.post("/verify-token", response_model=TokenValidationResponse)
async def verify_token_post(current_user: Optional[User] = Depends(get_current_user_optional)):
    """Verify if token is valid (POST variant for compatibility)."""
    return await verify_token(current_user)


@router.post("/login")
async def login(credentials: UserLogin):
    """Legacy password-grant login is disabled. Use the browser-based Keycloak flow instead."""
    raise HTTPException(
        status_code=410,
        detail="Legacy password-grant login is disabled. Use the browser-based Keycloak flow instead.",
    )


@router.post("/callback")
async def exchange_authorization_code(payload: dict[str, str]):
    """Exchange a browser-flow authorization code for tokens."""
    code = payload.get("code")
    redirect_uri = payload.get("redirect_uri")
    code_verifier = payload.get("code_verifier")

    if not code:
        raise HTTPException(status_code=400, detail="Authorization code is required")
    if not redirect_uri:
        raise HTTPException(status_code=400, detail="Redirect URI is required")

    token_payload: dict[str, str] = {
        "code": code,
        "redirect_uri": redirect_uri,
    }
    if code_verifier:
        token_payload["code_verifier"] = code_verifier

    return await _request_keycloak_tokens("authorization_code", token_payload)


@router.post("/refresh")
async def refresh_token(payload: dict[str, str]):
    """Refresh an access token through Keycloak."""
    refresh_token_value = payload.get("refresh_token")
    if not refresh_token_value:
        raise HTTPException(status_code=400, detail="Refresh token is required")

    return await _request_keycloak_tokens(
        "refresh_token",
        {
            "refresh_token": refresh_token_value,
        },
    )


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return UserInfo(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        given_name=current_user.given_name,
        family_name=current_user.family_name,
        preferred_username=current_user.preferred_username,
        roles=current_user.roles
    )

@router.get("/user-info")
async def get_user_info(current_user: User = Depends(require_user_role)):
    """Get detailed user information (requires user role)."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "given_name": current_user.given_name,
        "family_name": current_user.family_name,
        "preferred_username": current_user.preferred_username,
        "roles": current_user.roles,
        "has_user_role": "user" in current_user.roles,
        "has_admin_role": "admin" in current_user.roles,
        "has_analyst_role": "analyst" in current_user.roles
    }

@router.post("/logout")
async def logout():
    """Logout endpoint (for future token blacklisting implementation)."""
    # TODO: Implement token blacklisting with Redis if needed
    return {"message": "Logout successful"}

# Legacy endpoints for backward compatibility
@router.post("/register")
async def legacy_register():
    """Legacy register endpoint - redirects to Keycloak."""
    raise HTTPException(
        status_code=410, 
        detail="Legacy registration is deprecated. Use Keycloak for user management."
    )

@router.get("/users")
async def legacy_list_users():
    """Legacy users endpoint - use Keycloak for user management."""
    raise HTTPException(
        status_code=410, 
        detail="Legacy user management is deprecated. Use Keycloak for user management."
    )
