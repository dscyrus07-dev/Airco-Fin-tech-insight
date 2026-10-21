"""PDF capability check: can AirCo read this file at all?

Text layer only. This module never runs OCR: an image-only PDF is reported as SCANNED. With
STATEMENT_ENGINE_OCR_MODE off (default) the user is told it is not supported; with the optional T4 OCR tier
enabled (see statement_engine/ocr), SCANNED/MIXED files are routed there instead.

`classify_pages` is pure (testable without a PDF). `check_pdf` opens a file with pdfplumber and
also returns the extracted text of the pages it read, so the bank detector does not open the file again.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .contracts import Capability, CapabilityResult

MIN_TEXT_CHARS = 40          # non-space characters for a page to count as "has text"
_CID = re.compile(r"\(cid:\d+\)")
_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class PageInfo:
    text_chars: int   # readable non-space characters (font-garbage like "(cid:12)" already removed)
    images: int       # embedded images on the page


def readable_chars(text: str) -> int:
    """Count readable non-space characters, ignoring unmapped-font garbage."""
    return len(_WS.sub("", _CID.sub("", text or "")))


def classify_pages(pages: Sequence[PageInfo], *, sampled: bool = False) -> CapabilityResult:
    n = len(pages)
    if n == 0:
        return CapabilityResult(Capability.UNREADABLE, 0, reason="The file has no pages.")
    text_pages = sum(1 for p in pages if p.text_chars >= MIN_TEXT_CHARS)
    image_only = sum(1 for p in pages if p.text_chars < MIN_TEXT_CHARS and p.images > 0)
    blank = n - text_pages - image_only
    note = " (first and last pages checked)" if sampled else ""
    if text_pages == 0:
        why = (
            "Every page is an image with no text layer" if image_only
            else "No readable text was found on any page"
        )
        return CapabilityResult(
            Capability.SCANNED, n, 0, image_only, blank,
            reason=f"{why}{note}. AirCo supports text-based PDF statements only.",
        )
    if image_only > 0:
        return CapabilityResult(
            Capability.MIXED, n, text_pages, image_only, blank,
            reason=f"{image_only} of {n} pages are images without text{note}; the rest have text.",
        )
    return CapabilityResult(Capability.TEXT, n, text_pages, 0, blank, reason="Text layer found.")


def _page_indexes(total: int, max_pages: int) -> Tuple[List[int], bool]:
    if total <= max_pages:
        return list(range(total)), False
    head = max_pages * 2 // 3
    tail = max_pages - head
    return sorted(set(range(head)) | set(range(total - tail, total))), True


def _is_password_error(exc: BaseException) -> bool:
    """True if the exception, or anything it wraps, says the PDF needs a password."""
    seen = set()
    stack = [exc]
    while stack:
        e = stack.pop()
        if id(e) in seen or not isinstance(e, BaseException):
            continue
        seen.add(id(e))
        text = (type(e).__name__ + " " + str(e)).lower()
        if "password" in text or "encrypt" in text:
            return True
        stack.extend([e.__cause__, e.__context__, *e.args])
    return False


def _decrypt_if_needed(path: str, password: Optional[str]):
    """Return (source, locked_result). Uses pikepdf (already a dependency) to detect a lock reliably and to hand
    pdfplumber an in-memory decrypted copy, so no extra crypto library is needed. (None, result) when locked."""
    try:
        import pikepdf
    except Exception:
        return path, None
    try:
        with pikepdf.open(path, password=password or "") as pdf:
            if not pdf.is_encrypted:
                return path, None
            import io

            buf = io.BytesIO()
            pdf.save(buf)
            buf.seek(0)
            return buf, None
    except pikepdf.PasswordError:
        why = "The PDF is password-protected" + (" and the password given is wrong." if password else ".")
        return None, CapabilityResult(Capability.LOCKED, 0, reason=why)
    except Exception:
        return path, None   # not pikepdf's business: let pdfplumber report what it can


def check_pdf(
    path: str,
    password: Optional[str] = None,
    *,
    max_pages: int = 12,
) -> Tuple[CapabilityResult, List[str]]:
    """Return (capability, page_texts). page_texts[i] belongs to page index i of the sample, see page_numbers.

    Never raises for a bad file: failures come back as LOCKED or UNREADABLE.
    """
    try:
        import pdfplumber  # lazy: keeps this module importable without the PDF stack
    except Exception as exc:  # pragma: no cover - environment problem
        return CapabilityResult(Capability.UNREADABLE, 0, reason=f"PDF library unavailable: {exc}"), []
    source, locked = _decrypt_if_needed(path, password)
    if locked is not None:
        return locked, []
    try:
        with pdfplumber.open(source, password=password if source is path else None) as pdf:
            total = len(pdf.pages)
            idx, sampled = _page_indexes(total, max_pages)
            infos: List[PageInfo] = []
            texts: List[str] = []
            for i in idx:
                page = pdf.pages[i]
                text = page.extract_text() or ""
                infos.append(PageInfo(readable_chars(text), len(page.images)))
                texts.append(text)
            result = classify_pages(infos, sampled=sampled)
            result.page_count = total
            return result, texts
    except Exception as exc:
        if _is_password_error(exc):
            why = "The PDF is password-protected" + (" and the password given is wrong." if password else ".")
            return CapabilityResult(Capability.LOCKED, 0, reason=why), []
        return CapabilityResult(Capability.UNREADABLE, 0, reason=f"The file could not be opened: {type(exc).__name__}"), []
