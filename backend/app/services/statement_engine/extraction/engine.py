"""Pure, layout-neutral extraction over pages of words (no PDF library); everything bank-specific comes from the
LayoutSpec. The pdfplumber glue is in pdf_extractor.py."""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from .anchors import AnchorError, ColumnAnchors, derive_anchors
from .checks import Checks, parse_period_date, run_checks
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
    notes: List[str] = field(default_factory=list)          # informational, never a review reason
    schema_errors: List[str] = field(default_factory=list)
    consumed_pages: int = 0                                  # pages (of the input list) up to and including this statement's end


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
            cut_at = next((i for i in range(len(text) - 1, 5, -1) if spec.date_re.match(text[:i].strip()) and text[i:].strip()
                           and not (text[i].isdigit() or text[i] in "/-.,:")), None)   # never cut inside a longer date such as 01/04/2023
            if cut_at is not None:
                cut = w.x0 + (w.x1 - w.x0) * cut_at / len(text)
                out.append(Word(text[:cut_at].strip(), w.x0, cut, w.top, w.bottom))
                out.append(Word(text[cut_at:].strip(), cut, w.x1, w.top, w.bottom))
                continue
        out.append(w)
    return out


def _split_monospace(words: Sequence[Word]) -> List[Word]:
    """A text-rendered (fixed-pitch) page is read as one word per line: split on whitespace and place each piece by its
    character offset, so the ordinary header-anchored column logic applies."""
    out: List[Word] = []
    for w in words:
        text = w.text
        if len(text) < 2 or not re.search(r"\s", text.strip()):
            out.append(w)
            continue
        pitch = (w.x1 - w.x0) / len(text)
        for m in re.finditer(r"\S+", text):
            out.append(Word(m.group(), w.x0 + m.start() * pitch, w.x0 + m.end() * pitch, w.top, w.bottom))
    return out


def _merge_drcr_suffix(words: Sequence[Word], spec: LayoutSpec) -> List[Word]:
    """Attach a separate "Cr"/"Dr" word to the amount printed immediately before it on the same line."""
    out: List[Word] = []
    for w in words:
        if re.match(r"(?i)^\(?(cr|dr)\)?\.?$", w.text.strip()) and out:
            prev = out[-1]
            if abs(prev.top - w.top) <= 3.0 and -1.0 <= w.x0 - prev.x1 <= 12.0 and spec.amount_re.match(prev.text.strip()):
                out[-1] = Word(prev.text.strip() + w.text.strip(), prev.x0, w.x1, prev.top, prev.bottom)
                continue
        out.append(w)
    return out


def _prepare_amounts(words: Sequence[Word], spec: LayoutSpec) -> List[Word]:
    """Strip the currency prefix and attach a standalone +/- word to the amount that follows it."""
    out: List[Word] = []
    for w in words:
        text = w.text.strip()
        if spec.amount_sign_gap:
            collapsed = re.sub(r"^([+-])\s+", r"\g<1>", text)
            if collapsed != text:
                text = collapsed
                w = Word(text, w.x0, w.x1, w.top, w.bottom)
        if spec.amount_prefix:
            stripped = re.sub(r"^([+-]?)\s*" + "(?:" + "|".join(re.escape(x) for x in spec.amount_prefix.split("|") if x) + r")\s*", r"\1", text)
            if stripped != text:
                text = stripped
                w = Word(text, w.x0, w.x1, w.top, w.bottom)
        if spec.merge_sign_prefix and out and out[-1].text.strip() in ("+", "-") and abs(out[-1].top - w.top) <= 3.0 \
                and 0.0 <= w.x0 - out[-1].x1 <= 14.0 and spec.amount_re.match(text):
            prev = out.pop()
            w = Word(prev.text.strip() + text, prev.x0, w.x1, w.top, w.bottom)
        out.append(w)
    return out


