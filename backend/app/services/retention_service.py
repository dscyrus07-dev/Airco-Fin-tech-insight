import asyncio
from contextlib import suppress

from ..core.config import settings
from ..utils.logging import get_logger
from .file_history_service import file_history_service

logger = get_logger(__name__)


class RetentionService:
    def __init__(self):
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if not settings.RETENTION_ENABLED:
            logger.info("Retention service disabled via configuration")
            return

        if self._task and not self._task.done():
            return

        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Retention service started",
            retention_days=settings.DATA_RETENTION_DAYS,
            sweep_interval_minutes=settings.RETENTION_SWEEP_INTERVAL_MINUTES,
        )

    async def stop(self) -> None:
        if not self._task:
            return

        self._stop_event.set()
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        logger.info("Retention service stopped")

    async def sweep_once(self) -> int:
        expired_records = file_history_service.list_expired_records()
        deleted_count = 0

        for record in expired_records:
            try:
                if file_history_service.purge_expired_record(record, reason="retention expired after 7 days"):
                    deleted_count += 1
            except Exception as exc:
                logger.warning(
                    "Retention sweep failed for record",
                    job_id=getattr(record, "job_id", None) or (record.get("job_id") if isinstance(record, dict) else None),
                    error=str(exc),
                )

        if deleted_count:
            logger.info("Retention sweep deleted expired files", deleted_count=deleted_count)
        return deleted_count

    async def _run_loop(self) -> None:
        await self.sweep_once()
        interval_seconds = max(60, settings.RETENTION_SWEEP_INTERVAL_MINUTES * 60)

        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                await self.sweep_once()


retention_service = RetentionService()
