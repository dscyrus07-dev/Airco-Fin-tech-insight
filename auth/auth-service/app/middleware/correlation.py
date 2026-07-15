"""
Middleware to inject correlation ID into requests for Auth Service.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import uuid

from ..utils.logging import correlation_id

class CorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation ID to all requests."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract correlation ID from header or generate new one
        cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        correlation_id.set(cid)
        
        # Process request
        response = await call_next(request)
        
        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = cid
        
        return response
