"""OCR page -> engine Page (the text-layer contract `Word(text, x0, x1, top, bottom)`).

PaddleOCR-VL returns a table as HTML (rows x cells, no cell coordinates) and other regions as text blocks with
a bounding box. The engine only needs coordinates to decide which column a word belongs to, so each table cell
is laid out in a fixed synthetic column band:

    column c  ->  x in [MARGIN + c*COL_W, MARGIN + (c+1)*COL_W - GAP]
    row r     ->  top = y_cursor + r*ROW_PITCH

Amount-like single-token cells are right-aligned to the band edge (the universal inference clusters numeric
right edges into columns); other cells are laid out left to right and compressed to fit the band, so a long
narration can never spill into the next column. Text blocks (headers, summaries, period lines) become ordinary
lines placed above/below the table in reading order. The result feeds universal.reader.read(pages=...) and
every existing check, unchanged.

Text is never altered here beyond whitespace normalisation: no digit "correction", no guessing.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Optional, Sequence

from ..extraction.rows import Page
from ..extraction.words import Word
from .contracts import OcrPage
from .html_table import parse_tables, parse_tables_shaped

MARGIN = 20.0
COL_W = 150.0
GAP = 8.0
ROW_PITCH = 20.0
LINE_H = 9.0
CHAR_W = 4.6
BLOCK_GAP = 14.0
TEXT_LINE_MAX_W = 900.0

_AMOUNT = re.compile(r"^[-(]?(?:₹|rs\.?|inr)?\s*[\d,]+(?:\.\d{1,2})?\)?(?:\s*(?:cr|dr))?\.?$", re.I)
_WS = re.compile(r"\s+")
_TAG = re.compile(r"<[^>]+>")


def _is_amount(text: str) -> bool:
    t = text.strip()
    return bool(t) and any(ch.isdigit() for ch in t) and bool(_AMOUNT.match(t))


def _cell_words(text: str, x0: float, x1: float, top: float) -> List[Word]:
    toks = [t for t in _WS.split(text.strip()) if t]
    if not toks:
        return []
    bottom = top + LINE_H
    if len(toks) == 1 and _is_amount(toks[0]):
        w = min(len(toks[0]) * CHAR_W, x1 - x0)
        return [Word(toks[0], x1 - w, x1, top, bottom)]
    natural = sum(len(t) * CHAR_W for t in toks) + CHAR_W * (len(toks) - 1)
    scale = min(1.0, (x1 - x0) / natural) if natural > 0 else 1.0
    out, x = [], x0
    for t in toks:
        w = len(t) * CHAR_W * scale
        out.append(Word(t, x, x + w, top, bottom))
        x += w + CHAR_W * scale
    return out


def _text_lines(content: str) -> List[str]:
    plain = _TAG.sub(" ", content or "")
    return [ln.strip() for ln in plain.splitlines() if ln.strip()]


def _line_words(text: str, top: float) -> List[Word]:
    return _cell_words(text, MARGIN, MARGIN + TEXT_LINE_MAX_W, top)


def table_words(grid: Sequence[Sequence[str]], top: float) -> List[Word]:
    words: List[Word] = []
    for r, row in enumerate(grid):
        y = top + r * ROW_PITCH
        for c, cell in enumerate(row):
            x0 = MARGIN + c * COL_W
            words.extend(_cell_words(cell, x0, x0 + COL_W - GAP, y))
    return words


def _well_shaped(grid: Sequence[Sequence[str]], counts: Sequence[int]):
    """Rows whose real cell count matches the table's prevailing one, plus how many were dropped.

    A row the recogniser emitted short cannot be placed: its cells sit one column left of where they belong, so
    an amount would land under the wrong heading. There is no way to tell WHICH cell was dropped (the HTML
    carries no coordinates), and guessing would move money between debit and credit. Such rows are left out and
    counted; the caller reports the count, and the balance chain then fails rather than passing on shifted
    values. Tables too small for a prevailing shape are kept as they are."""
    if len(grid) < 3:
        return list(grid), 0
    # A table's first row is its header and its titles are never empty, so when that row is the widest it
    # states the true column count; otherwise fall back to the prevailing one. Taking the majority alone
    # would discard the header whenever the recogniser shortens every data row.
    expected = counts[0] if counts[0] == max(counts) else Counter(counts).most_common(1)[0][0]
    keep = [row for row, n in zip(grid, counts) if n == expected]
    return keep, len(grid) - len(keep)


def page_from_ocr(op: OcrPage, stats: Optional[Dict[str, int]] = None) -> Page:
    """One engine Page from one OCR page, blocks in the order the layout model returned (its reading order).

    `stats`, when given, collects "rows_dropped": rows the recogniser emitted mis-shaped (see _well_shaped)."""
    words: List[Word] = []
    y = MARGIN
    max_cols = 0
    for b in op.blocks:
        if b.is_table:
            for grid, counts in parse_tables_shaped(b.content):
                if not grid:
                    continue
                grid, dropped = _well_shaped(grid, counts)
                if dropped and stats is not None:
                    stats["rows_dropped"] = stats.get("rows_dropped", 0) + dropped
                if not grid:
                    continue
                max_cols = max(max_cols, max(len(r) for r in grid))
                words.extend(table_words(grid, y))
                y += len(grid) * ROW_PITCH + BLOCK_GAP
        else:
            for ln in _text_lines(b.content):
                words.extend(_line_words(ln, y))
                y += ROW_PITCH
            y += BLOCK_GAP - ROW_PITCH / 2
    width = max(MARGIN * 2 + max_cols * COL_W, MARGIN * 2 + TEXT_LINE_MAX_W)
    return Page(words=words, width=width)


def pages_from_ocr(pages: Sequence[OcrPage], dropped: Optional[Dict[int, int]] = None) -> List[Page]:
    """Engine pages for the OCR pages that succeeded, in page order. Failed pages are NOT represented here;
    the caller reports them (a failed page is never silently treated as empty).

    `dropped`, when given, is filled with source page number -> mis-shaped rows left out on that page."""
    out: List[Page] = []
    for p in sorted(pages, key=lambda p: p.page):
        if not p.ok:
            continue
        stats: Dict[str, int] = {}
        out.append(page_from_ocr(p, stats))
        if dropped is not None and stats.get("rows_dropped"):
            dropped[p.page] = stats["rows_dropped"]
    return out


def page_text(op: OcrPage) -> str:
    """Plain text of an OCR page (for the bank detector)."""
    parts: List[str] = []
    for b in op.blocks:
        if b.is_table:
            for grid in parse_tables(b.content):
                parts.extend(" ".join(c for c in row if c) for row in grid)
        else:
            parts.extend(_text_lines(b.content))
    return "\n".join(parts)
