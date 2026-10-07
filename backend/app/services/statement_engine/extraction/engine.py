"""Pure, layout-neutral extraction over pages of words (no PDF library); everything bank-specific comes from the
LayoutSpec. The pdfplumber glue is in pdf_extractor.py."""
from __future__ import annotations

import re
from decimal import Decimal
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from .anchors import AnchorError, ColumnAnchors, derive_anchors
from .checks import Checks, run_checks
from .layout_spec import LayoutSpec
from .normalize import NormalizedRow, normalize_rows
from .rows import AssembledTable, Page, assemble
from .summary import PrintedSummary, parse_summary
from .words import Word, group_lines, norm_token, squash

# failure codes (design section 13)
NO_TABLE_HEADER = "NO_TABLE_HEADER"
NO_ROWS = "NO_ROWS"


@dataclass
class V2Outcome:
    failure: Optional[str] = None
    failure_detail: str = ""
    rows: List[NormalizedRow] = field(default_factory=list)
    anchors: Optional[ColumnAnchors] = None
    table: Optional[AssembledTable] = None
    period: Optional[Tuple[str, str]] = None
    summary: Optional[PrintedSummary] = None
    checks: Optional[Checks] = None
    account_number: str = ""
    ifsc: str = ""
    warnings: List[str] = field(default_factory=list)


def _account_number(page_words: Sequence[Word], spec: LayoutSpec) -> str:
    """Value following the account label; the label may be one printed word ("AccountNo") or several ("Account No")."""
    if not spec.account_label:
        return ""
    for line in group_lines(page_words):
        for i in range(len(line)):
            acc = ""
            for j in range(i, len(line)):
                acc += norm_token(line[j].text)
                if acc == spec.account_label:
                    for nxt in line[j + 1:]:
                        t = nxt.text.strip()
                        if t and t != ":" and re.fullmatch(r"\d{6,}", t):
                            return t
                        found = re.search(r"\d{6,}", t) if t.startswith(":") else None
                        if found:
                            return found.group(0)
                    break
                if not spec.account_label.startswith(acc):
                    break
    return ""


def extract_pages(pages: Sequence[Page], spec: LayoutSpec) -> V2Outcome:
    out = V2Outcome()
    if not pages:
        out.failure, out.failure_detail = NO_TABLE_HEADER, "no pages"
        return out
    first = pages[0]
    try:
        anchors = derive_anchors(first.words, spec, first.width)
    except AnchorError as exc:
        out.failure, out.failure_detail = NO_TABLE_HEADER, str(exc)
        return out
    out.anchors = anchors
    table = assemble(pages, anchors, spec)
    out.table = table
    out.period = table.period
    out.warnings.extend(table.warnings)
    page1_text = "".join(squash(line) for line in group_lines(first.words))
    m = spec.ifsc_re.search(page1_text) if spec.ifsc_re else None
    out.ifsc = m.group(0) if m else ""
    out.account_number = _account_number(first.words, spec)
    out.summary = parse_summary(table.summary_lines, spec) if table.summary_lines and spec.summary_label_text else None
    if out.summary is None and (spec.opening_balance_re or spec.closing_balance_re or spec.totals_line_re):
        # printed opening / closing balance lines are still references to verify the derived values against
        opening = closing = debits = credits = None
        try:
            mo = spec.opening_balance_re.search(page1_text) if spec.opening_balance_re else None
            if mo:
                opening = Decimal(mo.group(1).replace(",", ""))
            if table.printed_closing:
                closing = Decimal(table.printed_closing.replace(",", ""))
            if table.printed_totals:
                debits, credits = (Decimal(x.replace(",", "")) for x in table.printed_totals)
        except ArithmeticError:
            opening = closing = debits = credits = None
        if any(v is not None for v in (opening, closing, debits, credits)):
            out.summary = PrintedSummary(opening=opening, closing=closing, debits=debits, credits=credits)
    rows, errors = normalize_rows(table.rows, spec)
    out.rows = rows
    if not table.rows and not (out.summary and out.summary.dr_count == 0 and out.summary.cr_count == 0):
        out.failure, out.failure_detail = NO_ROWS, "header found but no transaction rows"
        return out
    out.checks = run_checks(rows, out.period, out.summary, errors, out.warnings, spec.period_date_format, spec.summary_expected,
                          spec.dates_monotonic_expected, spec.period_tolerance_days,
                          spec.side_flip_policy)
    return out
