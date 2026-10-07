"""Route one PDF through the v2 engine, or say exactly why it must not be used. Pure orchestration: capability (text layer,
lock), bank-anchored layout resolution, extraction. The caller decides what to do with a fallback; this module never falls
back silently and never repairs a statement: a fallback reason is always returned.

status: "v2"            a layout resolved and the engine produced a result (check result.verification_status)
        "fallback"      v2 must not be used; fallback_reason says why (no_layout, ambiguous, foreign_bank, v2_failed:<code>)
        "unsupported"   the file cannot be processed by this engine (scanned_no_text, locked, read_error)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from app.services.migration.contract import ExtractionResult

from .extraction.engine import extract_pages
from .extraction.pdf_extractor import LOCKED, READ_ERROR, SCANNED_NO_TEXT, _is_password_error, read_pages, to_extraction_result
from .extraction.registry import LayoutRegistry
from .extraction.rows import Page

# failures where the file may still be handled by the legacy path
_RECOVERABLE = {"NO_ROWS", "NO_TABLE_HEADER"}


@dataclass
class RoutedExtraction:
    status: str
    layout_id: Optional[str] = None
    result: Optional[ExtractionResult] = None
    fallback_reason: str = ""
    candidates: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def use_v2(self) -> bool:
        return self.status == "v2" and self.result is not None and not self.result.failure


def route_pages(pages: Sequence[Page], registry: LayoutRegistry, bank_key: str = "") -> RoutedExtraction:
    if not any(p.words for p in pages):
        return RoutedExtraction("unsupported", fallback_reason=SCANNED_NO_TEXT.lower())
    res = registry.resolve(pages, bank_key)
    if res.spec is None:
        return RoutedExtraction("fallback", fallback_reason=res.status, candidates=res.candidates, notes=res.notes + [f"rejected:{x}" for x in res.rejected])
    outcome = extract_pages(pages, res.spec)
    result = to_extraction_result(outcome, res.spec)
    routed = RoutedExtraction("v2", res.spec.layout_id, result, candidates=res.candidates, notes=res.notes + list(outcome.notes))
    if outcome.failure:
        code = outcome.failure
        routed.status = "fallback" if code in _RECOVERABLE else "v2"
        if routed.status == "fallback":
            routed.fallback_reason = f"v2_failed:{code}"
    return routed


def route_pdf(pdf_path: str, registry: LayoutRegistry, password: Optional[str] = None, bank_key: str = "") -> RoutedExtraction:
    try:
        pages = read_pages(pdf_path, password)
    except Exception as exc:   # pdfplumber / pdfminer raise several types for encrypted or broken files
        return RoutedExtraction("unsupported", fallback_reason=(LOCKED if _is_password_error(exc) else READ_ERROR).lower())
    return route_pages(pages, registry, bank_key)
