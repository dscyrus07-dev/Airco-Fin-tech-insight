"""
Enhanced logging utilities with correlation ID support.
"""

import logging
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .correlation import get_correlation_id

class StructuredLogger:
    """Structured JSON logger with correlation ID support."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def _log(self, level: int, message: str, **kwargs):
        """Log with structured data including correlation ID."""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": logging.getLevelName(level),
            "message": message,
            "correlation_id": get_correlation_id(),
            "service": "airco-backend",
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
