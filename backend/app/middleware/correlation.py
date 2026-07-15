"""
Middleware to inject correlation ID into requests.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable

from ..utils.correlation import set_correlation_id, generate_request_id

class CorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation ID to all requests."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract correlation ID from header or generate new one
        correlation_id = request.headers.get("X-Correlation-ID") or generate_request_id()
        set_correlation_id(correlation_id)
        
        # Process request
        response = await call_next(request)
        
        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        
        return response
