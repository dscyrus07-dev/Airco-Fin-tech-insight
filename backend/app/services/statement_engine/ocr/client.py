"""Backend-side client for the separate ocr-service (the backend itself never loads a model or needs a GPU).

Configuration (environment only; no secrets involved):
    STATEMENT_ENGINE_OCR_URL            http://ocr-service:8090   or   mock:<dir>  (local fixtures, see below)
    STATEMENT_ENGINE_OCR_PAGE_TIMEOUT_S per-page budget used to size the request timeout (default 45; ~20 s/page measured on an RTX 3060)
    STATEMENT_ENGINE_OCR_MAX_PAGES      pages per document OCR will accept (default 60)
    STATEMENT_ENGINE_OCR_DETECT_TIMEOUT_S  analysis-time budget for pages 1-2 (default 5)

Service contract: POST {url}/v1/ocr?pages=1,2&verify=1 with the raw PDF bytes (Content-Type application/pdf);
response is contracts.OcrDocument as JSON. GET {url}/health -> {"status": "ok", ...}.

mock:<dir> serves <dir>/<sha256-of-pdf>.json (an OcrDocument dict). It exists so the integration can be
developed and tested without a GPU; it never fabricates output for a file it has no fixture for.

Never raises: every failure comes back as OcrDocument(error=CODE).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from typing import Optional, Sequence

from .contracts import OcrDocument, document_from_dict

URL_ENV = "STATEMENT_ENGINE_OCR_URL"

OCR_UNCONFIGURED = "OCR_UNCONFIGURED"
OCR_UNAVAILABLE = "OCR_SERVICE_UNAVAILABLE"
OCR_TIMEOUT = "OCR_TIMEOUT"
OCR_BAD_RESPONSE = "OCR_BAD_RESPONSE"
OCR_TOO_MANY_PAGES = "OCR_TOO_MANY_PAGES"
OCR_NO_FIXTURE = "OCR_NO_FIXTURE"


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def max_pages() -> int:
    return int(_env_float("STATEMENT_ENGINE_OCR_MAX_PAGES", 60))


def page_timeout_s() -> float:
    return _env_float("STATEMENT_ENGINE_OCR_PAGE_TIMEOUT_S", 45.0)


def detect_timeout_s() -> float:
    return _env_float("STATEMENT_ENGINE_OCR_DETECT_TIMEOUT_S", 5.0)


def service_url() -> str:
    return (os.environ.get(URL_ENV) or "").strip()


def configured() -> bool:
    return bool(service_url())


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _from_mock(root: str, pdf_path: str, pages: Optional[Sequence[int]]) -> OcrDocument:
    try:
        path = os.path.join(root, _sha256(pdf_path) + ".json")
        if not os.path.isfile(path):
            return OcrDocument(error=OCR_NO_FIXTURE)
        with open(path, "r", encoding="utf-8") as fh:
            doc = document_from_dict(json.load(fh))
    except Exception:
        return OcrDocument(error=OCR_BAD_RESPONSE)
    if pages:
        keep = set(pages)
        doc.pages = [p for p in doc.pages if p.page in keep]
    return doc


def health(timeout_s: float = 2.0) -> bool:
    url = service_url()
    if not url:
        return False
    if url.startswith("mock:"):
        return os.path.isdir(url[5:])
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=timeout_s) as r:
            return r.status == 200 and json.loads(r.read().decode("utf-8") or "{}").get("status") == "ok"
    except Exception:
        return False


def ocr_pdf(pdf_path: str, pages: Optional[Sequence[int]] = None, *, verify: bool = True,
            page_count: Optional[int] = None, timeout_s: Optional[float] = None, vl: bool = True) -> OcrDocument:
    """OCR `pages` (1-based; None = all) of a PDF. The PDF must already be decrypted.

    vl=False is the fast reading: the service skips the VL model and returns text lines only."""
    url = service_url()
    if not url:
        return OcrDocument(error=OCR_UNCONFIGURED)
    n = len(pages) if pages else (page_count or 0)
    if n > max_pages():
        return OcrDocument(error=OCR_TOO_MANY_PAGES)
    if url.startswith("mock:"):
        doc = _from_mock(url[5:], pdf_path, pages)
        if not vl and not doc.error:         # a fixture answers as the service would for the fast reading
            for p in doc.pages:
                p.blocks = []
            doc.engine, doc.verifier = "PP-OCRv5", ""
        return doc
    budget = timeout_s if timeout_s is not None else 15.0 + page_timeout_s() * max(1, n or 1)
    q = []
    if pages:
        q.append("pages=" + ",".join(str(int(p)) for p in pages))
    q.append("verify=" + ("1" if verify else "0"))
    q.append("vl=" + ("1" if vl else "0"))
    endpoint = url.rstrip("/") + "/v1/ocr?" + "&".join(q)
    t0 = time.monotonic()
    try:
        with open(pdf_path, "rb") as fh:
            body = fh.read()
        req = urllib.request.Request(endpoint, data=body, method="POST",
                                     headers={"Content-Type": "application/pdf"})
        with urllib.request.urlopen(req, timeout=budget) as r:
            payload = json.loads(r.read().decode("utf-8"))
        doc = document_from_dict(payload)
    except urllib.error.HTTPError:
        return OcrDocument(error=OCR_UNAVAILABLE, elapsed_s=time.monotonic() - t0)
    except (TimeoutError, OSError) as exc:
        code = OCR_TIMEOUT if "timed out" in str(exc).lower() or isinstance(exc, TimeoutError) else OCR_UNAVAILABLE
        return OcrDocument(error=code, elapsed_s=time.monotonic() - t0)
    except (ValueError, TypeError):
        return OcrDocument(error=OCR_BAD_RESPONSE, elapsed_s=time.monotonic() - t0)
    if not doc.elapsed_s:
        doc.elapsed_s = time.monotonic() - t0
    return doc
