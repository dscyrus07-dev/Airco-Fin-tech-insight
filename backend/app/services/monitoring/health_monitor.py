"""
System Health Monitor
Collects system metrics and service health every 60 seconds
Writes to system_health_logs in Supabase
"""

import asyncio
import socket
import time
import traceback
from datetime import datetime
from typing import Optional

import psutil

from ...database.session import get_db
from ...database.audit_models import SystemHealthLog, Session, ProcessingJob
from ...utils.logging import get_logger
from ...core.config import settings

logger = get_logger(__name__)

POLL_INTERVAL_SECONDS = 60


async def _ping_redis() -> tuple[bool, Optional[int]]:
    try:
        import redis.asyncio as redis_lib
        start = time.monotonic()
        r = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        latency_ms = int((time.monotonic() - start) * 1000)
        return True, latency_ms
    except Exception:
        return False, None


def _ping_rabbitmq_sync() -> tuple[bool, Optional[int], int, int]:
    """Probe RabbitMQ with pika (same client used by message_queue)."""
    try:
        import pika
    except ImportError:
        return False, None, 0, 0

    connection = None
    try:
        start = time.monotonic()
        parameters = pika.URLParameters(settings.RABBITMQ_URL)
        parameters.socket_timeout = 3
        parameters.blocked_connection_timeout = 3
        parameters.heartbeat = 30
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        # Passive declare: fails if queue missing, does not recreate it.
        result = channel.queue_declare(queue="file_upload_queue", durable=True, passive=True)
        latency_ms = int((time.monotonic() - start) * 1000)
        message_count = int(getattr(result.method, "message_count", 0) or 0)
        return True, latency_ms, message_count, 0
    except Exception:
        return False, None, 0, 0
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


async def _ping_rabbitmq() -> tuple[bool, Optional[int], int, int]:
    return await asyncio.to_thread(_ping_rabbitmq_sync)


async def _ping_object_storage() -> tuple[bool, Optional[int]]:
    """Ping Supabase S3-compatible object storage via boto3 head_bucket."""
    try:
        import boto3
        from botocore.client import Config as BotoConfig

        if not settings.S3_ENDPOINT or not settings.S3_ACCESS_KEY:
            return False, None

        start = time.monotonic()
        client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": settings.S3_ADDRESSING_STYLE or "path"},
            ),
            region_name=settings.S3_REGION or "us-east-1",
        )
        client.head_bucket(Bucket=settings.S3_BUCKET_UPLOADS)
        latency_ms = int((time.monotonic() - start) * 1000)
        return True, latency_ms
    except Exception:
        return False, None



async def _ping_supabase(db) -> tuple[bool, Optional[int]]:
    try:
        from sqlalchemy import text as _text
        start = time.monotonic()
        db.execute(_text("SELECT 1"))
        latency_ms = int((time.monotonic() - start) * 1000)
        return True, latency_ms
    except Exception:
        return False, None


async def _ping_keycloak() -> tuple[bool, Optional[int]]:
    try:
        import httpx
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=3) as client:
            url = f"{settings.KEYCLOAK_URL.rstrip('/')}/realms/{settings.KEYCLOAK_REALM}"
            r = await client.get(url)
            ok = r.status_code < 500
        latency_ms = int((time.monotonic() - start) * 1000)
        return ok, latency_ms
    except Exception:
        return False, None


def _collect_system_metrics() -> dict:
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "cpu_percent": cpu,
        "memory_percent": mem.percent,
        "memory_used_mb": mem.used // (1024 * 1024),
        "memory_total_mb": mem.total // (1024 * 1024),
        "disk_percent": disk.percent,
        "disk_used_gb": round(disk.used / (1024 ** 3), 2),
        "disk_total_gb": round(disk.total / (1024 ** 3), 2),
    }


async def collect_and_store_health():
    """Single health collection cycle — called every POLL_INTERVAL_SECONDS."""
    db = next(get_db())
    try:
        sys_metrics = _collect_system_metrics()

        (redis_ok, redis_ms), (rmq_ok, rmq_ms, rmq_ready, rmq_unacked), \
        (storage_ok, storage_ms), (supa_ok, supa_ms), (kc_ok, kc_ms) = await asyncio.gather(
            _ping_redis(),
            _ping_rabbitmq(),
            _ping_object_storage(),
            _ping_supabase(db),
            _ping_keycloak(),
        )


        # Determine active sessions and jobs
        active_sessions = db.query(Session).filter(Session.is_active == True).count()
        active_jobs = db.query(ProcessingJob).filter(
            ProcessingJob.status.in_(["PROCESSING", "QUEUED"])
        ).count()

        # Determine overall status
        alerts = []
        if sys_metrics["cpu_percent"] > 85:
            alerts.append({"type": "HIGH_CPU", "value": sys_metrics["cpu_percent"]})
        if sys_metrics["memory_percent"] > 85:
            alerts.append({"type": "HIGH_MEMORY", "value": sys_metrics["memory_percent"]})
        if sys_metrics["disk_percent"] > 90:
            alerts.append({"type": "HIGH_DISK", "value": sys_metrics["disk_percent"]})
        if not redis_ok:
            alerts.append({"type": "REDIS_DOWN"})
        if not rmq_ok:
            alerts.append({"type": "RABBITMQ_DOWN"})
        if not storage_ok:
            alerts.append({"type": "STORAGE_DOWN"})
        if not supa_ok:
            alerts.append({"type": "SUPABASE_DOWN"})

        if any(a["type"].endswith("_DOWN") for a in alerts):
            status = "CRITICAL"
        elif alerts:
            status = "DEGRADED"
        else:
            status = "HEALTHY"

        record = SystemHealthLog(
            host=socket.gethostname(),
            environment=getattr(settings, "ENVIRONMENT", "PRODUCTION"),
            **sys_metrics,
            redis_healthy=redis_ok,
            rabbitmq_healthy=rmq_ok,
            minio_healthy=storage_ok,  # column name kept for DB compatibility
            supabase_healthy=supa_ok,
            keycloak_healthy=kc_ok,
            redis_latency_ms=redis_ms,
            rabbitmq_latency_ms=rmq_ms,
            minio_latency_ms=storage_ms,  # column name kept for DB compatibility
            supabase_latency_ms=supa_ms,
            keycloak_latency_ms=kc_ms,

            rabbitmq_ready_messages=rmq_ready,
            rabbitmq_unacked_messages=rmq_unacked,
            active_sessions=active_sessions,
            active_jobs=active_jobs,
            status=status,
            alerts=alerts,
        )
        db.add(record)
        db.commit()

        if status != "HEALTHY":
            logger.warning(f"Health check: status={status} alerts={alerts}")
        else:
            logger.debug("Health check: HEALTHY")

    except Exception as e:
        logger.error(f"Health monitor error: {e}", exc_info=True)
    finally:
        db.close()


class HealthMonitor:
    """Background task that polls system health every minute."""

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("HealthMonitor started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("HealthMonitor stopped")

    async def _loop(self):
        while self._running:
            await collect_and_store_health()
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


health_monitor = HealthMonitor()