def _document_anchors(pages: Sequence[Page], spec: LayoutSpec) -> Tuple[List[Decimal], List[Decimal], List[Tuple[str, str]]]:
    """Whole-document anchor scan (opt-in spec.anchor_scan == "document"): every page's lines are searched for the
    layout's opening/closing/totals labels, in statement order. Returns the ordered DISTINCT printed values for
    opening and closing plus every printed totals pair."""
    openings: List[Decimal] = []
    closings: List[Decimal] = []
    totals: List[Tuple[str, str]] = []
    for pg in pages:
        lines = group_lines(pg.words)
        for ln in lines:
            flat = squash(ln)
            for rx, acc in ((spec.opening_balance_re, openings), (spec.closing_balance_re, closings)):
                if rx is not None:
                    m = rx.search(flat)
                    if m:
                        try:
                            v = Decimal(m.group(1).replace(",", ""))
                            if v not in acc:
                                acc.append(v)
                        except ArithmeticError:
                            pass
            if spec.totals_line_re is not None:
                mt = spec.totals_line_re.search(flat)
                if mt:
                    g = mt.groups()
                    pair = (g[1], g[0]) if spec.totals_credit_first and len(g) >= 2 else (g[0], g[1])
                    if pair not in totals:
                        totals.append(pair)
        if spec.opening_balance_re is not None:
            # the label and the value may sit on separate lines: the page-level scan keeps that case
            mo = spec.opening_balance_re.search("".join(squash(ln) for ln in lines))
            if mo:
                try:
                    v = Decimal(mo.group(1).replace(",", ""))
                    if v not in openings:
                        openings.append(v)
                except ArithmeticError:
                    pass
    return openings, closings, totals


def _prepare_pages(pages: Sequence[Page], spec: LayoutSpec) -> List[Page]:
    """The layout's word preparation (monospace split, amount prefixes, merged dates, Dr/Cr suffixes), shared by the
    extractor and the completeness guard so both see the same words."""
    if spec.monospace_text:
        pages = [Page(_split_monospace(p.words), p.width) for p in pages]
    if spec.amount_prefix or spec.merge_sign_prefix or spec.amount_sign_gap:
        pages = [Page(_prepare_amounts(p.words, spec), p.width) for p in pages]
    pages = [Page(_split_merged_dates(p.words, spec), p.width) for p in pages]
    if spec.merge_drcr_suffix:
        pages = [Page(_merge_drcr_suffix(p.words, spec), p.width) for p in pages]
    return list(pages)


