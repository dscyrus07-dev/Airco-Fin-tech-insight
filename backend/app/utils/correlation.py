"""
Correlation ID and Job Tracking utilities for microservices migration.
Provides request/job correlation across async processing.
"""

import uuid
from typing import Optional
from contextvars import ContextVar

# Context variable for correlation ID
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)

def get_correlation_id() -> str:
    """Get current correlation ID or generate a new one."""
    cid = correlation_id.get()
    if not cid:
        cid = str(uuid.uuid4())
        correlation_id.set(cid)
    return cid

def set_correlation_id(cid: str) -> None:
    """Set correlation ID for current context."""
    correlation_id.set(cid)

def generate_job_id() -> str:
    """Generate a unique job ID for async processing."""
    return str(uuid.uuid4())

def generate_request_id() -> str:
    """Generate a unique request ID."""
    return str(uuid.uuid4())
