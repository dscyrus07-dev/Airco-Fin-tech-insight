"""
Logging utilities for Auth Service.
"""

import logging
import json
from datetime import datetime
from typing import Any, Dict

# Context variable for correlation ID
try:
    from contextvars import ContextVar
    correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')
except ImportError:
    # Fallback for older Python versions
    class ContextVar:
        def __init__(self, name, default=''):
            self.name = name
            self.default = default
            self._value = default
        
        def get(self):
            return self._value
        
        def set(self, value):
            self._value = value
    
    correlation_id = ContextVar('correlation_id', default='')

class StructuredLogger:
    """Structured JSON logger with correlation ID support."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def _log(self, level: int, message: str, **kwargs):
        """Log with structured data including correlation ID."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": logging.getLevelName(level),
            "message": message,
            "correlation_id": correlation_id.get(),
            "service": "auth-service",
            **kwargs
        }
        self.logger.log(level, json.dumps(log_data))
    
    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)

def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    return StructuredLogger(name)
