"""Statement downloader with hashing, dedup and password verification.

- streams downloads to a temp file, then moves into place (no partial files)
- computes SHA-256 while writing
- skips saving when the same hash already exists for the user (duplicate)
- never overwrites a different file under the same name (picks the next index)
- verifies password-protected PDFs with pypdf and reports
  password_required / password_invalid instead of discarding the file
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from pypdf import PdfReader
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from .config import PipelineConfig
from .logging_utils import get_logger, safe_url
from .models import (
    ST_DOWNLOADED,
    ST_DUPLICATE,
    ST_DOWNLOAD_FAILED,
    ST_DOWNLOAD_INVALID,
    ST_INVALID_URL,
    ST_PASSWORD_INVALID,
    ST_PASSWORD_REQUIRED,
    StatementRecord,
)

logger = get_logger(__name__)

# pypdf logs noisy warnings (invalid header, EOF marker) to stderr when it
# inspects non-PDF files; keep them out of the pipeline output.
logging.getLogger("pypdf").setLevel(logging.CRITICAL)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}

_CONTENT_TYPE_EXT = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel": ".xls",
    "application/zip": ".zip",
    "text/csv": ".csv",
    "application/octet-stream": "",  # fall back to URL extension
}

_MAGIC_EXT = [
    (b"%PDF", ".pdf", "pdf"),
    (b"\xff\xd8\xff", ".jpg", "jpeg"),
    (b"\x89PNG", ".png", "png"),
    (b"PK\x03\x04", None, "zip"),  # zip/xlsx/docx container: keep URL/CT extension
    (b"GIF8", ".gif", "gif"),
    (b"BM", ".bmp", "bmp"),
]

_HTML_MARKERS = (b"<!DOCTYPE", b"<!doctype", b"<html", b"<HTML")

_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize(name: str) -> str:
    name = _UNSAFE_NAME.sub("_", name).strip("._")
    return name[:120] or "statement"


def _extension_for(content_type: str, url: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct in _CONTENT_TYPE_EXT:
        ext = _CONTENT_TYPE_EXT[ct]
        if ext:
            return ext
    suffix = Path(urlsplit(url).path).suffix.lower()
    if suffix and len(suffix) <= 6 and suffix.isalnum() or suffix == ".pdf":
        return suffix
    return ".bin"


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    return False


class DownloadVerdict:
    __slots__ = (
        "status", "filename", "local_path", "file_size", "sha256", "error",
        "file_type", "password_verified",
    )

    def __init__(
        self, status, filename=None, local_path=None, file_size=None, sha256=None,
        error=None, file_type=None, password_verified=False,
    ):
        self.status = status
        self.filename = filename
        self.local_path = local_path
        self.file_size = file_size
        self.sha256 = sha256
        self.error = error
        self.file_type = file_type
        self.password_verified = password_verified


class Downloader:
    def __init__(self, config: PipelineConfig, client: httpx.AsyncClient, limiter=None):
        self.config = config
        self.client = client
        self._limiter = limiter

    async def download(
        self,
        record: StatementRecord,
        dest_dir: Path,
        index: int,
        known_hashes: set[str],
    ) -> DownloadVerdict:
        url = record.source_url
        if not url or not url.lower().startswith(("http://", "https://")):
            return DownloadVerdict(ST_INVALID_URL, error="missing or unsupported URL")

        dest_dir.mkdir(parents=True, exist_ok=True)
        attempts = self.config.max_retries + 1
        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception(_is_retryable),
                wait=wait_exponential(
                    multiplier=self.config.backoff_base_seconds,
                    max=self.config.backoff_max_seconds,
                ),
                stop=stop_after_attempt(attempts),
                reraise=True,
            ):
                with attempt:
                    return await self._attempt_download(record, dest_dir, index, known_hashes)
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            error = f"http {code}" if code in RETRYABLE_STATUS else f"http {code} (permanent)"
            logger.error("download failed", user_id=record.user_id, url=safe_url(url), error=error)
            _cleanup_part_files(dest_dir, index)
            return DownloadVerdict(ST_DOWNLOAD_FAILED, error=error)
        except httpx.TransportError as exc:
            error = f"transport error: {type(exc).__name__}"
            logger.error("download failed", user_id=record.user_id, url=safe_url(url), error=error)
            _cleanup_part_files(dest_dir, index)
            return DownloadVerdict(ST_DOWNLOAD_FAILED, error=error)

    def reverify(self, local_path: str, record: StatementRecord) -> DownloadVerdict:
        """Re-check an already-downloaded file (e.g. password retry on resume)."""
        path = Path(local_path)
        digest = _sha256_of(path)
        size = path.stat().st_size
        verdict = self._verify_password(path, record)
        verdict.sha256 = digest
        verdict.file_size = size
        logger.info(
            "statement reverified",
            user_id=record.user_id,
            filename=path.name,
            status=verdict.status,
        )
        return verdict

    async def _attempt_download(
        self, record: StatementRecord, dest_dir: Path, index: int, known_hashes: set[str]
    ) -> DownloadVerdict:
        url = record.source_url
        if self._limiter is not None:
            await self._limiter.acquire()
        async with self.client.stream("GET", url) as response:
            response.raise_for_status()
            ext = _extension_for(response.headers.get("content-type", ""), url)
            base = _sanitize(f"statement_{index:03d}")
            tmp_path = dest_dir / f"{base}{ext}.part"
            hasher = hashlib.sha256()
            size = 0
            with tmp_path.open("wb") as fh:
                async for chunk in response.aiter_bytes(64 * 1024):
                    fh.write(chunk)
                    hasher.update(chunk)
                    size += len(chunk)
            digest = hasher.hexdigest()

        # Validate + sniff real content: some "statement PDFs" are photos
        # (JPEG/PNG); error pages or empty bodies must not be saved.
        try:
            override_ext, file_type = _sniff_type(tmp_path)
        except ValueError as exc:
            tmp_path.unlink(missing_ok=True)
            logger.warning(
                "download invalid", user_id=record.user_id, url=safe_url(url), error=str(exc)
            )
            return DownloadVerdict(ST_DOWNLOAD_INVALID, error=str(exc), file_type="invalid")
        if override_ext and override_ext != ext:
            renamed = tmp_path.with_suffix(f"{override_ext}.part")
            tmp_path.replace(renamed)
            tmp_path = renamed
            ext = override_ext

        if digest in known_hashes:
            tmp_path.unlink(missing_ok=True)
            logger.info(
                "duplicate skipped",
                user_id=record.user_id,
                sha256=digest[:12],
                url=safe_url(url),
            )
            return DownloadVerdict(ST_DUPLICATE, sha256=digest, file_size=size, file_type=file_type)

        final_path = self._resolve_target(dest_dir, base, ext, digest)
        os.replace(tmp_path, final_path)
        _restrict_permissions(final_path)

        verdict = self._verify_password(final_path, record)
        verdict.sha256 = digest
        verdict.file_size = size
        verdict.file_type = file_type
        logger.info(
            "statement saved",
            user_id=record.user_id,
            filename=final_path.name,
            status=verdict.status,
            sha256=digest[:12],
            url=safe_url(url),
        )
        return verdict

    def _resolve_target(self, dest_dir: Path, base: str, ext: str, digest: str) -> Path:
        """Pick a free filename; never overwrite a different file."""
        candidate = dest_dir / f"{base}{ext}"
        if not candidate.exists():
            return candidate
        if _sha256_of(candidate) == digest:
            return candidate  # same content, overwrite is safe
        for bump in range(1, 1000):
            candidate = dest_dir / f"{base}_{bump}{ext}"
            if not candidate.exists() or _sha256_of(candidate) == digest:
                return candidate
        raise RuntimeError("could not resolve target filename")

    @staticmethod
    def _verify_password(path: Path, record: StatementRecord) -> DownloadVerdict:
        local = str(path)
        try:
            reader = PdfReader(local)
            if not reader.is_encrypted:
                return DownloadVerdict(ST_DOWNLOADED, filename=path.name, local_path=local)
            password = record.password
            if not password:
                logger.warning(
                    "password required", user_id=record.user_id, filename=path.name
                )
                return DownloadVerdict(
                    ST_PASSWORD_REQUIRED, filename=path.name, local_path=local,
                    error="PDF is password protected and no password was provided",
                )
            try:
                if reader.decrypt(password) > 0:
                    return DownloadVerdict(
                        ST_DOWNLOADED, filename=path.name, local_path=local,
                        password_verified=True,
                    )
            except Exception:  # noqa: BLE001 - pypdf raises varied errors on bad passwords
                pass
            logger.warning("password invalid", user_id=record.user_id, filename=path.name)
            return DownloadVerdict(
                ST_PASSWORD_INVALID, filename=path.name, local_path=local,
                error="provided password did not unlock the PDF",
            )
        except Exception as exc:  # noqa: BLE001 - never fail the run on verification errors
            logger.warning(
                "pdf verification skipped",
                user_id=record.user_id,
                filename=path.name,
                error=type(exc).__name__,
            )
            return DownloadVerdict(ST_DOWNLOADED, filename=path.name, local_path=local)


def _sniff_type(path: Path) -> tuple[str | None, str]:
    """Return (extension_override|None, file_type) from magic bytes.

    Raises ValueError for non-document content (HTML error pages etc.).
    """
    with path.open("rb") as fh:
        head = fh.read(16)
    if not head:
        raise ValueError("empty response body")
    if any(head.startswith(marker) for marker in _HTML_MARKERS):
        raise ValueError("response is an HTML page, not a document")
    for magic, ext, file_type in _MAGIC_EXT:
        if head.startswith(magic):
            return ext, file_type
    if head.lstrip().startswith(b"<?xml"):
        raise ValueError("response is XML, not a document")
    return None, "unknown"


def _cleanup_part_files(dest_dir: Path, index: int):
    """Remove leftover .part files after permanent download failure."""
    try:
        for part in dest_dir.glob(f"statement_{index:03d}*.part"):
            part.unlink(missing_ok=True)
    except OSError:
        pass


def _sha256_of(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(64 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _restrict_permissions(path: Path):
    """Best-effort restrictive permissions (POSIX only)."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # Windows / FAT filesystems: rely on directory-level protection
