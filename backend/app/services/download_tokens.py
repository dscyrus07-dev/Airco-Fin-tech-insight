"""Short-lived signed download tokens.

A token proves that the holder was authorised (via a verified bearer token) to
read ONE job's result. It lets plain browser links and the Next.js proxy fetch
the workbook without a bearer header, without making any job world-readable.

Format: ``<job_id>.<expiry_unix>.<hex hmac-sha256>``. Stateless, scoped to one
job id, bound to an expiry. The secret comes from DOWNLOAD_TOKEN_SECRET; when
unset a random per-process secret is used (tokens then do not survive a restart
or work across replicas, which fails closed).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

_DEFAULT_TTL_SECONDS = 15 * 60
_process_secret = secrets.token_bytes(32)


def _secret() -> bytes:
    configured = os.getenv("DOWNLOAD_TOKEN_SECRET", "").strip()
    return configured.encode("utf-8") if configured else _process_secret


def _ttl() -> int:
    try:
        return max(30, int(os.getenv("DOWNLOAD_TOKEN_TTL_SECONDS", _DEFAULT_TTL_SECONDS)))
    except ValueError:
        return _DEFAULT_TTL_SECONDS


def _sign(job_id: str, expires: int) -> str:
    msg = f"{job_id}.{expires}".encode("utf-8")
    return hmac.new(_secret(), msg, hashlib.sha256).hexdigest()


def issue_download_token(job_id: str, ttl_seconds: Optional[int] = None) -> str:
    expires = int(time.time()) + (ttl_seconds if ttl_seconds is not None else _ttl())
    return f"{job_id}.{expires}.{_sign(job_id, expires)}"


def verify_download_token(token: Optional[str], job_id: str) -> bool:
    """True only for an unexpired token issued for exactly this job id."""
    if not token or not job_id:
        return False
    try:
        token_job, expires_raw, signature = token.rsplit(".", 2)
        expires = int(expires_raw)
    except ValueError:
        return False
    if token_job != job_id or expires < int(time.time()):
        return False
    return hmac.compare_digest(signature, _sign(job_id, expires))
