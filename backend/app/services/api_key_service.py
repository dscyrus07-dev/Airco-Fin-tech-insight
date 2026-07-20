"""
Platform API key service — generate, hash, verify, revoke, rate-limit.
Pure logic; no FastAPI dependencies. Never log full raw keys.
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy.orm import Session

from ..core.config import settings
from ..database.models import ApiKey
from ..utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_SCOPES: List[str] = ["upload", "jobs:read", "download"]
ALL_SCOPES: List[str] = ["upload", "jobs:read", "download", "jobs:delete"]
PREFIX_LENGTH = 20
_RATE_LIMIT_TTL_SECONDS = 60
_RATE_LIMIT_KEY_PREFIX = "airco:ratelimit:"


def generate_api_key(environment: str = "live") -> str:
    env = (environment or "live").strip().lower()
    if env not in ("live", "test"):
        raise ValueError("environment must be 'live' or 'test'")
    return f"airco_sk_{env}_{secrets.token_hex(16)}"


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def extract_prefix(raw_key: str) -> str:
    return raw_key[:PREFIX_LENGTH]


def verify_key(raw_key: str, db: Session) -> Optional[ApiKey]:
    """Lookup by hash; enforce active + environment. Increments usage once."""
    if not raw_key or not raw_key.strip():
        return None

    key_hash = hash_key(raw_key.strip())
    record = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
    if not record:
        return None
    if not record.is_active:
        return None

    expected_env = (settings.API_KEY_ENVIRONMENT or "live").strip().lower()
    record_env = (record.environment or "live").strip().lower()
    if record_env != expected_env:
        logger.debug(
            "API key environment mismatch",
            key_prefix=record.key_prefix,
            key_env=record_env,
            server_env=expected_env,
        )
        return None

    record.last_used_at = datetime.now(timezone.utc)
    record.usage_count = (record.usage_count or 0) + 1
    db.commit()
    db.refresh(record)
    return record


def create_key(
    user_id: str,
    tenant_id: str,
    name: str,
    scopes: Optional[List[str]],
    environment: str,
    db: Session,
    rate_limit_per_minute: Optional[int] = None,
    daily_quota: Optional[int] = None,
) -> Tuple[str, ApiKey]:
    env = (environment or "test").strip().lower()
    if env not in ("live", "test"):
        raise ValueError("environment must be 'live' or 'test'")

    resolved_scopes = list(scopes) if scopes is not None else list(DEFAULT_SCOPES)
    for scope in resolved_scopes:
        if scope not in ALL_SCOPES:
            raise ValueError(f"Invalid scope: {scope}")

    raw_key = generate_api_key(env)
    record = ApiKey(
        user_id=user_id,
        tenant_id=tenant_id or "default",
        name=name.strip(),
        key_prefix=extract_prefix(raw_key),
        key_hash=hash_key(raw_key),
        scopes=resolved_scopes,
        environment=env,
        rate_limit_per_minute=rate_limit_per_minute
        if rate_limit_per_minute is not None
        else settings.API_KEY_RATE_LIMIT_DEFAULT,
        daily_quota=daily_quota
        if daily_quota is not None
        else (settings.API_KEY_DAILY_QUOTA_DEFAULT or None) or None,
        usage_count=0,
        processed_pdf_count=0,
        is_active=True,
    )
    if record.daily_quota == 0:
        record.daily_quota = None

    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info(
        "API key created",
        user_id=user_id,
        key_prefix=record.key_prefix,
        environment=env,
    )
    return raw_key, record


def revoke_key(key_id: str, user_id: str, db: Session) -> bool:
    try:
        uid = UUID(str(key_id))
    except (ValueError, TypeError):
        return False

    record = db.query(ApiKey).filter(ApiKey.id == uid).first()
    if not record or record.user_id != user_id:
        return False
    if not record.is_active:
        return False

    record.is_active = False
    record.revoked_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("API key revoked", user_id=user_id, key_prefix=record.key_prefix)
    return True


def list_keys(user_id: str, db: Session) -> List[ApiKey]:
    return (
        db.query(ApiKey)
        .filter(ApiKey.user_id == user_id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )


def increment_processed_pdf_count(
    key_id: Optional[str],
    db: Session,
    *,
    job_id: Optional[str] = None,
) -> bool:
    """
    +1 PDF when one job finishes successfully.
    job_id makes it idempotent (retries won't double-count).
    """
    if not key_id:
        return False
    try:
        uid = UUID(str(key_id))
    except (ValueError, TypeError):
        return False

    if job_id:
        try:
            import redis as sync_redis

            redis_key = f"airco:pdfcount:{job_id}"
            client = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
            try:
                # SET NX = only first success for this job counts
                if not client.set(redis_key, "1", nx=True, ex=7 * 24 * 3600):
                    return False
            finally:
                try:
                    client.close()
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("PDF count idempotency check failed", job_id=job_id, error=str(exc))

    from sqlalchemy import text

    row = db.execute(
        text(
            "UPDATE api_keys "
            "SET processed_pdf_count = COALESCE(processed_pdf_count, 0) + 1 "
            "WHERE id = :id "
            "RETURNING processed_pdf_count, key_prefix"
        ),
        {"id": str(uid)},
    ).fetchone()
    db.commit()
    if not row:
        return False
    logger.info(
        "PDF count +1",
        key_prefix=row[1],
        processed_pdf_count=row[0],
        job_id=job_id,
    )
    return True


def reset_stale_pdf_counts(db: Session) -> int:
    """
    Zero garbage PDF counters from earlier bugs.
    - PDFs can never exceed Usage
    - Unused keys (usage=0) cannot have PDFs
    """
    from sqlalchemy import text

    result = db.execute(
        text(
            "UPDATE api_keys "
            "SET processed_pdf_count = 0 "
            "WHERE COALESCE(processed_pdf_count, 0) > 0 "
            "  AND ("
            "        COALESCE(usage_count, 0) = 0 "
            "     OR COALESCE(processed_pdf_count, 0) > COALESCE(usage_count, 0)"
            "  )"
        )
    )
    db.commit()
    return int(result.rowcount or 0)


class _RateLimitRedis:
    """Per-event-loop Redis client (same pattern as RedisJobStore)."""

    def __init__(self) -> None:
        self._loop_clients: Dict[int, redis.Redis] = {}

    def client(self) -> redis.Redis:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        loop_id = id(loop)
        if loop_id not in self._loop_clients:
            self._loop_clients[loop_id] = redis.from_url(
                settings.REDIS_URL, decode_responses=True
            )
        return self._loop_clients[loop_id]


_rate_limit_redis = _RateLimitRedis()


async def check_rate_limit(key_id: str, limit: int) -> bool:
    """Redis INCR with 60s TTL. Returns True if under limit."""
    if limit <= 0:
        return True
    client = _rate_limit_redis.client()
    redis_key = f"{_RATE_LIMIT_KEY_PREFIX}{key_id}"
    try:
        current = await client.incr(redis_key)
        if current == 1:
            await client.expire(redis_key, _RATE_LIMIT_TTL_SECONDS)
        return int(current) <= int(limit)
    except redis.RedisError as exc:
        logger.warning("Rate limit Redis error; allowing request", error=str(exc))
        return True

