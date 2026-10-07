"""pdfplumber glue: the only module of the extraction package that touches a PDF library.

LayoutExtractor implements the migration StatementExtractor protocol for any LayoutSpec and returns a RAW
ExtractionResult (no repair, no classification). The password is used in memory only.
"""
from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from app.services.migration.contract import ExtractionResult
from app.services.pipeline.models import StatementMetadata

from .engine import V2Outcome, extract_pages
from .layout_spec import LayoutSpec
from .rows import Page
from .words import Word

LOCKED = "LOCKED"
SCANNED_NO_TEXT = "SCANNED_NO_TEXT"
READ_ERROR = "READ_ERROR"

# word extraction parameters (kept explicit; the pure engine does not depend on them)
_WORD_KWARGS = dict(keep_blank_chars=True, x_tolerance=2, y_tolerance=2)


def read_pages(pdf_path: str, password: Optional[str] = None) -> List[Page]:
    import pdfplumber

    pages: List[Page] = []
    with pdfplumber.open(pdf_path, password=password or None) as pdf:
        for i in range(len(pdf.pages)):
            pg = pdf.pages[i]
            words = [Word(w["text"], float(w["x0"]), float(w["x1"]), float(w["top"]), float(w["bottom"]))
                     for w in pg.extract_words(**_WORD_KWARGS)]
            pages.append(Page(words=words, width=float(pg.width)))
            pg.flush_cache()   # release parsed page objects: keeps a 277-page file at ~50 MB instead of ~2 GB
    return pages


def to_extraction_result(outcome: V2Outcome, spec: LayoutSpec) -> ExtractionResult:
    if outcome.failure:
        return ExtractionResult(
            engine="v2", metadata=StatementMetadata(bank_name=spec.bank_name, bank_key=spec.bank_key), transactions=[],
            failure=f"{outcome.failure}: {outcome.failure_detail}", warnings=list(outcome.warnings),
        )
    checks = outcome.checks
    derived = checks.derived if checks else {}
    period = outcome.period
    summ = outcome.summary
    meta = StatementMetadata(
        bank_name=spec.bank_name, bank_key=spec.bank_key, account_number=outcome.account_number,
        opening_balance=derived.get("opening") or Decimal("0"),
        closing_balance=derived.get("closing") or Decimal("0"),
        statement_from=period[0] if period else "", statement_to=period[1] if period else "",
        extras={
            "layout_id": spec.layout_id, "ifsc": outcome.ifsc,
            "verdict": checks.verdict if checks else None, "verdict_reasons": list(checks.reasons) if checks else [],
            "checks": {k: {"status": v.status, **{dk: dv for dk, dv in v.detail.items() if dk in ("outcome", "breaks", "opening_matches", "closing_matches")}} for k, v in (checks.results.items() if checks else [])},
            "printed_summary": None if summ is None else {
                "opening": str(summ.opening), "closing": str(summ.closing),
                "dr_count": summ.dr_count, "cr_count": summ.cr_count,
                "debits": str(summ.debits), "credits": str(summ.credits)},
        },
    )
    return ExtractionResult(
        engine="v2", metadata=meta, transactions=[r.txn for r in outcome.rows],
        printed_total_debit=summ.debits if summ else None,
        printed_total_credit=summ.credits if summ else None,
        printed_totals_reconciled=(checks.results["totals"].detail.get("outcome") in ("MATCH", "RECONCILED_VIA_REVERSALS")) if checks else None,
        verification_status=checks.verdict if checks else None,
        warnings=list(outcome.warnings) + (list(checks.reasons) if checks else []),
    )


def _is_password_error(exc: BaseException) -> bool:
    """pdfplumber wraps pdfminer errors (PdfminerException(PDFPasswordIncorrect)), so inspect the wrapped exception too."""
    seen = []
    stack = [exc]
    while stack and len(seen) < 6:
        e = stack.pop()
        seen.append(e)
        text = f"{type(e).__name__} {e}"
        if "Password" in text or "Encrypt" in text or "encrypt" in text:
            return True
        stack.extend(a for a in getattr(e, "args", ()) if isinstance(a, BaseException))
        if e.__cause__ is not None:
            stack.append(e.__cause__)
    return False


class LayoutExtractor:
    """StatementExtractor for one layout specification."""

    def __init__(self, spec: LayoutSpec, name: Optional[str] = None):
        self.spec = spec
        self.name = name or f"{spec.bank_key}_v2"

    def _failure(self, text: str) -> ExtractionResult:
        return ExtractionResult(engine="v2", metadata=StatementMetadata(bank_name=self.spec.bank_name, bank_key=self.spec.bank_key),
                                transactions=[], failure=text)

    def extract(self, pdf_path: str, password: Optional[str] = None) -> ExtractionResult:
        try:
            pages = read_pages(pdf_path, password)
        except Exception as exc:  # pdfplumber/pdfminer raise several types for encrypted or broken files
            name = type(exc).__name__
            code = LOCKED if _is_password_error(exc) else READ_ERROR
            return self._failure(f"{code}: {name}")
        if not any(p.words for p in pages):
            return self._failure(f"{SCANNED_NO_TEXT}: no text layer")
        return to_extraction_result(extract_pages(pages, self.spec), self.spec)
