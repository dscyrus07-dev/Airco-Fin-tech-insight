"""HTML table -> grid of cell strings (stdlib html.parser only; no new dependency).

colspan/rowspan are expanded so every row has one string per column position. A spanned cell's text is placed
in its first position only; the other covered positions are empty strings, so a value is never duplicated
(duplicating an amount would invent money).
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import List, Optional

_WS = re.compile(r"\s+")


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: List[List[List[tuple]]] = []   # table -> rows -> (text, colspan, rowspan, is_header)
        self._depth = 0
        self._row: Optional[list] = None
        self._cell: Optional[list] = None
        self._span = (1, 1, False)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self._depth += 1
            if self._depth == 1:
                self.tables.append([])
        elif self._depth != 1:
            return
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            if self._row is None:
                self._row = []
            self._cell = []
            self._span = (_int(a.get("colspan")), _int(a.get("rowspan")), tag == "th")
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag == "table":
            if self._depth == 1:
                self._close_row()
            self._depth = max(0, self._depth - 1)
        elif self._depth != 1:
            return
        elif tag in ("td", "th"):
            self._close_cell()
        elif tag == "tr":
            self._close_row()

    def handle_data(self, data):
        if self._depth == 1 and self._cell is not None:
            self._cell.append(data)

    def _close_cell(self):
        if self._cell is not None and self._row is not None:
            text = _WS.sub(" ", html.unescape("".join(self._cell))).strip()
            c, r, th = self._span
            self._row.append((text, c, r, th))
        self._cell = None

    def _close_row(self):
        self._close_cell()
        if self._row is not None and self.tables:
            if self._row:
                self.tables[-1].append(self._row)
        self._row = None


def _int(v) -> int:
    try:
        n = int(str(v).strip())
        return n if 1 <= n <= 50 else 1
    except (TypeError, ValueError):
        return 1


def parse_tables(markup: str) -> List[List[List[str]]]:
    """Every top-level <table> in `markup` as a rectangular grid of strings."""
    p = _TableParser()
    try:
        p.feed(markup or "")
        p.close()
    except Exception:
        return []
    out = []
    for raw_rows in p.tables:
        grid: List[List[Optional[str]]] = []
        pending = {}   # (row, col) -> True for positions covered by a rowspan from above
        for ri, raw in enumerate(raw_rows):
            row: List[Optional[str]] = []
            col = 0
            for text, cspan, rspan, _th in raw:
                while pending.pop((ri, col), False):
                    row.append("")
                    col += 1
                row.append(text)
                for k in range(1, cspan):
                    row.append("")
                for dr in range(1, rspan):
                    for dc in range(cspan):
                        pending[(ri + dr, col + dc)] = True
                col += cspan
            while pending.pop((ri, col), False):
                row.append("")
                col += 1
            grid.append(row)
        width = max((len(r) for r in grid), default=0)
        out.append([[c or "" for c in r] + [""] * (width - len(r)) for r in grid])
    return out
