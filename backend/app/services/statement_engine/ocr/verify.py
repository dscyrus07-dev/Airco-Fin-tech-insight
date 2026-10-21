"""Independent amount verification against a second recogniser (PP-OCRv5 lines with their own scores).

For every extracted row, each printed amount (debit, credit, balance) is looked up among the verifier's text
lines on the SAME source page. Outcomes per amount:

    confirmed       the amount string appears in a verifier line with score >= MIN_SCORE
    low_confidence  it appears only in lines scored below MIN_SCORE
    unconfirmed     the verifier did not read this amount on that page

Nothing is corrected. Disagreement only adds row warnings and review codes. When the verifier produced no lines
for a page, its rows are 'not_run' (no confidence is assumed either way).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .contracts import OcrPage

MIN_SCORE = float(os.environ.get("STATEMENT_ENGINE_OCR_MIN_SCORE", "0.90"))

UNCONFIRMED = "OCR_AMOUNT_UNCONFIRMED"
LOW_CONFIDENCE = "OCR_AMOUNT_LOW_CONFIDENCE"
NOT_RUN = "OCR_VERIFIER_NOT_RUN"

_NUM = re.compile(r"\d[\d,]*\.\d{2}|\d[\d,]*")


def _canon(v) -> Optional[str]:
    """Decimal value -> canonical '1234.56' (no separators, two decimals)."""
    if v is None or v == "":
        return None
    try:
        d = Decimal(str(v)).copy_abs().quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None
    return f"{d:.2f}"


def _line_amounts(text: str) -> Set[str]:
    out: Set[str] = set()
    for m in _NUM.findall((text or "").replace(" ", "")):
        c = _canon(m.replace(",", ""))
        if c is not None:
            out.add(c)
    return out


@dataclass
class VerifyReport:
    status: str = "not_run"          # ran | partial | not_run
    amounts_checked: int = 0
    confirmed: int = 0
    low_confidence: int = 0
    unconfirmed: int = 0
    rows_flagged: int = 0
    pages_without_verifier: List[int] = field(default_factory=list)
    row_flags: Dict[int, List[str]] = field(default_factory=dict)   # row index -> codes

    def to_dict(self) -> Dict:
        return {"status": self.status, "amounts_checked": self.amounts_checked, "confirmed": self.confirmed,
                "low_confidence": self.low_confidence, "unconfirmed": self.unconfirmed,
                "rows_flagged": self.rows_flagged, "pages_without_verifier": self.pages_without_verifier,
                "min_score": MIN_SCORE}


def verify_rows(rows: Sequence[Tuple[int, Iterable]], pages: Sequence[OcrPage]) -> VerifyReport:
    """rows: (source_page_number, amounts) per extracted row, in row order. pages: the OCR pages."""
    by_page: Dict[int, Tuple[Set[str], Set[str]]] = {}
    for p in pages:
        if not p.lines:
            continue
        good, weak = set(), set()
        for ln in p.lines:
            (good if ln.score >= MIN_SCORE else weak).update(_line_amounts(ln.text))
        by_page[p.page] = (good, weak - good)
    rep = VerifyReport()
    if not by_page:
        rep.pages_without_verifier = sorted({pg for pg, _ in rows})
        return rep
    missing_pages: Set[int] = set()
    for i, (pg, amounts) in enumerate(rows):
        if pg not in by_page:
            missing_pages.add(pg)
            continue
        good, weak = by_page[pg]
        codes: List[str] = []
        for a in amounts:
            c = _canon(a)
            if c is None:
                continue
            rep.amounts_checked += 1
            if c in good:
                rep.confirmed += 1
            elif c in weak:
                rep.low_confidence += 1
                codes.append(LOW_CONFIDENCE)
            else:
                rep.unconfirmed += 1
                codes.append(UNCONFIRMED)
        if codes:
            rep.row_flags[i] = sorted(set(codes))
    rep.rows_flagged = len(rep.row_flags)
    rep.pages_without_verifier = sorted(missing_pages)
    rep.status = "partial" if missing_pages else "ran"
    return rep
