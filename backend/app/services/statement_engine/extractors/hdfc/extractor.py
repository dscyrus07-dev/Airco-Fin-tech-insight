"""pdfplumber glue: the only module in this package that touches a PDF library.

Implements the migration StatementExtractor protocol and returns a RAW ExtractionResult (no repair, no
classification). Password is used in memory only.
"""
from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from app.services.migration.contract import ExtractionResult
from app.services.pipeline.models import StatementMetadata

from .engine import V2Outcome, extract_pages
from .layout_spec import HDFC_LAYOUT_A, LayoutSpec
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
        for pg in pdf.pages:
            words = [Word(w["text"], float(w["x0"]), float(w["x1"]), float(w["top"]), float(w["bottom"]))
                     for w in pg.extract_words(**_WORD_KWARGS)]
            pages.append(Page(words=words, width=float(pg.width)))
    return pages


def _iso(printed: str) -> str:
    d, m, y = printed.split("/")
    return f"{y}-{m}-{d}"


def to_extraction_result(outcome: V2Outcome, spec: LayoutSpec = HDFC_LAYOUT_A) -> ExtractionResult:
    if outcome.failure:
        return ExtractionResult(
            engine="v2", metadata=StatementMetadata(bank_name="HDFC Bank", bank_key=spec.bank_key), transactions=[],
            failure=f"{outcome.failure}: {outcome.failure_detail}", warnings=list(outcome.warnings),
        )
    checks = outcome.checks
    derived = checks.derived if checks else {}
    period = outcome.period
    meta = StatementMetadata(
        bank_name="HDFC Bank", bank_key=spec.bank_key, account_number=outcome.account_number,
        opening_balance=derived.get("opening") or Decimal("0"),
        closing_balance=derived.get("closing") or Decimal("0"),
        statement_from=period[0] if period else "", statement_to=period[1] if period else "",
        extras={
            "layout_id": spec.layout_id, "ifsc": outcome.ifsc,
            "verdict": checks.verdict if checks else None, "verdict_reasons": list(checks.reasons) if checks else [],
            "checks": {k: {"status": v.status, **{dk: dv for dk, dv in v.detail.items() if dk in ("outcome", "breaks", "opening_matches", "closing_matches")}} for k, v in (checks.results.items() if checks else [])},
            "printed_summary": None if outcome.summary is None else {
                "opening": str(outcome.summary.opening), "closing": str(outcome.summary.closing),
                "dr_count": outcome.summary.dr_count, "cr_count": outcome.summary.cr_count,
                "debits": str(outcome.summary.debits), "credits": str(outcome.summary.credits)},
        },
    )
    return ExtractionResult(
        engine="v2", metadata=meta, transactions=[r.txn for r in outcome.rows],
        printed_total_debit=outcome.summary.debits if outcome.summary else None,
        printed_total_credit=outcome.summary.credits if outcome.summary else None,
        verification_status=checks.verdict if checks else None,
        warnings=list(outcome.warnings) + (list(checks.reasons) if checks else []),
    )


class HDFCV2Extractor:
    name = "hdfc_v2"

    def __init__(self, spec: LayoutSpec = HDFC_LAYOUT_A):
        self.spec = spec

    def extract(self, pdf_path: str, password: Optional[str] = None) -> ExtractionResult:
        try:
            pages = read_pages(pdf_path, password)
        except Exception as exc:  # pdfplumber/pdfminer raise several types for encrypted or broken files
            name = type(exc).__name__
            code = LOCKED if "Password" in name or "Encrypt" in name else READ_ERROR
            return ExtractionResult(engine="v2", metadata=StatementMetadata(bank_name="HDFC Bank", bank_key=self.spec.bank_key),
                                    transactions=[], failure=f"{code}: {name}")
        if not any(p.words for p in pages):
            return ExtractionResult(engine="v2", metadata=StatementMetadata(bank_name="HDFC Bank", bank_key=self.spec.bank_key),
                                    transactions=[], failure=f"{SCANNED_NO_TEXT}: no text layer")
        return to_extraction_result(extract_pages(pages, self.spec), self.spec)
