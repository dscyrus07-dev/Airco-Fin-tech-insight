"""T4 OCR reader: OcrDocument -> guarded pages -> text layer -> T3 inference + engine + checks ->
independent amount verification -> verdict capped at REVIEW.

Policy (docs/ocr/UNIVERSAL_OCR_PHASE1.md, Part F decisions of 2026-10-21):
- OCR-derived statements are NEVER VERIFIED (code OCR_READER). The pre-cap verdict is recorded for evaluation.
- Table rows the recogniser emitted mis-shaped are left out, never re-placed by guesswork, and counted per
  page (OCR_TABLE_ROWS_DROPPED): a shifted cell would move money between debit and credit.
- Pages that fail OCR or a guard are listed; rows from the other pages are kept only if the existing checks do
  not FAIL (the existing failure policy decides). A partial result always carries OCR_PARTIAL_PAGES.
- No value is corrected anywhere; disagreements only add review codes and row warnings.
Never raises.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..universal import reader as _u
from .contracts import OcrDocument
from .grid import pages_from_ocr
from .line_layer import page_from_lines
from .guards import apply_guards
from .verify import NOT_RUN, VerifyReport, verify_rows

NOT_RUN_STATUS = "not_run"

OCR_READER = "OCR_READER"
OCR_PARTIAL_PAGES = "OCR_PARTIAL_PAGES"
OCR_UNCONFIRMED_AMOUNTS = "OCR_UNCONFIRMED_AMOUNTS"
OCR_NO_USABLE_PAGES = "OCR_NO_USABLE_PAGES"
OCR_TABLE_ROWS_DROPPED = "OCR_TABLE_ROWS_DROPPED"
OCR_FUSED_AMOUNTS = "OCR_FUSED_AMOUNTS"
OCR_NO_TEXT_BOXES = "OCR_NO_TEXT_BOXES"

TEXT_LAYER_ENV = "STATEMENT_ENGINE_OCR_TEXT_LAYER"
LAYERS = ("blocks", "lines")


def text_layer() -> str:
    """Which text layer feeds the engine.

    blocks (default) — coordinates invented from the VL model's table markup (ocr/grid.py).
    lines            — the recogniser's own text boxes (ocr/line_layer.py). Candidate replacement: the first
                       real-GPU run found the markup misstates the column structure on every split-layout
                       statement. Kept opt-in until measured against blocks on the same corpus."""
    v = (os.environ.get(TEXT_LAYER_ENV) or "blocks").strip().lower()
    return v if v in LAYERS else "blocks"

BUDGET_S = 30.0          # inference + extraction on the synthetic layer (OCR time is separate)


@dataclass
class OcrResult:
    verdict: str = "FAILED"                 # REVIEW | FAILED
    code: str = ""
    detail: str = ""
    universal: Optional[_u.UniversalResult] = None
    review_codes: List[str] = field(default_factory=list)
    pages_total: int = 0
    pages_ok: List[int] = field(default_factory=list)
    failed_pages: Dict[int, str] = field(default_factory=dict)    # page -> failure code
    rows_dropped: Dict[int, int] = field(default_factory=dict)    # page -> mis-shaped table rows left out
    fused_amounts: int = 0            # boxes holding two amounts: their split is estimated, not measured
    layer: str = "blocks"
    reading: str = ""                 # thorough | fast, as requested for this job
    layer_note: str = ""              # why the layer used differs from the one requested, if it does
    verification: VerifyReport = field(default_factory=VerifyReport)
    engine: str = ""
    verifier: str = ""
    ocr_elapsed_s: float = 0.0
    elapsed_s: float = 0.0
    bank_hint: str = "Unknown bank"

    @property
    def ok(self) -> bool:
        return self.verdict == "REVIEW" and self.universal is not None and self.universal.ok

    @property
    def partial(self) -> bool:
        return bool(self.failed_pages)

    def to_block(self) -> Dict[str, Any]:
        u = self.universal
        return {
            "tier": "T4",
            "engine": "ocr",
            "ocr_engine": self.engine,
            "verifier": self.verifier or None,
            "verdict": self.verdict,
            "code": self.code,
            "detail": (self.detail or "")[:200],
            "needs_review": True,
            "review_codes": list(self.review_codes),
            "anchored": False,
            "pre_cap_verdict": u.meta.get("checks_verdict") if u else None,
            "check_results": u.meta.get("check_results") if u else None,
            "rows": u.meta.get("rows", 0) if u else 0,
            "pages_total": self.pages_total,
            "pages_ok": list(self.pages_ok),
            "failed_pages": {str(k): v for k, v in sorted(self.failed_pages.items())},
            "rows_dropped": {str(k): v for k, v in sorted(self.rows_dropped.items())},
            "rows_dropped_total": sum(self.rows_dropped.values()),
            "text_layer": self.layer,
            "reading": self.reading or None,
            "layer_note": self.layer_note or None,
            "fused_amounts": self.fused_amounts,
            "partial": self.partial,
            "verification": self.verification.to_dict(),
            "ocr_elapsed_ms": round(self.ocr_elapsed_s * 1000, 1),
            "elapsed_ms": round(self.elapsed_s * 1000, 1),
            "bank_hint": self.bank_hint,
        }


def _row_amounts(nrow) -> List[Any]:
    t = nrow.txn
    vals = []
    for name in ("debit", "credit", "balance"):
        v = getattr(t, name, None)
        if v not in (None, "", 0):
            vals.append(v)
    return vals


def read_document(doc: OcrDocument, bank_hint: str = "Unknown bank", budget_s: float = BUDGET_S,
                  layer: Optional[str] = None) -> OcrResult:
    """`layer` (blocks | lines) overrides STATEMENT_ENGINE_OCR_TEXT_LAYER for this one document."""
    t0 = time.monotonic()
    res = OcrResult(bank_hint=bank_hint or "Unknown bank", engine=doc.engine, verifier=doc.verifier,
                    ocr_elapsed_s=doc.elapsed_s)
    try:
        if doc.error:
            res.code, res.detail = doc.error, "OCR request failed"
            return res
        res.pages_total = len(doc.pages)
        apply_guards(doc)
        res.failed_pages = {p.page: (p.error or "OCR_PAGE_FAILED") for p in doc.pages if not p.ok}
        ok_pages = sorted((p for p in doc.pages if p.ok), key=lambda p: p.page)
        res.pages_ok = [p.page for p in ok_pages]
        if not ok_pages:
            res.code, res.detail = OCR_NO_USABLE_PAGES, "no page could be read"
            return res
        res.layer = layer if layer in LAYERS else text_layer()
        if res.layer == "blocks" and not any(p.blocks for p in ok_pages) and any(p.lines for p in ok_pages):
            # the VL model did not run (the service is in lines-only mode): there is no markup to read, but the
            # line boxes are a text layer in their own right, so read those instead of refusing the document
            res.layer, res.layer_note = "lines", "VL_UNAVAILABLE"
        if res.layer == "lines":
            used, engine_pages = [], []
            for p in ok_pages:
                per: Dict[str, int] = {}
                page = page_from_lines(p, per)
                res.fused_amounts += per.get("fused_amounts", 0)
                if page is None:
                    # reported like any unread page, never treated as an empty one
                    res.failed_pages[p.page] = OCR_NO_TEXT_BOXES
                else:
                    used.append(p)
                    engine_pages.append(page)
            ok_pages = used
            res.pages_ok = [p.page for p in ok_pages]
            if not engine_pages:
                res.code, res.detail = OCR_NO_USABLE_PAGES, "no page carried a text box"
                return res
        else:
            engine_pages = pages_from_ocr(ok_pages, res.rows_dropped)
        u = _u.read(pages=engine_pages, bank_hint=res.bank_hint, budget_s=budget_s)
        res.universal = u
        if not u.ok:
            res.verdict, res.code = "FAILED", u.code or "OCR_READ_FAILED"
            res.detail = u.detail
            if res.rows_dropped:
                res.review_codes = [OCR_TABLE_ROWS_DROPPED]
            return res
        # provenance: engine page k (1-based over the usable pages) -> source page number
        src = {i + 1: p.page for i, p in enumerate(ok_pages)}
        rows = u.outcome.rows if u.outcome else []
        if res.layer == "lines":
            # The rows were READ FROM these lines, so checking their amounts against the same lines would confirm
            # every one of them and claim a second reading that never happened. There is no independent reader
            # on this path: say so (OCR_VERIFIER_NOT_RUN) instead of reporting a check that is circular.
            res.verification = VerifyReport(status=NOT_RUN_STATUS, pages_without_verifier=[p.page for p in ok_pages])
        else:
            res.verification = verify_rows([(src.get(r.page, r.page), _row_amounts(r)) for r in rows], ok_pages)
        for i, codes in res.verification.row_flags.items():
            rows[i].row_warnings.extend(c for c in codes if c not in rows[i].row_warnings)
        for i, r in enumerate(rows):
            r.page = src.get(r.page, r.page)
            extras = dict(r.txn.extras or {})
            extras["source_page"] = r.page          # provenance: original PDF page of this row
            extras["extraction"] = "ocr"
            if i in res.verification.row_flags:
                extras["ocr_flags"] = list(res.verification.row_flags[i])
            r.txn.extras = extras
        codes = [OCR_READER]
        if res.partial:
            codes.append(OCR_PARTIAL_PAGES)
        if res.rows_dropped:
            codes.append(OCR_TABLE_ROWS_DROPPED)
        if res.fused_amounts:
            codes.append(OCR_FUSED_AMOUNTS)
        if res.verification.unconfirmed or res.verification.low_confidence:
            codes.append(OCR_UNCONFIRMED_AMOUNTS)
        if res.verification.status != "ran":
            codes.append(NOT_RUN)
        res.review_codes = codes
        res.verdict, res.code = "REVIEW", OCR_READER
        res.detail = "capped from VERIFIED" if u.meta.get("checks_verdict") == "VERIFIED" else u.detail
        return res
    except Exception as exc:                                   # defence in depth: never raise
        res.verdict, res.code, res.detail = "FAILED", "OCR_CRASH", type(exc).__name__
        return res
    finally:
        res.elapsed_s = time.monotonic() - t0
