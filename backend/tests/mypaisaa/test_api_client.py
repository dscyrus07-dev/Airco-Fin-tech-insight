"""API client tests: retries, backoff, status handling, timeouts."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from scripts.mypaisaa_fetch.api_client import (
    ApiPermanentError,
    ApiRetryError,
    MyPaisaaClient,
)
from tests.mypaisaa.conftest import make_config


@pytest.mark.asyncio
async def test_success_returns_payload():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"status": "success", "data": [{"url": "https://x/1.pdf"}]}
        )
    )
    client = MyPaisaaClient(make_config(Path(".")), transport=transport)
    try:
        response = await client.fetch_user_statements("U1")
        assert response.status_code == 200
        assert response.payload["data"][0]["url"] == "https://x/1.pdf"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_5xx_retried_then_success():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 3:
            return httpx.Response(503, text="service unavailable")
        return httpx.Response(200, json={"status": "success", "data": []})

    client = MyPaisaaClient(make_config(Path(".")), transport=httpx.MockTransport(handler))
    try:
        response = await client.fetch_user_statements("U1")
        assert response.status_code == 200
        assert calls["count"] == 3
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_5xx_exhausts_retries():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(500, text="boom")

    client = MyPaisaaClient(make_config(Path(".")), transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ApiRetryError) as excinfo:
            await client.fetch_user_statements("U1")
        assert calls["count"] == 3  # max_retries=2 -> 3 attempts
        assert excinfo.value.attempts == 3
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_4xx_not_retried():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(403, text="forbidden")

    client = MyPaisaaClient(make_config(Path(".")), transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ApiPermanentError) as excinfo:
            await client.fetch_user_statements("U1")
        assert calls["count"] == 1
        assert excinfo.value.status_code == 403
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_timeout_retried():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ConnectTimeout("timed out", request=request)
        return httpx.Response(200, json={"status": "success", "data": []})

    client = MyPaisaaClient(make_config(Path(".")), transport=httpx.MockTransport(handler))
    try:
        response = await client.fetch_user_statements("U1")
        assert response.status_code == 200
        assert calls["count"] == 2
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_429_retried_then_success():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, text="slow down")
        return httpx.Response(200, json={"status": "success", "data": []})

    client = MyPaisaaClient(make_config(Path(".")), transport=httpx.MockTransport(handler))
    try:
        response = await client.fetch_user_statements("U1")
        assert response.status_code == 200
        assert calls["count"] == 2
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_invalid_json_is_permanent():
    client = MyPaisaaClient(
        make_config(Path(".")),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text="<html>oops</html>")),
    )
    try:
        with pytest.raises(ApiPermanentError):
            await client.fetch_user_statements("U1")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_user_id_in_path_not_query():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"status": "success", "data": []})

    client = MyPaisaaClient(
        make_config(Path(".")), transport=httpx.MockTransport(handler)
    )
    try:
        await client.fetch_user_statements("C25331952091")
        assert "/fetchaccount/customerbankdetails/C25331952091" in captured["url"]
        assert "userId=" not in captured["url"]
    finally:
        await client.aclose()
