"""Downloader tests: hashing, dedup, password PDFs, failures, extensions."""

from __future__ import annotations

import httpx
import pytest

from scripts.mypaisaa_fetch.downloader import Downloader
from scripts.mypaisaa_fetch.models import StatementRecord
from tests.mypaisaa.conftest import (
    download_transport,
    encrypted_pdf_bytes,
    is_encrypted_with,
    make_config,
    minimal_pdf_bytes,
    multi_page_pdf_bytes,
)


def _record(url: str, password: str | None = None, user_id: str = "U1") -> StatementRecord:
    return StatementRecord(user_id=user_id, source_url=url, password=password)


@pytest.fixture
def downloader():
    config = make_config(__import__("pathlib").Path("."))
    client = httpx.AsyncClient(follow_redirects=True)
    yield Downloader(config, client)
    import asyncio

    asyncio.get_event_loop_policy()
    asyncio.run(client.aclose())


@pytest.mark.asyncio
async def test_download_success(downloader, tmp_path):
    transport = download_transport({"/a/1.pdf": minimal_pdf_bytes()})
    downloader.client = httpx.AsyncClient(transport=transport, follow_redirects=True)
    verdict = await downloader.download(_record("https://statements.test/a/1.pdf"), tmp_path, 1, set())
    assert verdict.status == "downloaded"
    assert (tmp_path / "statement_001.pdf").exists()
    assert verdict.file_size == len(minimal_pdf_bytes())
    assert len(verdict.sha256) == 64


@pytest.mark.asyncio
async def test_duplicate_hash_skipped(downloader, tmp_path):
    data = minimal_pdf_bytes()
    transport = download_transport({"/a/1.pdf": data, "/a/2.pdf": data})
    downloader.client = httpx.AsyncClient(transport=transport, follow_redirects=True)
    v1 = await downloader.download(_record("https://statements.test/a/1.pdf"), tmp_path, 1, set())
    v2 = await downloader.download(_record("https://statements.test/a/2.pdf"), tmp_path, 2, {v1.sha256})
    assert v1.status == "downloaded"
    assert v2.status == "duplicate"
    # Only one file stored
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.asyncio
async def test_never_overwrites_different_file_same_name(downloader, tmp_path):
    transport = download_transport({"/a/1.pdf": minimal_pdf_bytes(), "/a/2.pdf": multi_page_pdf_bytes(2)})
    downloader.client = httpx.AsyncClient(transport=transport, follow_redirects=True)
    v1 = await downloader.download(_record("https://statements.test/a/1.pdf"), tmp_path, 1, set())
    v2 = await downloader.download(_record("https://statements.test/a/2.pdf"), tmp_path, 1, set())
    assert v1.status == "downloaded"
    assert v2.status == "downloaded"
    assert v2.filename == "statement_001_1.pdf"


@pytest.mark.asyncio
async def test_password_protected_correct_password(downloader, tmp_path):
    data = encrypted_pdf_bytes("secret123")
    transport = download_transport({"/a/1.pdf": data})
    downloader.client = httpx.AsyncClient(transport=transport, follow_redirects=True)
    verdict = await downloader.download(
        _record("https://statements.test/a/1.pdf", password="secret123"), tmp_path, 1, set()
    )
    assert verdict.status == "downloaded"
    assert is_encrypted_with((tmp_path / "statement_001.pdf").read_bytes(), "secret123")


@pytest.mark.asyncio
async def test_password_protected_no_password(downloader, tmp_path):
    transport = download_transport({"/a/1.pdf": encrypted_pdf_bytes("secret123")})
    downloader.client = httpx.AsyncClient(transport=transport, follow_redirects=True)
    verdict = await downloader.download(_record("https://statements.test/a/1.pdf"), tmp_path, 1, set())
    assert verdict.status == "password_required"
    assert (tmp_path / "statement_001.pdf").exists()  # file is kept


@pytest.mark.asyncio
async def test_password_protected_wrong_password(downloader, tmp_path):
    transport = download_transport({"/a/1.pdf": encrypted_pdf_bytes("secret123")})
    downloader.client = httpx.AsyncClient(transport=transport, follow_redirects=True)
    verdict = await downloader.download(
        _record("https://statements.test/a/1.pdf", password="wrong"), tmp_path, 1, set()
    )
    assert verdict.status == "password_invalid"
    assert (tmp_path / "statement_001.pdf").exists()


@pytest.mark.asyncio
async def test_http_404_is_permanent_failure(downloader, tmp_path):
    downloader.client = httpx.AsyncClient(
        transport=download_transport({}), follow_redirects=True
    )
    verdict = await downloader.download(_record("https://statements.test/missing.pdf"), tmp_path, 1, set())
    assert verdict.status == "download_failed"
    assert "404" in verdict.error


@pytest.mark.asyncio
async def test_http_500_retried_then_success(downloader, tmp_path):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, content=minimal_pdf_bytes(), headers={"Content-Type": "application/pdf"})

    downloader.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    verdict = await downloader.download(_record("https://statements.test/a/1.pdf"), tmp_path, 1, set())
    assert verdict.status == "downloaded"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_invalid_url(downloader, tmp_path):
    verdict = await downloader.download(_record("ftp://statements.test/a/1.pdf"), tmp_path, 1, set())
    assert verdict.status == "invalid_url"
    verdict = await downloader.download(_record(None), tmp_path, 1, set())
    assert verdict.status == "invalid_url"


@pytest.mark.asyncio
async def test_jpeg_content_gets_jpg_extension(downloader, tmp_path):
    jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    transport = download_transport({"/a/1.pdf": jpeg})
    downloader.client = httpx.AsyncClient(transport=transport, follow_redirects=True)
    verdict = await downloader.download(_record("https://statements.test/a/1.pdf"), tmp_path, 1, set())
    assert verdict.status == "downloaded"
    assert verdict.filename == "statement_001.jpg"


@pytest.mark.asyncio
async def test_html_error_page_rejected(downloader, tmp_path):
    html = b"<!DOCTYPE html><html><body><h1>AccessDenied</h1></body></html>"
    transport = download_transport({"/a/1.pdf": html})
    downloader.client = httpx.AsyncClient(transport=transport, follow_redirects=True)
    verdict = await downloader.download(_record("https://statements.test/a/1.pdf"), tmp_path, 1, set())
    assert verdict.status == "download_invalid"
    assert verdict.file_type == "invalid"
    assert list(tmp_path.iterdir()) == []  # nothing saved


@pytest.mark.asyncio
async def test_empty_body_rejected(downloader, tmp_path):
    transport = download_transport({"/a/1.pdf": b""})
    downloader.client = httpx.AsyncClient(transport=transport, follow_redirects=True)
    verdict = await downloader.download(_record("https://statements.test/a/1.pdf"), tmp_path, 1, set())
    assert verdict.status == "download_invalid"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_corrupted_pdf_still_saved(downloader, tmp_path):
    # Truncated PDF: magic bytes present, body cut off. The file is kept and
    # marked downloaded (verification is best-effort, never fails the run).
    corrupted = minimal_pdf_bytes()[:40]
    transport = download_transport({"/a/1.pdf": corrupted})
    downloader.client = httpx.AsyncClient(transport=transport, follow_redirects=True)
    verdict = await downloader.download(_record("https://statements.test/a/1.pdf"), tmp_path, 1, set())
    assert verdict.status == "downloaded"
    assert verdict.file_type == "pdf"
