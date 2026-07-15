"""
Authentication Routes - Session and Audit Logging
Integrates Keycloak authentication with Supabase audit system
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from user_agents import parse as parse_user_agent

from ...dependencies.auth import get_current_user_optional
from ...database.session import get_db
from ...services.audit.audit_service import AuditService
from ...services.audit.audit_context import AuditContext, AuditContextManager
from ...utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ips = forwarded_for.split(",")
        return ips[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    if request.client:
        return request.client.host
    
    return "unknown"


def _parse_user_agent(user_agent_string: str) -> Dict[str, Any]:
    """Parse user agent string into components"""
    parsed_ua = parse_user_agent(user_agent_string)
    
    return {
        "browser": parsed_ua.browser.family if parsed_ua else None,
        "os": parsed_ua.os.family if parsed_ua else None,
        "device_type": "mobile" if parsed_ua and parsed_ua.is_mobile else (
            "tablet" if parsed_ua and parsed_ua.is_tablet else (
                "desktop" if parsed_ua and parsed_ua.is_pc else "unknown"
            )
        )
    }


@router.post("/login")
async def record_login(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Record user login in audit system.
    Called by frontend after successful Keycloak authentication.
    Creates session and audit log entries.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_id = current_user.get("id")
    user_email = current_user.get("email")
    user_name = current_user.get("name")
    
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user data")
    
    # Extract request context
    ip_address = _get_client_ip(request)
    user_agent_string = request.headers.get("user-agent", "")
    ua_data = _parse_user_agent(user_agent_string)
    session_token = request.headers.get("Authorization", "").replace("Bearer ", "")
    
    # Initialize audit service
    audit_service = AuditService(db)
    
    try:
        # Ensure user exists in audit system
        user = audit_service.get_user_by_id(user_id)
        if not user:
            # Create user if not exists (using default tenant)
            audit_service.create_user(
                tenant_id="default",
                user_id=user_id,
                email=user_email,
                full_name=user_name,
                role="USER",
                auth_provider="KEYCLOAK",
                auth_provider_id=user_id
            )
            logger.info(f"Created audit user: {user_id}")
        
        # Update user login statistics
        audit_service.update_user_login(user_id, ip_address)
        
        # Create session
        session = audit_service.create_session(
            tenant_id="default",
            user_id=user_id,
            session_token=session_token,
            ip_address=ip_address,
            user_agent=user_agent_string,
            browser=ua_data["browser"],
            os=ua_data["os"],
            device_type=ua_data["device_type"]
        )
        
        # Create audit log for login event
        audit_service.create_audit_log(
            tenant_id="default",
            event_type="AUTHENTICATION",
            event_name="USER_LOGIN",
            user_id=user_id,
            session_id=session_token,
            event_category="AUTH",
            description=f"User logged in from {ip_address}",
            ip_address=ip_address,
            user_agent=user_agent_string,
            metadata={
                "browser": ua_data["browser"],
                "os": ua_data["os"],
                "device_type": ua_data["device_type"]
            },
            status="SUCCESS",
            severity="INFO"
        )
        
        logger.info(f"Recorded login for user: {user_id}, session: {session.id}")
        
        return {
            "message": "Login recorded successfully",
            "session_id": str(session.id),
            "user_id": user_id
        }
        
    except Exception as e:
        logger.error(f"Failed to record login: {e}", exc_info=True)
        # Don't fail the login if audit logging fails
        return {
            "message": "Login recorded (audit logging failed)",
            "user_id": user_id
        }


@router.post("/logout")
async def record_logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Record user logout in audit system.
    Called by frontend before or after Keycloak logout.
    Ends session and creates audit log entry.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_id = current_user.get("id")
    session_token = request.headers.get("Authorization", "").replace("Bearer ", "")
    
    if not session_token:
        raise HTTPException(status_code=400, detail="No session token provided")
    
    # Initialize audit service
    audit_service = AuditService(db)
    
    try:
        # End session
        session = audit_service.end_session(
            session_token=session_token,
            logout_reason="USER_LOGOUT"
        )
        
        # Create audit log for logout event
        audit_service.create_audit_log(
            tenant_id="default",
            event_type="AUTHENTICATION",
            event_name="USER_LOGOUT",
            user_id=user_id,
            session_id=session_token,
            event_category="AUTH",
            description="User logged out",
            status="SUCCESS",
            severity="INFO"
        )
        
        logger.info(f"Recorded logout for user: {user_id}")
        
        return {
            "message": "Logout recorded successfully",
            "user_id": user_id
        }
        
    except Exception as e:
        logger.error(f"Failed to record logout: {e}", exc_info=True)
        # Don't fail the logout if audit logging fails
        return {
            "message": "Logout recorded (audit logging failed)",
            "user_id": user_id
        }


@router.get("/session")
async def get_session_info(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Get current session information from audit system.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session_token = request.headers.get("Authorization", "").replace("Bearer ", "")
    
    if not session_token:
        raise HTTPException(status_code=400, detail="No session token provided")
    
    # Initialize audit service
    audit_service = AuditService(db)
    
    try:
        session = audit_service.get_active_session(session_token)
        
        if not session:
            return {
                "active": False,
                "message": "No active session found"
            }
        
        return {
            "active": True,
            "session_id": str(session.id),
            "login_time": session.login_time.isoformat() if session.login_time else None,
            "ip_address": session.ip_address,
            "browser": session.browser,
            "os": session.os,
            "device_type": session.device_type
        }
        
    except Exception as e:
        logger.error(f"Failed to get session info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve session information")