def _extract_one(pages: Sequence[Page], spec: LayoutSpec) -> V2Outcome:
    out = V2Outcome()
    pages = _prepare_pages(pages, spec)
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
    consumed_base = skipped
    out.anchors = anchors
    table = assemble(pages, anchors, spec)
    out.table = table
    out.consumed_pages = consumed_base + (table.summary_page or len(pages))
    out.period = table.period
    if spec.year_from_period:
        _add_years(table.rows, table.period, spec)
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
    doc_opening: Optional[Decimal] = None
    if spec.anchor_scan == "document":
        doc_openings, doc_closings, doc_totals = _document_anchors(pages, spec)
        segmented = spec.segment_header_re is not None
        if len(doc_openings) > 1 and not segmented:           # multi-account docs legitimately print an opening
            out.warnings.append("anchor_conflict:opening")    # per segment; per-segment anchors are checkpointed
        elif doc_openings:
            doc_opening = doc_openings[0]                     # first printed opening in statement order
        if len(doc_closings) > 1 and not segmented:
            out.warnings.append("anchor_conflict:closing")
        elif doc_closings and not table.printed_closing:
            table.printed_closing = str(doc_closings[-1])     # last printed closing in statement order
        if len(doc_totals) > 1:
            out.warnings.append("anchor_conflict:totals")
        elif doc_totals and not table.printed_totals:
            table.printed_totals = doc_totals[-1]
        if out.summary is not None:                           # the summary block must agree with every printed anchor
            if doc_opening is not None and out.summary.opening is not None and out.summary.opening != doc_opening:
                out.warnings.append("anchor_conflict:opening")
            if doc_closings and out.summary.closing is not None and out.summary.closing != doc_closings[-1]:
                out.warnings.append("anchor_conflict:closing")
    row_opening = None
    balance_only_first = bool(spec.opening_row_balance_only and table.rows and table.rows[0].amounts.get(spec.balance_column)
                              and not table.rows[0].amounts.get(spec.debit_column) and not table.rows[0].amounts.get(spec.credit_column))
    if table.rows and (balance_only_first or (spec.opening_row_marker and re.sub(r"\s+", "", table.rows[0].narration).upper().startswith(spec.opening_row_marker))):
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
        if not table.printed_closing:
            for pt in (page1_text,) if len(pages) == 1 else (page1_text, "".join(squash(ln) for ln in group_lines(pages[-1].words))):
                mc = spec.closing_balance_re.search(pt)
                if mc:
                    table.printed_closing = mc.group(1)
                    break
    if out.summary is None and (spec.opening_balance_re or spec.closing_balance_re or spec.totals_line_re or row_opening is not None):
        # printed opening / closing balance lines are still references to verify the derived values against
        opening = closing = debits = credits = None
        try:
            mo = spec.opening_balance_re.search(page1_text) if spec.opening_balance_re else None
            if mo is None and spec.opening_balance_re and len(pages) > 1:
                page_last_text = "".join(squash(ln) for ln in group_lines(pages[-1].words))
                mo = spec.opening_balance_re.search(page_last_text)
            if mo:
                opening = Decimal(mo.group(1).replace(",", ""))
            elif doc_opening is not None:
                opening = doc_opening
            elif row_opening is not None:
                opening = row_opening
            if table.printed_closing:
                closing = Decimal(table.printed_closing.replace(",", ""))
            if table.printed_totals:
                debits, credits = (Decimal(x.replace(",", "")) for x in table.printed_totals)
        except ArithmeticError:
            opening = closing = debits = credits = None
        if any(v is not None for v in (opening, closing, debits, credits)):
            if spec.anchor_full and not (opening is not None and (closing is not None or debits is not None or credits is not None)):
                pass  # single-ended anchor: far end of the chain stays self-derived -> treat as no summary (REVIEW cap)
            else:
                out.summary = PrintedSummary(opening=opening, closing=closing, debits=debits, credits=credits)
    rows, errors = normalize_rows(table.rows, spec)
    if spec.row_order == "reverse":
        rows.reverse()
    elif spec.row_order == "auto" and len(rows) > 1:
        # printed oldest-first or newest-first depending on the file: reverse only when the balance chain is unbroken
        # newest-first and broken oldest-first (evidence, never a guess)
        fwd = all(_chain_ok(a, b) for a, b in zip(rows, rows[1:]))
        rev = all(_chain_ok(a, b) for a, b in zip(rows[::-1], rows[::-1][1:]))
        if rev and not fwd:
            rows.reverse()
            out.notes.append("row_order:reversed")
    if spec.segment_header_re is not None and len({r.segment for r in rows}) <= 1:
        for r in rows:                      # a single account leaves no segment id: existing consumers see no new field
            r.txn.extras.pop("segment", None)
    out.rows = rows
    out.schema_errors = list(errors)
    if not table.rows and not (out.summary and out.summary.dr_count == 0 and out.summary.cr_count == 0):
        out.failure, out.failure_detail = NO_ROWS, "header found but no transaction rows"
        return out
    out.checks = run_checks(rows, out.period, out.summary, errors, out.warnings, spec.period_date_format, spec.summary_expected,
                          spec.dates_monotonic_expected, spec.period_tolerance_days,
                          spec.side_flip_policy, spec.no_running_balance, spec.chain_reorder_same_date,
                          table.segment_counts or None, table.segment_side_counts or None, _checkpoint_amounts(table))
    return out


def _checkpoint_amounts(table: AssembledTable) -> List[Tuple[int, Decimal, str]]:
    out: List[Tuple[int, Decimal, str]] = []
    for tup in table.checkpoints:
        try:
            out.append((tup[0], Decimal(tup[1].replace(",", "")), tup[2] if len(tup) > 2 else ""))
        except ArithmeticError:
            continue
    return out


def _key(r: NormalizedRow):
    t = r.txn
    return (t.date, t.debit, t.credit, t.balance)


