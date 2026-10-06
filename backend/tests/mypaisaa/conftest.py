"""Shared fixtures for the MyPaisaa fetch pipeline tests."""

from __future__ import annotations

import io
from pathlib import Path

import httpx
import pytest
from pypdf import PdfReader, PdfWriter

from scripts.mypaisaa_fetch.config import PipelineConfig

API_HOST = "https://api.test"
STATEMENT_HOST = "https://statements.test"


def make_config(tmp_path: Path, input_file: Path | None = None, **overrides) -> PipelineConfig:
    defaults = dict(
        api_base_url=API_HOST,
        api_statements_path="/fetchaccount/customerbankdetails/{userid}",
        input_file=input_file or (tmp_path / "users.csv"),
        output_dir=tmp_path / "bank_statements",
        max_concurrent_users=3,
        max_retries=2,
        backoff_base_seconds=0.01,
        backoff_max_seconds=0.05,
        request_timeout_seconds=5.0,
        connect_timeout_seconds=2.0,
    )
    defaults.update(overrides)
    return PipelineConfig(**defaults)


def write_users_csv(path: Path, user_ids: list[str]):
    lines = ["user_id"] + user_ids
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def minimal_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def multi_page_pdf_bytes(pages: int) -> bytes:
    """Distinct PDFs (different page counts) so hashes differ between files."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def encrypted_pdf_bytes(password: str) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt(user_password=password)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def api_transport(statements_by_user: dict[str, list[dict]]) -> httpx.MockTransport:
    """Mock the MyPaisaa API. Each entry in statements_by_user is a list of
    raw statement objects returned inside ``data``."""

    def handler(request: httpx.Request) -> httpx.Response:
        user_id = request.url.path.rstrip("/").split("/")[-1]
        data = statements_by_user.get(user_id)
        if data is None:
            return httpx.Response(200, json={"status": "success", "data": []})
        return httpx.Response(200, json={"status": "success", "data": data})

    return httpx.MockTransport(handler)


def download_transport(files: dict[str, bytes]) -> httpx.MockTransport:
    """Mock the statement file server. Key = path part of the URL."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path in files:
            return httpx.Response(
                200,
                content=files[path],
                headers={"Content-Type": "application/pdf"},
            )
        return httpx.Response(404, text="not found")

    return httpx.MockTransport(handler)


def is_encrypted_with(data: bytes, password: str) -> bool:
    reader = PdfReader(io.BytesIO(data))
    if not reader.is_encrypted:
        return False
    return reader.decrypt(password) > 0


@pytest.fixture
def pdf_bytes() -> bytes:
    return minimal_pdf_bytes()
