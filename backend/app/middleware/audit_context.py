"""
Audit Context Middleware - FastAPI Middleware
Extracts and sets audit context for every request
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging
from user_agents import parse as parse_user_agent
import ipaddress

from ..services.audit.audit_context import AuditContext, AuditContextManager

logger = logging.getLogger(__name__)


class AuditContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract and set audit context for every request
    Ensures user context is available throughout the request lifecycle
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        # Extract context from request
        context = self._extract_context(request)
        
        # Store in request state for dependency injection
        request.state.audit_context = context
        
        # Process request
        response = await call_next(request)
        
        # Add context headers to response (optional, for debugging)
        response.headers["X-Request-ID"] = context.correlation_id or "unknown"
        
        return response
    
    def _extract_context(self, request: Request) -> AuditContext:
        """Extract audit context from request"""
        # Get client IP
        ip_address = self._get_client_ip(request)
        
        # Parse user agent
        user_agent = request.headers.get("user-agent", "")
        parsed_ua = parse_user_agent(user_agent)
        
        # Extract from headers (set by authentication middleware)
        tenant_id = request.headers.get("X-Tenant-ID", "default")
        tenant_slug = request.headers.get("X-Tenant-Slug", "default")
        user_id = request.headers.get("X-User-ID", "anonymous")
        user_email = request.headers.get("X-User-Email", "anonymous@example.com")
        user_name = request.headers.get("X-User-Name")
        user_role = request.headers.get("X-User-Role", "USER")
        session_id = request.headers.get("X-Session-ID")
        session_token = request.headers.get("Authorization", "").replace("Bearer ", "")
        
        # Geographic data (from headers if available)
        country_code = request.headers.get("X-Country-Code")
        city = request.headers.get("X-City")
        
        # Generate correlation ID if not present
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            import uuid
            correlation_id = str(uuid.uuid4())
        
        # Create context
        context = AuditContext(
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            user_id=user_id,
            user_email=user_email,
            user_name=user_name,
            user_role=user_role,
            session_id=session_id,
            session_token=session_token,
            ip_address=ip_address,
            user_agent=user_agent,
            browser=parsed_ua.browser.family if parsed_ua else None,
            os=parsed_ua.os.family if parsed_ua else None,
            device_type=self._get_device_type(parsed_ua),
            country_code=country_code,
            city=city,
            correlation_id=correlation_id
        )
        
        logger.debug(f"Extracted audit context: {context.tenant_id}/{context.user_id}")
        return context
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request"""
        # Check for forwarded headers (proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, take the first one
            ips = forwarded_for.split(",")
            return ips[0].strip()
        
        # Check for real IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct connection
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _get_device_type(self, parsed_ua) -> str:
        """Determine device type from user agent"""
        if not parsed_ua:
            return "unknown"
        
        if parsed_ua.is_mobile:
            return "mobile"
        elif parsed_ua.is_tablet:
            return "tablet"
        elif parsed_ua.is_pc:
            return "desktop"
        elif parsed_ua.is_bot:
            return "bot"
        else:
            return "unknown"
