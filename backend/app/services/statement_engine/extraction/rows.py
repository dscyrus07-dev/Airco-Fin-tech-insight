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
    pending_side: str = ""                                   # side marker seen before its amount (type-on-dated-line)
    warnings: List[str] = field(default_factory=list)
    segment: int = 0                # account segment index (0 when the document prints no segment headers)

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
    segment_counts: Dict[int, int] = field(default_factory=dict)   # segment index -> printed transaction count (total)
    segment_side_counts: Dict[int, Tuple[int, int]] = field(default_factory=dict)  # seg -> (printed debits, credits)
    checkpoints: List[Tuple[int, str, str]] = field(default_factory=list)  # (rows seen so far, printed balance, 'pre'|'post'|'')
    warnings: List[str] = field(default_factory=list)


_SUMMARY_TAIL_LINES = 14


def _ends(text: str, markers) -> bool:
    """True when the (upper-cased, whitespace-free) line text carries an end marker; a marker starting with "=" must equal the whole line, one starting with "^" must open it."""
    return any((text == m[1:]) if m.startswith("=") else text.startswith(m[1:]) if m.startswith("^") else (m in text) for m in markers)


def _line_cols(line: Sequence[Word], anchors: ColumnAnchors, spec: LayoutSpec) -> Dict[str, List[str]]:
    cols: Dict[str, List[str]] = {}
    for w in line:
        c = classify_word(w, anchors, spec)
        if c:
            cols.setdefault(c, []).append(w.text.strip())
    return cols


def _is_section_date(line: Sequence[Word], anchors: ColumnAnchors, spec: LayoutSpec) -> bool:
    """A bare section-date line: its whole text is the section-date shape and every word sits inside the date
    column zone (x0 left of the date/narration boundary). A narration fragment that happens to look like a date
    fails the zone test."""
    return (spec.section_date_re is not None and line
            and spec.section_date_re.fullmatch(squash(line)) is not None
            and all(w.x0 < anchors.date_right for w in line))


def _grouped_row_start(cols: Dict[str, List[str]], spec: LayoutSpec) -> bool:
    """A section-dated statement's row trigger: an undated line carrying at least one full amount cell. Decimal
    fragments of a wrapped amount (" .00") never qualify."""
    return (spec.section_date_re is not None and "date" not in cols
            and any(spec.amount_re.match(v) for cn in spec.amount_columns for v in cols.get(cn, ())))


def _first_dated(lines: List[List[Word]], begin: int, anchors: ColumnAnchors, spec: LayoutSpec) -> int:
    """Index of the first line at or after `begin` that starts a row; lines before it are header continuation."""
    end_markers = tuple(m for m in (spec.summary_marker, *spec.end_markers) if m)
    for i in range(begin, len(lines)):
        if any(classify_word(w, anchors, spec) == "date" for w in lines[i]) or _ends(squash(lines[i]).upper(), end_markers):
            return i
        if spec.section_date_re is not None:
            if _is_section_date(lines[i], anchors, spec) \
                    or _grouped_row_start(_line_cols(lines[i], anchors, spec), spec):
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
    for line in lines:
        if spec.period_re and spec.period_re.search(squash(line)):
            continue   # a repeated period header is not a row
        if any(classify_word(w, anchors, spec) == "date" for w in line):
            return True
    return False


