"""T4 OCR serving: flag-gated helpers for the pipeline orchestrator and the analysis service.

STATEMENT_ENGINE_OCR_MODE=off|shadow|serve (default off)

off    — nothing runs; behaviour identical to baseline (scanned PDFs keep today's "not supported" message).
shadow — when no other tier produced a result for a SCANNED/MIXED file, run T4 and record the block only;
         the job fails exactly as it does today.
serve  — same trigger, and REVIEW rows are served through the same downstream steps as T3
         (reconcile, classify, Excel + Statement Check, history). FAILED carries no data. Never VERIFIED.

T4 runs only when the PDF's capability is SCANNED or MIXED, so the text path never pays for OCR.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from ..serve import V2RowSource
from ..universal.serve import row_source_from_outcome
from . import client as _client
from .reader import OcrResult, read_document

ENV = "STATEMENT_ENGINE_OCR_MODE"
_MODES = ("off", "shadow", "serve")
OCR_CAPABILITIES = ("SCANNED", "MIXED")


def mode() -> str:
    m = (os.environ.get(ENV) or "off").strip().lower()
    return m if m in _MODES else "off"


def enabled() -> bool:
    return mode() != "off" and _client.configured()


def wants(capability: Optional[str]) -> bool:
    """True when T4 should be attempted for a file of this capability."""
    return enabled() and (capability or "") in OCR_CAPABILITIES


def attempt(pdf_path: str, bank_hint: str = "Unknown bank",
            page_count: Optional[int] = None) -> Tuple[OcrResult, Optional[V2RowSource]]:
    """OCR every page (MIXED files too: one coordinate system per document), then read. Never raises."""
    try:
        doc = _client.ocr_pdf(pdf_path, None, verify=True, page_count=page_count)
        res = read_document(doc, bank_hint=bank_hint)
        return res, (row_source_from_outcome(res.universal) if res.ok else None)
    except Exception as exc:                                    # defence in depth
        r = OcrResult(code="OCR_CRASH", detail=type(exc).__name__, bank_hint=bank_hint)
        return r, None


def detection_texts(pdf_path: str, pages: Tuple[int, ...] = (1, 2)) -> Tuple[List[str], Dict[str, Any]]:
    """Analysis-time OCR for bank detection only: pages 1-2 under a strict timeout.
    Returns (page_texts, info). Empty texts on any failure: the user then picks the bank."""
    from .grid import page_text
    from .guards import apply_guards

    info: Dict[str, Any] = {"attempted": False, "ok": False, "code": ""}
    if not enabled():
        info["code"] = "OCR_DISABLED"
        return [], info
    info["attempted"] = True
    doc = _client.ocr_pdf(pdf_path, list(pages), verify=False, timeout_s=_client.detect_timeout_s())
    if doc.error:
        info["code"] = doc.error
        return [], info
    apply_guards(doc)
    texts = [page_text(p) for p in sorted(doc.pages, key=lambda p: p.page) if p.ok]
    info.update(ok=bool(texts), code="" if texts else "OCR_NO_TEXT", elapsed_ms=round(doc.elapsed_s * 1000, 1))
    return texts, info


def engine_block_for(res: OcrResult, o_mode: str, detected_bank: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Top-level statement_engine block when T4 served the result."""
    return {
        "engine": "ocr",
        "mode": o_mode,
        "layout_id": "ocr_auto",
        "verdict": "REVIEW",
        "needs_review": True,
        "review_codes": list(res.review_codes),
        "anchored": False,
        "detected_bank": detected_bank,
        "advisory": None,
        "ocr": dict(res.to_block(), served=True, mode=o_mode),
    }


def block_for(res: OcrResult, *, served: bool, o_mode: str) -> Dict[str, Any]:
    return dict(res.to_block(), served=served, mode=o_mode)


def audit_attempt(audit_service, job_id: Optional[str], block: Dict[str, Any]) -> None:
    """Structured job event: verdict, codes, page numbers and timing only — never document content."""
    if not audit_service or not job_id:
        return
    try:
        audit_service.create_job_event(job_id, event_type="t4_ocr_decision", event_name="t4_ocr_decision",
                                       event_category="ocr", metadata=dict(block))
    except Exception:
        pass
