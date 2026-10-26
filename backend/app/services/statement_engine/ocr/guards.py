"""Per-page sanity guards on OCR output. A condemned reading is dropped with a code; it is never repaired.

Each reader on a page is judged ON ITS OWN: the VL model's markup and the line recogniser's boxes are independent,
so a loop in one must not discard the other. A page fails outright only when neither reader left anything usable.

Known failure modes:
- repetition loops: the decoder repeats a fragment many times. Two signals, either suffices:
    * compression ratio of the page TEXT (markup tags stripped) above LOOP_RATIO;
    * at least DUP_ROW_SHARE of the page's rows are exact duplicates of another row.
- runaway output: far more text than a statement page can hold.
- empty output: nothing read at all.

Calibration (2026-10-27, first real scans: 147 pages, 12 banks). The ratio was first set at 4.0 from prose-page
figures (normal ~1.5-2.5) and computed on the raw markup. A real statement table is repetitive by design: with tags
it compresses at a median 4.0 (p95 5.7), so that threshold condemned 70 of 147 healthy pages (48%) in 8 of 12
documents, and those transactions silently vanished from both readings. With tags stripped, healthy pages measure
median 2.7, p95 4.2, max 5.4; the three genuine loops measured 11.1, 13.7 and 24.0, and two of them repeated 69-78%
of their rows verbatim (healthy pages: median 0%, p95 13%). Hence 8.0 and 0.5, with a margin on both sides.
"""
from __future__ import annotations

import os
import re
import zlib
from collections import Counter
from typing import List

from .contracts import PAGE_FAILED, OcrDocument, OcrPage

LOOP_RATIO = float(os.environ.get("STATEMENT_ENGINE_OCR_LOOP_RATIO", "8.0"))
DUP_ROW_SHARE = float(os.environ.get("STATEMENT_ENGINE_OCR_DUP_ROW_SHARE", "0.5"))
DUP_MIN_ROWS = 10
LOOP_MIN_CHARS = 400
MAX_PAGE_CHARS = int(os.environ.get("STATEMENT_ENGINE_OCR_MAX_PAGE_CHARS", "60000"))

OCR_LOOP = "OCR_REPETITION_LOOP"
OCR_OVERSIZE = "OCR_OUTPUT_TOO_LARGE"
OCR_EMPTY = "OCR_EMPTY_PAGE"

_TAG = re.compile(r"<[^>]+>")
_ROW_END = re.compile(r"</tr\s*>", re.I)


def compression_ratio(text: str) -> float:
    raw = (text or "").encode("utf-8", "ignore")
    if not raw:
        return 0.0
    return len(raw) / max(1, len(zlib.compress(raw, 9)))


def duplicate_row_share(rows: List[str]) -> float:
    rows = [r for r in rows if r]
    if len(rows) < DUP_MIN_ROWS:
        return 0.0
    return sum(n - 1 for n in Counter(rows).values() if n > 1) / len(rows)


def _problem(text: str, rows: List[str]) -> str:
    if not text.strip():
        return OCR_EMPTY
    if len(text) > MAX_PAGE_CHARS:
        return OCR_OVERSIZE
    if len(text) >= LOOP_MIN_CHARS and compression_ratio(text) > LOOP_RATIO:
        return OCR_LOOP
    if duplicate_row_share(rows) >= DUP_ROW_SHARE:
        return OCR_LOOP
    return ""


def markup_problem(p: OcrPage) -> str:
    """The VL model's markup, judged as text: tags would make any healthy table look like a loop."""
    rows: List[str] = []
    for b in p.blocks:
        parts = _ROW_END.split(b.content or "") if b.is_table else (b.content or "").splitlines()
        rows += [" ".join(_TAG.sub(" ", x).split()) for x in parts]
    return _problem(_TAG.sub(" ", "\n".join(b.content or "" for b in p.blocks)), rows)


def lines_problem(p: OcrPage) -> str:
    texts = [(ln.text or "").strip() for ln in p.lines]
    return _problem("\n".join(texts), texts)


def page_problem(p: OcrPage) -> str:
    """'' when at least one reader left something usable on the page, else the failure code."""
    m = markup_problem(p) if p.blocks else OCR_EMPTY
    l = lines_problem(p) if p.lines else OCR_EMPTY
    if m and l:
        return m if m != OCR_EMPTY else l
    return ""


def apply_guards(doc: OcrDocument) -> List[int]:
    """Drop each insane reading in place, recording why; fail a page only when no reading survives.
    Returns the page numbers newly failed outright."""
    newly: List[int] = []
    for p in doc.pages:
        if not p.ok:
            continue
        m = markup_problem(p) if p.blocks else ""
        l = lines_problem(p) if p.lines else ""
        if m:
            p.blocks, p.markup_error = [], m
        if l:
            p.lines = []
        if not p.blocks and not p.lines:
            p.status, p.error = PAGE_FAILED, (m or l or OCR_EMPTY)
            newly.append(p.page)
    return newly
