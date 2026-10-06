"""Optional global request pacing (REQUESTS_PER_SECOND)."""

from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Ensures a minimum interval between request starts across all workers."""

    def __init__(self, requests_per_second: float):
        self._min_interval = 1.0 / requests_per_second if requests_per_second > 0 else 0.0
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        if self._min_interval <= 0:
            return
        async with self._lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            wait = self._last + self._min_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()
