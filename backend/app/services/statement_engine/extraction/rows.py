"""Row assembly: words -> table rows using column anchors.

A row starts at a date in the date column. Undated lines below it (narration wraps, wrapped references) belong to that
row. The table ends at the printed STATEMENT SUMMARY block. Page furniture (customer block, footer) is excluded by
position relative to the period line / summary marker / left margin, never by fixed page coordinates.
"""
from __future__ import annotations

import re
from decimal import Decimal

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .anchors import ColumnAnchors, classify_word, find_header
from .layout_spec import LayoutSpec
from .words import Word, group_lines, squash


@dataclass
class Page:
    words: List[Word]
    width: Optional[float] = None


@dataclass
class RawRow:
    page: int                       # 1-based
    top: float
    date: str = ""
    narration_lines: List[str] = field(default_factory=list)
    ref: str = ""
    value_date: str = ""
    amounts: Dict[str, str] = field(default_factory=dict)   # money column role -> printed text
    warnings: List[str] = field(default_factory=list)

    @property
    def narration(self) -> str:
        return " ".join(s for s in self.narration_lines if s)


@dataclass
class AssembledTable:
    rows: List[RawRow] = field(default_factory=list)
    period: Optional[Tuple[str, str]] = None                # (from, to) as printed, dd/mm/yyyy
    summary_lines: List[List[Word]] = field(default_factory=list)   # lines from the summary marker onward
    summary_page: Optional[int] = None
    printed_totals: Optional[Tuple[str, str]] = None        # (debits, credits) printed as a totals line inside the table
    printed_closing: Optional[str] = None                   # closing balance printed as a line inside the table
    warnings: List[str] = field(default_factory=list)


_SUMMARY_TAIL_LINES = 14


def _ends(text: str, markers) -> bool:
    """True when the (upper-cased, whitespace-free) line text carries an end marker; a marker starting with "=" must equal the whole line, one starting with "^" must open it."""
    return any((text == m[1:]) if m.startswith("=") else text.startswith(m[1:]) if m.startswith("^") else (m in text) for m in markers)


def _first_dated(lines: List[List[Word]], begin: int, anchors: ColumnAnchors, spec: LayoutSpec) -> int:
    """Index of the first line at or after `begin` that starts a row; lines before it are header continuation."""
    end_markers = tuple(m for m in (spec.summary_marker, *spec.end_markers) if m)
    for i in range(begin, len(lines)):
        if any(classify_word(w, anchors, spec) == "date" for w in lines[i]) or _ends(squash(lines[i]).upper(), end_markers):
            return i
    return len(lines)


def _region_start(lines: List[List[Word]], page_no: int, anchors: ColumnAnchors, spec: LayoutSpec) -> Tuple[int, Optional[Tuple[str, str]], bool]:
    """(index of first table line, period if a From/To line was seen, whether a start marker was found)."""
    period = None
    marker_idx = None
    for i, line in enumerate(lines):
        m = spec.period_re.search(squash(line))
        if m:
            period = (m.group(1), m.group(2))
            marker_idx = i
            break
    if page_no == 1:
        for i, line in enumerate(lines):
            if min(w.top for w in line) > anchors.header_top + 1.0:
                return _first_dated(lines, i, anchors, spec), period, True
        return len(lines), period, True
    if spec.header_repeats:
        found = find_header(lines, spec)
        if found and spec.page_break_re is not None and any(
                any(classify_word(w, anchors, spec) == "date" for w in ln) for ln in lines[:found[0]]):
            return 0, period, True      # rows sit above the header: a printed page break falls inside this PDF page
        if found:
            return _first_dated(lines, found[0] + 1, anchors, spec), period, True
    if marker_idx is not None:
        if spec.page_break_re is not None and any(
                any(classify_word(w, anchors, spec) == "date" for w in ln) for ln in lines[:marker_idx]):
            return 0, period, True      # rows above the period line: the printed page break falls after them
        return marker_idx + 1, period, True
    if spec.continuation_start == "top":
        return 0, period, True
    return 0, period, False


def _has_dated_row(lines: List[List[Word]], anchors: ColumnAnchors, spec: LayoutSpec) -> bool:
    """True when a row-start date appears in the date column: used after the summary block, where it means that the
    file carries another statement (merged PDFs), which a single-statement extraction must not silently drop."""
    return any(classify_word(w, anchors, spec) == "date" for line in lines for w in line)