def _chain_ok(prev: NormalizedRow, nxt: NormalizedRow) -> bool:
    t = nxt.txn
    if prev.txn.balance is None or t.balance is None:
        return False
    return prev.txn.balance - (t.debit or Decimal(0)) + (t.credit or Decimal(0)) == t.balance


def _merge(o1: V2Outcome, o2: V2Outcome, spec: LayoutSpec) -> Optional[V2Outcome]:
    """Join the next statement onto o1 when it re-prints the tail of o1 (overlapping export) or continues it exactly; else None."""
    if not o1.rows or not o2.rows or (o1.account_number and o2.account_number and o1.account_number != o2.account_number):
        return None
    a, b = o1.rows, o2.rows
    start = None
    for j in range(len(b)):                                  # overlap: b[:j+1] re-prints the last j+1 rows of a
        if j + 1 <= len(a) and all(_key(b[t]) == _key(a[len(a) - j - 1 + t]) for t in range(j + 1)):
            start = j + 1
            break
    if start is None:
        if _chain_ok(a[-1], b[0]):
            start = 0
        else:
            return None
    merged = V2Outcome(rows=a + b[start:], anchors=o1.anchors, table=o1.table, account_number=o1.account_number or o2.account_number,
                       ifsc=o1.ifsc or o2.ifsc, consumed_pages=o1.consumed_pages + o2.consumed_pages)
    merged.period = (o1.period[0], o2.period[1]) if o1.period and o2.period else (o1.period or o2.period)
    s1, s2 = o1.summary, o2.summary
    merged.summary = PrintedSummary(opening=s1.opening if s1 else None, closing=s2.closing if s2 else None) if (s1 or s2) else None
    merged.warnings = [w for w in o1.warnings if not w.startswith("additional_statement")] + list(o2.warnings)
    merged.schema_errors = o1.schema_errors + o2.schema_errors
    merged.notes = o1.notes + o2.notes + [f"merged_statement:overlap_rows={start if start else 0}"]
    merged.checks = run_checks(merged.rows, merged.period, merged.summary, merged.schema_errors, merged.warnings, spec.period_date_format,
                               spec.summary_expected, spec.dates_monotonic_expected, spec.period_tolerance_days, spec.side_flip_policy, spec.no_running_balance, spec.chain_reorder_same_date)
    return merged


def _add_years(rows, period, spec) -> None:
    """Dates printed without a year: append the year that puts the date inside the printed period. Without a parseable
    period the rows are left as printed, so normalisation reports them rather than guessing."""
    if not period:
        return
    try:
        start, end = (parse_period_date(period[i], spec.period_date_format) for i in (0, 1))
    except ValueError:
        return
    years = list(range(start.year, end.year + 1))
    formats = spec.date_format.split("|")

    def fix(text: str) -> str:
        text = text.strip()
        if not text:
            return text
        for one in formats:                      # a date_tail may have already supplied the year
            try:
                datetime.strptime(text, one)
                return text
            except ValueError:
                continue
        for y in years:
            for one in formats:
                try:
                    d = datetime.strptime(f"{text} {y}", one).date()
                except ValueError:
                    continue
                if start <= d <= end:
                    return f"{text} {y}"
                break           # parsed but outside the period: wrong year, try the next one
        return f"{text} {years[0]}"

    for r in rows:
        r.date = fix(r.date)
        r.value_date = fix(r.value_date)


_TXN_AMOUNT = re.compile(r"\d[\d,]*\.\d{2}")
_CARRY_LINE = re.compile(r"FORWARD|BROUGHT|CARRIED|OPENING|CLOSING|TOTAL|B/F|C/F|BALB/F|BALANCEB/F|BALANCE(?:AS|ON)")


def _amount_key(text: str) -> Optional[Decimal]:
    m = _TXN_AMOUNT.search(text)
    if not m:
        return None
    try:
        return abs(Decimal(m.group(0).replace(",", "")))
    except Exception:
        return None


