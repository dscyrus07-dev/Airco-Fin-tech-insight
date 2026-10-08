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
from .extraction.words import group_lines

# Slice 2 detector bank id -> LayoutSpec.bank_key, for every bank that has a layout. A bank the detector names with at
# least MEDIUM confidence that is NOT in this map is another bank: v2 must not be used, whatever header matched.
DETECTOR_TO_SPEC_BANK = {
    "hdfc": "hdfc", "sbi": "sbi", "canara": "canara", "axis": "axis", "idfc": "idfc", "kotak": "kotak",
    "federal": "federal", "bank_of_baroda": "bob", "icici": "icici", "union": "union", "paytm": "paytm",
    "standard_chartered": "scb", "indian_bank": "indian_bank", "karnataka": "karnataka", "dbs": "dbs", "citibank": "citibank", "kvb": "kvb", "hsbc": "hsbc", "indusind": "indusind", "idbi": "idbi", "pnb": "pnb", "yes": "yes", "iob": "iob", "south_indian": "south_indian", "central_bank": "central_bank", "equitas_sfb": "equitas_sfb",
}
_CONFIDENT = ("MEDIUM", "HIGH", "VERY_HIGH")


def detect_spec_bank(pages: Sequence[Page]) -> tuple:
    """(spec bank_key or "", detector bank_id or ""): what the Slice 2 detector says about this statement. bank_key is
    empty when the detector is not confident or names a bank without a layout."""
    from .detector import detect_bank
    texts = ["\n".join(" ".join(w.text for w in ln) for ln in group_lines(p.words)) for p in pages[:6]]
    det = detect_bank(texts)
    if det.bank_id is None or det.confidence.name not in _CONFIDENT:
        return "", ""
    return DETECTOR_TO_SPEC_BANK.get(det.bank_id, ""), det.bank_id


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


def route_pages(pages: Sequence[Page], registry: LayoutRegistry, bank_key: str = "", use_detector: bool = False,
                allow_header_only: bool = False) -> RoutedExtraction:
    """allow_header_only: accept a layout whose header matched but whose bank is named nowhere (policy choice; default off).
    use_detector: take bank_key from the Slice 2 detector when the caller gave none; a confident detection of a bank
    without a layout is a fallback (other_bank:<id>), never a header-only guess."""
    if not any(p.words for p in pages):
        return RoutedExtraction("unsupported", fallback_reason=SCANNED_NO_TEXT.lower())
    if use_detector and not bank_key:
        bank_key, detected = detect_spec_bank(pages)
        if not bank_key and detected:
            return RoutedExtraction("fallback", fallback_reason=f"other_bank:{detected}")
    res = registry.resolve(pages, bank_key)
    if res.spec is None:
        return RoutedExtraction("fallback", fallback_reason=res.status, candidates=res.candidates, notes=res.notes + [f"rejected:{x}" for x in res.rejected])
    if res.bank_evidence == "none" and not allow_header_only:
        # a header match alone is not proof of the bank: without a bank name on the statement (or a detector bank that
        # agrees with the layout) the result could not be trusted as this bank's, so v2 is not used
        return RoutedExtraction("fallback", fallback_reason="bank_unconfirmed", candidates=res.candidates, notes=res.notes + [f"layout:{res.spec.layout_id}"])
    outcome = extract_pages(pages, res.spec)
    result = to_extraction_result(outcome, res.spec)
    routed = RoutedExtraction("v2", res.spec.layout_id, result, candidates=res.candidates, notes=res.notes + list(outcome.notes) + [f"bank_evidence:{res.bank_evidence}"])
    if outcome.failure:
        code = outcome.failure
        routed.status = "fallback" if code in _RECOVERABLE else "v2"
        if routed.status == "fallback":
            routed.fallback_reason = f"v2_failed:{code}"
    return routed


def route_pdf(pdf_path: str, registry: LayoutRegistry, password: Optional[str] = None, bank_key: str = "", use_detector: bool = True,
              allow_header_only: bool = False) -> RoutedExtraction:
    try:
        pages = read_pages(pdf_path, password)
    except Exception as exc:   # pdfplumber / pdfminer raise several types for encrypted or broken files
        return RoutedExtraction("unsupported", fallback_reason=(LOCKED if _is_password_error(exc) else READ_ERROR).lower())
    return route_pages(pages, registry, bank_key, use_detector, allow_header_only)