def assemble(pages: Sequence[Page], anchors: ColumnAnchors, spec: LayoutSpec) -> AssembledTable:
    table = AssembledTable()
    end_markers = tuple(m for m in (spec.summary_marker, *spec.end_markers) if m)
    current: Optional[RawRow] = None
    ended = False
    for pno, page in enumerate(pages, start=1):
        if ended:
            if not spec.dated_rows_after_end_ok and _has_dated_row(group_lines(page.words), anchors, spec) and not any(x.startswith("additional_statement") for x in table.warnings):
                table.warnings.append(f"additional_statement_after_summary:page{pno}")
            # the summary labels can sit at the bottom of one page and the numbers at the top of the next, below the
            # repeated customer block: take the lines after the period line (the table region) of the next page
            if len(table.summary_lines) < _SUMMARY_TAIL_LINES * 2:
                nxt = group_lines(page.words)
                begin, _p, found = _region_start(nxt, pno, anchors, spec)
                table.summary_lines.extend(nxt[begin if found else 0:][:_SUMMARY_TAIL_LINES])
            continue
        if page.width is not None and anchors.page_width is not None and abs(page.width - anchors.page_width) > 1.0:
            table.warnings.append(f"page_width_drift:page{pno}")
        lines = group_lines(page.words)
        start, period, marked = _region_start(lines, pno, anchors, spec)
        if period and table.period is None:
            table.period = period
        if not marked:
            first_dated = next((i for i, ln in enumerate(lines) if any(classify_word(w, anchors, spec) == "date" for w in ln)), None)
            if first_dated is None:
                # a page without rows can still be the footer page that ends the statement
                for li, line in enumerate(lines):
                    if _ends(squash(line).upper(), end_markers):
                        table.summary_page = pno
                        table.summary_lines = lines[li:li + _SUMMARY_TAIL_LINES]
                        ended = True
                        break
                continue
            start = first_dated
            if spec.page_break_re is None:
                table.warnings.append(f"no_period_marker:page{pno}")
        in_break = False
        for li in range(start, len(lines)):
            line = lines[li]
            text = squash(line).upper()
            if spec.page_break_re is not None:
                if in_break:
                    if find_header([line], spec):
                        in_break = False
                    continue
                if spec.page_break_re.search(squash(line)):
                    in_break = True
                    current = None
                    continue
            if spec.page_footer_markers and any(text.startswith(m) for m in spec.page_footer_markers):
                break
            if _ends(text, end_markers):
                table.summary_page = pno
                table.summary_lines = lines[li:li + _SUMMARY_TAIL_LINES]
                ended = True
                if not spec.dated_rows_after_end_ok and _has_dated_row(lines[li + 1:], anchors, spec):
                    table.warnings.append(f"additional_statement_after_summary:page{pno}")
                break
            flat = squash(line)
            if any(rx.search(flat) for rx in spec.ignore_line_res):
                continue
            if spec.closing_balance_re:
                mc = spec.closing_balance_re.search(flat)
                if mc:   # printed closing balance line: a reference value, not a transaction or a narration wrap
                    table.printed_closing = mc.group(1)
                    current = None
                    continue
            if spec.totals_line_re:
                mt = spec.totals_line_re.search(flat)
                if mt:
                    g = mt.groups()
                    pair = (g[1], g[0]) if spec.totals_credit_first else (g[0], g[1])
                    if spec.totals_accumulate and table.printed_totals:
                        pair = tuple(str(Decimal(a.replace(",", "")) + Decimal(b.replace(",", ""))) for a, b in zip(table.printed_totals, pair))
                    table.printed_totals = pair
                    if len(g) >= 3 and g[2]:
                        table.printed_closing = g[2]
                    current = None
                    continue
            if spec.carry_forward_re is not None and table.rows and spec.carry_forward_re.search(flat):
                # restated running balance, not a transaction; its dates seed rows printed without a date below it
                cf = {}
                for w in line:
                    col = classify_word(w, anchors, spec)
                    if col:
                        cf.setdefault(col, []).append(w.text.strip())
                current = RawRow(page=pno, top=min(w.top for w in line), date=(cf.get("date") or [""])[0],
                                 value_date=" ".join(cf.get(spec.secondary_date_column, [])) if spec.secondary_date_column else "")
                continue
            cols: Dict[str, List[str]] = {}
            for w in line:
                col = classify_word(w, anchors, spec)
                if col:
                    cols.setdefault(col, []).append(w.text.strip())
            if not cols:
                continue
            inherit = (spec.undated_rows_inherit_date and "date" not in cols and current is not None and spec.balance_column in cols
                       and any(c in cols for c in (spec.debit_column, spec.credit_column)))
            if "date" in cols or inherit:
                prev = current
                current = RawRow(page=pno, top=min(w.top for w in line), date=cols["date"][0] if "date" in cols else prev.date)
                table.rows.append(current)
                current.narration_lines.append(" ".join(cols.get("narration", [])))
                current.ref = "".join(cols.get("ref", []))
                if spec.secondary_date_column:
                    current.value_date = " ".join(cols.get(spec.secondary_date_column, [])) or (prev.value_date if inherit else "")
                for name in spec.amount_columns:
                    vals = [v for v in cols.get(name, []) if not (spec.empty_amount_marker and v == spec.empty_amount_marker)]
                    if vals:
                        current.amounts[name] = vals[0]
                        if len(vals) > 1:
                            current.warnings.append(f"multiple_values:{name}")
                if spec.side_marker_column and cols.get(spec.side_marker_column):
                    marker = next((v for v in cols[spec.side_marker_column] if re.match(r"(?i)^\(?(cr|dr)\)?\.?$", v)), "")
                    if marker and spec.single_amount_column in current.amounts:
                        current.amounts[spec.single_amount_column] = current.amounts[spec.single_amount_column] + " " + marker
            elif current is not None:
                if "date_tail" in cols:
                    current.date = f"{current.date} {' '.join(cols['date_tail'])}"
                tail = (spec.secondary_date_column or "") + "_tail"
                if tail in cols:
                    current.value_date = f"{current.value_date} {' '.join(cols[tail])}".strip()
                filled = False
                if spec.continuation_amounts:
                    for name in spec.amount_columns:
                        if cols.get(name) and not current.amounts.get(name):
                            current.amounts[name] = cols[name][0]
                            filled = True
                if any(c in cols for c in spec.amount_columns) and not filled:
                    current.warnings.append("orphan_amount_on_wrapped_line")
                if "narration" in cols:
                    current.narration_lines.append(" ".join(cols["narration"]))
                if "ref" in cols:
                    current.ref += "".join(cols["ref"])
    return table