def _unread_transaction_lines(pages: Sequence[Page], spec: LayoutSpec, rows: Sequence[NormalizedRow]) -> int:
    """Transaction-looking lines BEFORE the first or AFTER the last row that was read (document order).

    A row dropped from the middle of the table breaks the balance chain, which the chain check already fails. Rows
    dropped at the start or the end (a mid-statement summary or footer taken as the end of the table, rows after it on
    the same page) leave the chain intact, and a printed closing that matches the truncated end hides them from the
    reference check too. This guard finds them: lines that start with a date in this layout's shape, carry an amount,
    are not an opening/brought-forward/total line, and whose balance (last amount on the line) is not a balance of any
    row read, lying outside the span of lines that match the rows read. Conservative by construction: a date split over
    several tokens, or a line whose last amount happens to equal some balance, is not counted."""
    bals = {abs(r.txn.balance) for r in rows if r.txn.balance is not None}
    pages = _prepare_pages(pages, spec)
    if not bals and not spec.no_running_balance:
        return 0
    keys: List[Optional[Decimal]] = []
    for pg in pages:
        for ln in group_lines(pg.words):
            if not ln:
                continue
            first = ln[0].text.strip()
            head3 = " ".join(w.text for w in ln[:3]).strip()
            if not (spec.date_re.fullmatch(first) or spec.date_re.fullmatch(head3)):
                continue
            text = "".join(w.text for w in ln).upper()
            if _CARRY_LINE.search(text) or "%" in text:
                continue                        # opening / brought-forward / totals / rate lines are not transactions
            amounts = [k for k in (_amount_key(w.text) for w in ln[1:]) if k is not None]
            if amounts:
                keys.append(amounts[-1])
    if spec.no_running_balance:
        # no balances to map lines onto: every dated amount-bearing line should have produced one row
        return max(len(keys) - len(rows), 0)
    hit = [i for i, k in enumerate(keys) if k in bals]
    if not hit:
        return 0
    lo, hi = min(hit), max(hit)
    return sum(1 for i, k in enumerate(keys) if (i < lo or i > hi) and k not in bals)


def extract_pages(pages: Sequence[Page], spec: LayoutSpec) -> V2Outcome:
    out = _extract_pages_core(pages, spec)
    if out.failure or not out.rows:
        return out
    unread = _unread_transaction_lines(pages, spec, out.rows)
    if unread:
        out.warnings.append(f"unread_transaction_lines:{unread}")
        out.notes.append(f"completeness:unread_transaction_lines={unread}")
        out.checks = run_checks(out.rows, out.period, out.summary, out.schema_errors, out.warnings, spec.period_date_format,
                                spec.summary_expected, spec.dates_monotonic_expected, spec.period_tolerance_days, spec.side_flip_policy,
                                spec.no_running_balance, spec.chain_reorder_same_date,
                                out.table.segment_counts if out.table is not None else None,
                                out.table.segment_side_counts if out.table is not None else None,
                                _checkpoint_amounts(out.table) if out.table is not None else None)
    return out


def _extract_pages_core(pages: Sequence[Page], spec: LayoutSpec) -> V2Outcome:
    out = _extract_one(pages, spec)
    if not spec.merge_statements:
        return out
    for _ in range(8):
        if out.failure or out.table is None or not any(w.startswith("additional_statement") for w in out.warnings):
            break
        rest = list(pages[out.consumed_pages:])
        nxt = _extract_one(rest, spec) if rest else None
        if nxt is None or nxt.failure == NO_ROWS:       # a header with no transaction rows is an empty statement; text without a header stays a REVIEW
            out.warnings = [w for w in out.warnings if not w.startswith("additional_statement")]     # nothing usable follows
            out.notes.append("ignored_empty_following_statement")
            out.checks = run_checks(out.rows, out.period, out.summary, out.schema_errors, out.warnings, spec.period_date_format,
                                    spec.summary_expected, spec.dates_monotonic_expected, spec.period_tolerance_days, spec.side_flip_policy,
                                    spec.no_running_balance, spec.chain_reorder_same_date,
                                    out.table.segment_counts if out.table is not None else None,
                                    out.table.segment_side_counts if out.table is not None else None,
                                    _checkpoint_amounts(out.table) if out.table is not None else None)
            break
        if nxt.failure:
            break
        merged = _merge(out, nxt, spec)
        if merged is None:
            break
        out = merged
    return out
