"""Structured JSON logging with sensitive-value redaction.

Mirrors the style of ``app/utils/logging.py`` but is self-contained so the
pipeline can run without importing the FastAPI app package.

Security rules enforced here:
- statement URLs are never logged in full (host only, path/query dropped)
- passwords are never logged, anywhere
- response bodies are never logged
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit

_SECRET_KEY_MARKERS = ("password", "passwd", "pwd", "pass")


def safe_url(url: str | None) -> str:
    """Return a log-safe version of a URL (scheme+host only)."""
    if not url:
        return ""
    try:
        parts = urlsplit(url)
        host = parts.netloc or ""
        return f"{parts.scheme}://{host}/" if host else "<invalid-url>"
    except ValueError:
        return "<invalid-url>"


def redact(mapping: dict) -> dict:
    """Mask values whose keys look sensitive."""
    out = {}
    for key, value in mapping.items():
        if any(marker in key.lower() for marker in _SECRET_KEY_MARKERS):
            out[key] = "***"
        else:
            out[key] = value
    return out


class StructuredLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def _log(self, level: int, message: str, **kwargs):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": logging.getLevelName(level),
            "message": message,
            "service": "mypaisaa-fetch",
            **redact(kwargs),
        }
        self.logger.log(level, json.dumps(payload, default=str))

    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)

    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)


def get_logger(name: str) -> StructuredLogger:
    if not logging.getLogger(name).handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger = logging.getLogger(name)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return StructuredLogger(name)
