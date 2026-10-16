"""Small in-process sliding-window rate limiter for upload endpoints.

Per backend process (no shared store): it bounds abuse and accidental floods from
one user/IP, it is not a global quota. Limits come from settings/env.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from fastapi import HTTPException

_lock = threading.Lock()
_hits: Dict[str, Deque[float]] = defaultdict(deque)


def upload_limit_per_minute() -> int:
    try:
        return int(os.getenv("UPLOAD_RATE_LIMIT_PER_MINUTE", "30"))
    except ValueError:
        return 30


def max_pdf_pages() -> int:
    try:
        return int(os.getenv("MAX_PDF_PAGES", "200"))
    except ValueError:
        return 200


def check_rate_limit(key: str, limit: Optional[int] = None, window_seconds: int = 60) -> None:
    """Raise 429 when ``key`` exceeded ``limit`` calls in the window. limit<=0 disables."""
    limit = upload_limit_per_minute() if limit is None else limit
    if limit <= 0:
        return
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and now - q[0] > window_seconds:
            q.popleft()
        if len(q) >= limit:
            retry_after = max(1, int(window_seconds - (now - q[0])))
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Too many uploads. Please wait a moment and try again.",
                    "code": "RATE_LIMITED",
                    "stage": "upload",
                },
                headers={"Retry-After": str(retry_after)},
            )
        q.append(now)
        if not q:
            _hits.pop(key, None)
