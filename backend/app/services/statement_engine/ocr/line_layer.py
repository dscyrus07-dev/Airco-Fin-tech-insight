"""Engine Pages built from the recogniser's own text boxes (PP-OCR lines), not from table markup.

Why this exists
---------------
The VL model returns a table as HTML with no coordinates, so ocr/grid.py has to invent them: cell number n is
placed in column band n. The first real-GPU evaluation (docs/ocr/R8_DEVIN_REPORT.md) showed that model
merging two adjacent money titles into a single cell on every split-layout statement, which makes the band
numbering wrong for the whole table — not occasionally, but systematically. Markup that misstates the column
structure cannot be repaired downstream, because the boundary it lost is not in the markup at all.

The line recogniser reports a box per text line, so the boundary IS present: it is the gap between boxes. That
is also the shape the extraction engine was built for (it infers columns by clustering the right edges of
numeric tokens), so the engine runs unchanged on these pages.

What is measured and what is estimated
--------------------------------------
A box holding one token gives that token's true edges. A box holding several tokens gives only the run's outer
edges, so the tokens inside are spread across it in proportion to their length; the outermost edges stay true.
When such a box holds more than one amount it straddles a column boundary, and the split between those amounts
is an estimate — counted as `fused_amounts` so the caller can report it, never silently trusted.

No text is altered here: no digit is corrected and no value is invented.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

from ..extraction.rows import Page
from ..extraction.words import Word
from .contracts import OcrLine, OcrPage

CHAR_W = 4.6                      # only used to share a multi-token box out; outer edges come from the box
MIN_BOX_W = 1.0

_WS = re.compile(r"\s+")
_AMOUNT = re.compile(r"^[-(]?(?:₹|rs\.?|inr)?\s*\d[\d,]*(?:\.\d{1,2})?\)?(?:\s*(?:cr|dr))?\.?$", re.I)


def _is_amount(token: str) -> bool:
    t = token.strip()
    return bool(t) and any(ch.isdigit() for ch in t) and bool(_AMOUNT.match(t))


def _usable(line: OcrLine) -> bool:
    box = list(line.box or [])
    return (len(box) >= 4 and bool((line.text or "").strip())
            and box[2] - box[0] >= MIN_BOX_W and box[3] - box[1] >= 0.0)


def line_words(line: OcrLine) -> List[Word]:
    """Words of one recognised line, placed inside its own box."""
    x0, top, x1, bottom = (float(v) for v in list(line.box)[:4])
    if bottom < top:
        top, bottom = bottom, top
    toks = [t for t in _WS.split((line.text or "").strip()) if t]
    if not toks:
        return []
    if len(toks) == 1:
        return [Word(toks[0], x0, x1, top, bottom)]
    natural = sum(len(t) for t in toks) + (len(toks) - 1)
    scale = (x1 - x0) / natural if natural > 0 else CHAR_W
    out: List[Word] = []
    x = x0
    for i, t in enumerate(toks):
        w = len(t) * scale
        # the run's outer edges are measured, so pin them rather than letting rounding move them
        a = x0 if i == 0 else x
        b = x1 if i == len(toks) - 1 else x + w
        out.append(Word(t, a, b, top, bottom))
        x += w + scale
    return out


def fused_amounts(lines: Sequence[OcrLine]) -> int:
    """Boxes holding more than one amount: these straddle a column boundary, so their split is an estimate."""
    n = 0
    for ln in lines:
        if not _usable(ln):
            continue
        if sum(1 for t in _WS.split((ln.text or "").strip()) if _is_amount(t)) > 1:
            n += 1
    return n


def page_from_lines(op: OcrPage, stats: Optional[Dict[str, int]] = None) -> Optional[Page]:
    """One engine Page from one OCR page's text boxes, or None when the page carries no usable box.

    `stats`, when given, collects "fused_amounts" and "unusable_lines"."""
    usable = [ln for ln in (op.lines or []) if _usable(ln)]
    if stats is not None:
        if len(op.lines or []) - len(usable):
            stats["unusable_lines"] = stats.get("unusable_lines", 0) + len(op.lines or []) - len(usable)
        if fused_amounts(usable):
            stats["fused_amounts"] = stats.get("fused_amounts", 0) + fused_amounts(usable)
    if not usable:
        return None
    words: List[Word] = []
    for ln in usable:
        words.extend(line_words(ln))
    if not words:
        return None
    width = float(op.width) if op.width else max(w.x1 for w in words)
    return Page(words=words, width=width)


def pages_from_lines(pages: Sequence[OcrPage],
                     stats: Optional[Dict[int, Dict[str, int]]] = None) -> List[Page]:
    """Engine pages for the OCR pages that succeeded AND carry text boxes, in page order.

    A page with no box is left out exactly as a failed page is: the caller reports it, so a page is never
    silently treated as empty."""
    out: List[Page] = []
    for p in sorted(pages, key=lambda p: p.page):
        if not p.ok:
            continue
        per: Dict[str, int] = {}
        page = page_from_lines(p, per)
        if page is None:
            per["no_text_boxes"] = 1
        else:
            out.append(page)
        if stats is not None and per:
            stats[p.page] = per
    return out
