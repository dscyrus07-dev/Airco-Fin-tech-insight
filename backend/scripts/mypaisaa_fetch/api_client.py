"""Async HTTP client for the MyPaisaa customerbankdetails API.

Retry policy:
- retried: connection errors, timeouts, DNS failures, HTTP 5xx, HTTP 429
- not retried: other HTTP 4xx (bad request, forbidden, not found, ...)
- exponential backoff: base * 2^(attempt-1), capped

Security: response bodies are never logged (they contain statement URLs and
passwords). Only status codes and user IDs appear in logs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from .config import PipelineConfig
from .logging_utils import get_logger, safe_url

logger = get_logger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class ApiPermanentError(Exception):
    """Non-retryable API failure (4xx, invalid payload, ...)."""

    def __init__(self, user_id: str, status_code: int | None, reason: str):
        self.user_id = user_id
        self.status_code = status_code
        self.reason = reason
        super().__init__(f"[{user_id}] {reason}")


class ApiRetryError(Exception):
    """Retryable API failure that exhausted all attempts."""

    def __init__(self, user_id: str, reason: str, attempts: int):
        self.user_id = user_id
        self.reason = reason
        self.attempts = attempts
        super().__init__(f"[{user_id}] {reason} after {attempts} attempts")


@dataclass
class ApiResponse:
    status_code: int
    payload: dict


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    return False


class MyPaisaaClient:
    def __init__(
        self,
        config: PipelineConfig,
        transport: httpx.BaseTransport | None = None,
        limiter=None,
    ):
        self.config = config
        self._limiter = limiter
        self._client = httpx.AsyncClient(
            base_url=config.api_base_url,
            timeout=httpx.Timeout(
                connect=config.connect_timeout_seconds,
                read=config.request_timeout_seconds,
                write=config.request_timeout_seconds,
                pool=config.request_timeout_seconds,
            ),
            headers={"User-Agent": config.user_agent, "Accept": "application/json"},
            transport=transport,
            follow_redirects=True,
        )

    async def aclose(self):
        await self._client.aclose()

    async def fetch_user_statements(self, user_id: str) -> ApiResponse:
        """GET all statements for one user. Raises on unrecoverable errors."""
        path = self.config.api_statements_path.format(userid=user_id)
        attempts = self.config.max_retries + 1
        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception(_retryable),
                wait=wait_exponential(
                    multiplier=self.config.backoff_base_seconds,
                    max=self.config.backoff_max_seconds,
                ),
                stop=stop_after_attempt(attempts),
                reraise=True,
            ):
                with attempt:
                    if self._limiter is not None:
                        await self._limiter.acquire()
                    response = await self._client.get(path)
                    logger.info(
                        "api response",
                        user_id=user_id,
                        status_code=response.status_code,
                        url=safe_url(str(response.request.url)),
                    )
                    response.raise_for_status()
                    return ApiResponse(response.status_code, self._parse_json(user_id, response))
        except RetryError as exc:  # pragma: no cover - reraise=True avoids this
            raise ApiRetryError(user_id, str(exc.last_attempt.exception()), attempts) from exc
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code in RETRYABLE_STATUS:
                raise ApiRetryError(user_id, f"http {code}", attempts) from exc
            raise ApiPermanentError(user_id, code, f"http {code}") from exc
        except httpx.TransportError as exc:
            raise ApiRetryError(user_id, f"transport error: {type(exc).__name__}", attempts) from exc

    @staticmethod
    def _parse_json(user_id: str, response: httpx.Response) -> dict:
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise ApiPermanentError(user_id, response.status_code, "invalid JSON response") from exc
        if not isinstance(payload, dict):
            raise ApiPermanentError(user_id, response.status_code, "unexpected JSON payload type")
        return payload
