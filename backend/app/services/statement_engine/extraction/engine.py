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
from .normalize import NormalizeError, NormalizedRow, normalize_rows, parse_amount
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


def _split_merged_dates(words: Sequence[Word], spec: LayoutSpec) -> List[Word]:
    """A date cell can be extracted fused with the start of the narration ("08-Apr-22 NEFT" or "04-01-2024DEBIT"): split
    after the longest leading part that is a complete date, dividing the x-extent by character count."""
    out: List[Word] = []
    for w in words:
        text = w.text
        stripped = text.strip()
        if len(stripped) > 6 and not spec.date_re.match(stripped):
            cut_at = next((i for i in range(len(text) - 1, 5, -1) if spec.date_re.match(text[:i].strip()) and text[i:].strip()), None)
            if cut_at is not None:
                cut = w.x0 + (w.x1 - w.x0) * cut_at / len(text)
                out.append(Word(text[:cut_at].strip(), w.x0, cut, w.top, w.bottom))
                out.append(Word(text[cut_at:].strip(), cut, w.x1, w.top, w.bottom))
                continue
        out.append(w)
    return out


def _merge_drcr_suffix(words: Sequence[Word], spec: LayoutSpec) -> List[Word]:
    """Attach a separate "Cr"/"Dr" word to the amount printed immediately before it on the same line."""
    out: List[Word] = []
    for w in words:
        if w.text.strip().lower() in ("cr", "dr") and out:
            prev = out[-1]
            if abs(prev.top - w.top) <= 3.0 and -1.0 <= w.x0 - prev.x1 <= 12.0 and spec.amount_re.match(prev.text.strip()):
                out[-1] = Word(prev.text.strip() + w.text.strip(), prev.x0, w.x1, prev.top, prev.bottom)
                continue
        out.append(w)
    return out


def extract_pages(pages: Sequence[Page], spec: LayoutSpec) -> V2Outcome:
    out = V2Outcome()
    pages = [Page(_split_merged_dates(p.words, spec), p.width) for p in pages]
    if spec.merge_drcr_suffix:
        pages = [Page(_merge_drcr_suffix(p.words, spec), p.width) for p in pages]
    if not pages:
        out.failure, out.failure_detail = NO_TABLE_HEADER, "no pages"
        return out
    anchors = None
    skipped = 0
    for skipped, first in enumerate(pages):     # a cover / portfolio page may precede the table: anchor on the first page that carries the header
        try:
            anchors = derive_anchors(first.words, spec, first.width)
            break
        except AnchorError as exc:
            last_error = exc
    if anchors is None:
        out.failure, out.failure_detail = NO_TABLE_HEADER, str(last_error)
        return out
    pages = pages[skipped:]       # pages before the header page (cover, portfolio summary) carry no table rows
    out.anchors = anchors
    table = assemble(pages, anchors, spec)
    out.table = table
    out.period = table.period
    out.warnings.extend(table.warnings)
    page1_text = "".join(squash(line) for line in group_lines(first.words))
    m = spec.ifsc_re.search(page1_text) if spec.ifsc_re else None
    out.ifsc = m.group(0) if m else ""
    out.account_number = _account_number(first.words, spec)
    if spec.summary_label_text and spec.summary_position == "before":
        above = [ln for ln in group_lines(first.words) if max(w.bottom for w in ln) <= anchors.header_top + 1.0]
        out.summary = parse_summary(above, spec) if above else None
    else:
        out.summary = parse_summary(table.summary_lines, spec) if table.summary_lines and spec.summary_label_text else None
    row_opening = None
    if spec.opening_row_marker and table.rows and re.sub(r"\s+", "", table.rows[0].narration).upper().startswith(spec.opening_row_marker):
        first_row = table.rows.pop(0)
        try:
            row_opening = parse_amount(first_row.amounts.get(spec.balance_column, ""), suffix_sign=True)
        except (ArithmeticError, NormalizeError):
            row_opening = None
    if spec.closing_row_marker and table.rows and re.sub(r"\s+", "", table.rows[-1].narration).upper().startswith(spec.closing_row_marker):
        last_row = table.rows.pop()
        printed = last_row.amounts.get(spec.balance_column, "")
        try:
            val = parse_amount(printed, suffix_sign=True)
            table.printed_closing = None if val is None else str(val)
        except NormalizeError:
            pass
    if spec.closing_balance_re and not table.printed_closing:
        for ln in table.summary_lines:
            mc = spec.closing_balance_re.search(squash(ln))
            if mc:
                table.printed_closing = mc.group(1)
                break
    if out.summary is None and (spec.opening_balance_re or spec.closing_balance_re or spec.totals_line_re or row_opening is not None):
        # printed opening / closing balance lines are still references to verify the derived values against
        opening = closing = debits = credits = None
        try:
            mo = spec.opening_balance_re.search(page1_text) if spec.opening_balance_re else None
            if mo:
                opening = Decimal(mo.group(1).replace(",", ""))
            elif row_opening is not None:
                opening = row_opening
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
