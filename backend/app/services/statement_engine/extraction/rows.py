"""Row assembly: words -> table rows using column anchors.

A row starts at a date in the date column. Undated lines below it (narration wraps, wrapped references) belong to that
row. The table ends at the printed STATEMENT SUMMARY block. Page furniture (customer block, footer) is excluded by
position relative to the period line / summary marker / left margin, never by fixed page coordinates.
"""
from __future__ import annotations

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
    warnings: List[str] = field(default_factory=list)


_SUMMARY_TAIL_LINES = 14


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
                return i, period, True
        return len(lines), period, True
    if spec.header_repeats:
        found = find_header(lines, spec)
        if found:
            return found[0] + 1, period, True
    if marker_idx is not None:
        return marker_idx + 1, period, True
    return 0, period, False


def _has_dated_row(lines: List[List[Word]], anchors: ColumnAnchors, spec: LayoutSpec) -> bool:
    """True when a row-start date appears in the date column: used after the summary block, where it means that the
    file carries another statement (merged PDFs), which a single-statement extraction must not silently drop."""
    return any(classify_word(w, anchors, spec) == "date" for line in lines for w in line)


def assemble(pages: Sequence[Page], anchors: ColumnAnchors, spec: LayoutSpec) -> AssembledTable:
    table = AssembledTable()
    current: Optional[RawRow] = None
    ended = False
    for pno, page in enumerate(pages, start=1):
        if ended:
            if _has_dated_row(group_lines(page.words), anchors, spec) and not any(x.startswith("additional_statement") for x in table.warnings):
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
                continue
            start = first_dated
            table.warnings.append(f"no_period_marker:page{pno}")
        for li in range(start, len(lines)):
            line = lines[li]
            text = squash(line).upper()
            if spec.summary_marker in text:
                table.summary_page = pno
                table.summary_lines = lines[li:li + _SUMMARY_TAIL_LINES]
                ended = True
                if _has_dated_row(lines[li + 1:], anchors, spec):
                    table.warnings.append(f"additional_statement_after_summary:page{pno}")
                break
            cols: Dict[str, List[str]] = {}
            for w in line:
                col = classify_word(w, anchors, spec)
                if col:
                    cols.setdefault(col, []).append(w.text.strip())
            if not cols:
                continue
            if "date" in cols:
                current = RawRow(page=pno, top=min(w.top for w in line), date=cols["date"][0])
                table.rows.append(current)
                current.narration_lines.append(" ".join(cols.get("narration", [])))
                current.ref = "".join(cols.get("ref", []))
                current.value_date = " ".join(cols.get(spec.secondary_date_column, [])) if spec.secondary_date_column else ""
                for name in spec.amount_columns:
                    vals = cols.get(name, [])
                    if vals:
                        current.amounts[name] = vals[0]
                        if len(vals) > 1:
                            current.warnings.append(f"multiple_values:{name}")
            elif current is not None:
                if any(c in cols for c in spec.amount_columns):
                    current.warnings.append("orphan_amount_on_wrapped_line")
                if "narration" in cols:
                    current.narration_lines.append(" ".join(cols["narration"]))
                if "ref" in cols:
                    current.ref += "".join(cols["ref"])
    return table