def assemble(pages: Sequence[Page], anchors: ColumnAnchors, spec: LayoutSpec) -> AssembledTable:
    table = AssembledTable()
    end_markers = tuple(m for m in (spec.summary_marker, *spec.end_markers) if m)
    current: Optional[RawRow] = None
    ended = False
    seg_idx = 0
    pending_section: Optional[str] = None        # grouped layouts: the date every following row inherits
    pre_section = 0                              # rows seen before any section date (a document defect)
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
            first_dated = next((i for i, ln in enumerate(lines)
                                if any(classify_word(w, anchors, spec) == "date" for w in ln)
                                or _is_section_date(ln, anchors, spec)
                                or _grouped_row_start(_line_cols(ln, anchors, spec), spec)), None)
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
            if spec.page_break_re is None and not spec.implicit_header:
                table.warnings.append(f"no_period_marker:page{pno}")
        if spec.implicit_header or spec.leading_narration or spec.leading_amounts:
            # the row's first printed line is a narration-band txn-type line ABOVE its dated line: pull it into the scan
            allowed = {"narration"} | (set(spec.amount_columns) | {"ref", spec.side_marker_column or "ref"} if spec.leading_amounts else set())
            climb = 3 if spec.leading_amounts else len(lines)
            while start > 0 and climb:
                prev_cols = {classify_word(w, anchors, spec) for w in lines[start - 1]} - {None}
                if prev_cols and prev_cols <= allowed:
                    start -= 1
                    climb -= 1
                else:
                    break
        pending_prefix: List[str] = []
        pending_cells: List[Dict[str, List[str]]] = []
        in_break = False
        if spec.segment_header_re is not None and marked:
            # an account block sits ABOVE the repeated column header, outside the scanned region: still register the
            # new segment and its printed opening/count lines so segmentation stays correct
            for pre in lines[:start]:
                pf = squash(pre)
                if spec.segment_header_re.search(pf):
                    seg_idx += 1
                    current = None
                elif spec.opening_balance_re is not None and spec.opening_balance_re.search(pf):
                    mo2 = spec.opening_balance_re.search(pf)
                    table.checkpoints.append((len(table.rows), mo2.group(1), "pre"))
                elif spec.closing_balance_re is not None and spec.closing_balance_re.search(pf):
                    mc2 = spec.closing_balance_re.search(pf)
                    table.printed_closing = mc2.group(1)
                    table.checkpoints.append((len(table.rows), mc2.group(1), "post"))
        for li in range(start, len(lines)):
            line = lines[li]
            text = squash(line).upper()
            flat = squash(line)
            if spec.page_break_re is not None:
                if in_break:
                    if spec.segment_count_re and spec.segment_count_re.search(flat):  # a count may print inside the break (B. Summary block)
                        ints = [w.text.strip().replace(",", "") for w in line if re.fullmatch(r"\d[\d,]*", w.text.strip())]
                        if ints:
                            table.segment_counts[seg_idx] = int(ints[-1]) if len(ints) == 1 else int(ints[-1]) + int(ints[-2])
                            if len(ints) >= 2:
                                table.segment_side_counts[seg_idx] = (int(ints[-2]), int(ints[-1]))
                    if find_header([line], spec):
                        in_break = False
                    continue
                if spec.page_break_re.search(flat):
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
            if any(rx.search(flat) for rx in spec.ignore_line_res):
                continue
            if _is_section_date(line, anchors, spec):
                pending_section = " ".join(w.text.strip() for w in line)
                current = None                  # the next row starts a new section; it cannot be a wrap
                continue
            if spec.segment_header_re and spec.segment_header_re.search(flat):
                seg_idx += 1
                current = None
                continue
            if spec.segment_header_re is not None and spec.header_lines <= 1 and find_header([line], spec):
                current = None                        # a segment's repeated column-header line is not a row
                continue
            if spec.balance_checkpoint_re:
                mb = spec.balance_checkpoint_re.search(flat)
                if mb:
                    table.checkpoints.append((len(table.rows), mb.group(1), ""))
                    current = None
                    continue
            if spec.segment_header_re is not None and spec.opening_balance_re is not None:
                mo = spec.opening_balance_re.search(flat)
                if mo:   # a segment's printed opening: asserts the NEXT row's implied starting balance
                    table.checkpoints.append((len(table.rows), mo.group(1), "pre"))
                    current = None
                    continue
            if spec.segment_count_re and spec.segment_count_re.search(flat):
                ints = [w.text.strip().replace(",", "") for w in line if re.fullmatch(r"\d[\d,]*", w.text.strip())]
                if ints:
                    table.segment_counts[seg_idx] = int(ints[-1]) if len(ints) == 1 else int(ints[-1]) + int(ints[-2])
                    if len(ints) >= 2:
                        table.segment_side_counts[seg_idx] = (int(ints[-2]), int(ints[-1]))
                current = None
                continue
            if spec.balance_inline_re and current is not None:
                mib = spec.balance_inline_re.search(flat)
                if mib:
                    current.amounts[spec.balance_column] = mib.group(1)
                    continue
            if spec.closing_balance_re:
                mc = spec.closing_balance_re.search(flat)
                if mc:   # printed closing balance line: a reference value, not a transaction or a narration wrap
                    table.printed_closing = mc.group(1)
                    if spec.segment_header_re is not None:      # a segment's printed closing: asserts the
                        table.checkpoints.append((len(table.rows), mc.group(1), "post"))   # chain's exit balance
                    current = None
                    continue
            if spec.totals_line_re:
                mt = spec.totals_line_re.search(flat)
                if mt:
                    g = mt.groups()
                    if spec.totals_sum_tail and len(g) > 2:
                        rest = sum((Decimal(x.replace(",", "")) for x in g[1:]), Decimal(0))
                        pair = (str(rest), g[0]) if spec.totals_credit_first else (g[0], str(rest))
                    else:
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
            line_inline_bal = None
            cols: Dict[str, List[str]] = {}
            for w in line:
                if spec.balance_inline_re is not None and line_inline_bal is None:
                    mib = spec.balance_inline_re.fullmatch(w.text.strip())
                    if mib:                      # a "Balance : X" word glued onto a dated line is that row's balance
                        line_inline_bal = mib.group(1)
                        continue
                col = classify_word(w, anchors, spec)
                if col:
                    cols.setdefault(col, []).append(w.text.strip())
            if not cols:
                continue
            if spec.leading_amounts and "date" not in cols:
                # fp-A prints a record's amount (and a narration line) ABOVE its dated line: buffer every non-dated
                # line that sits in the run ending at the next dated line. Marker lines (closing/totals/checkpoint/
                # inline balance) are consumed earlier and never reach this branch.
                if spec.single_amount_column and not any(c in cols for c in spec.amount_columns):
                    # the amount word is sometimes glued to a dash ("- 10,000.00 Dr") and lands in a text column:
                    # recover the trailing amount+side token from the raw line text
                    ms = re.search(r"(?i)(-?[\d,]+\.\d{2}\s*(?:cr|dr)\.?)\s*$", flat)
                    if ms:
                        cols[spec.single_amount_column] = [ms.group(1)]
                j = li + 1
                while j < len(lines) and not any(classify_word(w, anchors, spec) == "date" for w in lines[j]):
                    if _ends(squash(lines[j]).upper(), end_markers):
                        break
                    j += 1
                if j < len(lines):
                    pending_cells.append(cols)
                    continue
            if (spec.implicit_header or spec.leading_narration) and set(cols) == {"narration"} and li + 1 < len(lines) \
                    and any(classify_word(w, anchors, spec) == "date" for w in lines[li + 1]):
                pending_prefix.append(" ".join(cols["narration"]))
                continue
            inherit = (spec.undated_rows_inherit_date and "date" not in cols and current is not None and spec.balance_column in cols
                       and any(c in cols for c in (spec.debit_column, spec.credit_column)))
            grouped = _grouped_row_start(cols, spec)
            if "date" in cols or inherit or grouped:
                if grouped and pending_section is None:
                    pre_section += 1        # a row before any section date: a defect, not a transaction
                    current = None
                    continue
                prev = current
                date_words = pending_section if grouped and "date" not in cols else \
                    (" ".join(cols["date"]) if getattr(spec, "date_join_words", False) and "date" in cols
                     else (cols["date"][0] if "date" in cols else prev.date))
                current = RawRow(page=pno, top=min(w.top for w in line), date=date_words, segment=seg_idx)
                table.rows.append(current)
                for pc in pending_cells:           # leading lines' cells belong to this row (amount above the date)
                    mk = next((v for vs in pc.values() for v in vs if re.match(r"(?i)^\(?(cr|dr)\)?\.?$", v)), "")
                    for cn, vals in pc.items():
                        if cn == "narration":
                            rest = [v for v in vals if v != mk]
                            if rest:
                                pending_prefix.append(" ".join(rest))
                        elif cn in spec.amount_columns and vals and cn not in current.amounts:
                            current.amounts[cn] = vals[0] + (" " + mk if mk and spec.single_amount_column == cn else "")
                        elif cn == "ref" and vals:
                            current.ref += "".join(vals)
                        elif spec.side_marker_column and cn == spec.side_marker_column:
                            mk = next((v for v in vals if re.match(r"(?i)^\(?(cr|dr)\)?\.?$", v)), "")
                            if mk and spec.single_amount_column in current.amounts:
                                current.amounts[spec.single_amount_column] += " " + mk
                pending_cells = []
                if line_inline_bal is not None:
                    current.amounts[spec.balance_column] = line_inline_bal
                if pending_prefix:
                    current.narration_lines.extend(pending_prefix)
                    pending_prefix = []
                current.narration_lines.append(" ".join(cols.get("narration", [])))
                current.ref = "".join(cols.get("ref", []))
                if spec.secondary_date_column:
                    current.value_date = " ".join(cols.get(spec.secondary_date_column, [])) or (prev.value_date if inherit else "")
                for name in spec.amount_columns:
                    vals = [v for v in cols.get(name, []) if v.strip()
                            and not (spec.empty_amount_marker and v == spec.empty_amount_marker)]
                    if vals:
                        cell = vals[0]
                        merged = True
                        for v in vals[1:]:
                            # same-line wrapped decimals: "361" + ".63" is one amount, not two cells
                            if spec.wrapped_amount_tokens and re.match(r"^\.\d{1,2}$", v) and "." not in cell \
                                    and spec.amount_re.match(cell + v):
                                cell += v
                            else:
                                merged = False
                        current.amounts[name] = cell
                        if not merged:
                            current.warnings.append(f"multiple_values:{name}")
                if spec.side_marker_column and cols.get(spec.side_marker_column):
                    marker = next((v for v in cols[spec.side_marker_column] if re.match(r"(?i)^\(?(cr|dr)\)?\.?$", v)), "")
                    if marker and spec.single_amount_column in current.amounts:
                        current.amounts[spec.single_amount_column] = current.amounts[spec.single_amount_column] + " " + marker
                    elif marker:
                        current.pending_side = marker     # the amount arrives on a later line (continuation_amounts)
            elif current is not None:
                if line_inline_bal is not None:
                    current.amounts[spec.balance_column] = line_inline_bal
                if "date_tail" in cols:
                    current.date = f"{current.date} {' '.join(cols['date_tail'])}"
                tail = (spec.secondary_date_column or "") + "_tail"
                if tail in cols:
                    current.value_date = f"{current.value_date} {' '.join(cols[tail])}".strip()
                filled = False
                if spec.wrapped_amount_tokens:
                    for name in spec.amount_columns:
                        for v in cols.get(name, []):
                            prev_v = current.amounts.get(name)
                            if not prev_v or not spec.amount_re.match(prev_v + v):
                                continue
                            # a lone ".dd" cell can only be a wrapped decimal tail: join it even when the
                            # integer part alone already parses as an amount ("1,111" + ".40" = "1,111.40")
                            if not spec.amount_re.match(prev_v) \
                                    or (re.match(r"^\.\d{1,2}$", v) and "." not in prev_v):
                                current.amounts[name] = prev_v + v
                                filled = True
                if spec.continuation_amounts:
                    for name in spec.amount_columns:
                        if cols.get(name) and not current.amounts.get(name):
                            current.amounts[name] = cols[name][0]
                            if name == spec.single_amount_column and current.pending_side:
                                current.amounts[name] += " " + current.pending_side
                                current.pending_side = ""
                            filled = True
                if spec.side_marker_column and cols.get(spec.side_marker_column) and spec.single_amount_column in current.amounts:
                    marker = next((v for v in cols[spec.side_marker_column] if re.match(r"(?i)^\(?(cr|dr)\)?\.?$", v)), "")
                    cell = current.amounts[spec.single_amount_column]
                    if marker and not re.search(r"(?i)\(?(cr|dr)\)?\.?$", cell):
                        current.amounts[spec.single_amount_column] = cell + " " + marker
                if any(c in cols for c in spec.amount_columns) and not filled:
                    current.warnings.append("orphan_amount_on_wrapped_line")
                if "narration" in cols:
                    current.narration_lines.append(" ".join(cols["narration"]))
                if "ref" in cols:
                    current.ref += "".join(cols["ref"])
    if pre_section:
        table.warnings.append(f"rows_without_section_date:{pre_section}")
    if spec.segment_header_re is not None and any(r.segment for r in table.rows):
        # account blocks above the header bump seg_idx before any row exists: renumber the used ids densely
        # (0..k) so consumers see stable per-segment indices; segment count maps follow the same remap
        remap: Dict[int, int] = {}
        for r in table.rows:
            if r.segment not in remap:
                remap[r.segment] = len(remap)
            r.segment = remap[r.segment]
        table.segment_counts = {remap.get(k, k): v for k, v in table.segment_counts.items()}
        table.segment_side_counts = {remap.get(k, k): v for k, v in table.segment_side_counts.items()}
    return table
