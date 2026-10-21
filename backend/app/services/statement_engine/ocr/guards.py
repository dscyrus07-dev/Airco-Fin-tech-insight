"""Per-page sanity guards on OCR output. A guarded page becomes FAILED with a code; it is never repaired.

Known PaddleOCR-VL failure modes (see docs/ocr/UNIVERSAL_OCR_PHASE1.md, Part B):
- repetition loops: the decoder repeats a fragment thousands of times. Detected by the zlib compression ratio of
  the page text (normal pages ~1.5-2.5, a loop page ~10); threshold 4.0 as reported in the local benchmark notes.
- runaway output: far more text than a statement page can hold.
- empty output: nothing read at all.
"""
from __future__ import annotations

import os
import zlib
from typing import List

from .contracts import PAGE_FAILED, OcrDocument, OcrPage

LOOP_RATIO = float(os.environ.get("STATEMENT_ENGINE_OCR_LOOP_RATIO", "4.0"))
LOOP_MIN_CHARS = 400
MAX_PAGE_CHARS = int(os.environ.get("STATEMENT_ENGINE_OCR_MAX_PAGE_CHARS", "60000"))

OCR_LOOP = "OCR_REPETITION_LOOP"
OCR_OVERSIZE = "OCR_OUTPUT_TOO_LARGE"
OCR_EMPTY = "OCR_EMPTY_PAGE"


def compression_ratio(text: str) -> float:
    raw = (text or "").encode("utf-8", "ignore")
    if not raw:
        return 0.0
    return len(raw) / max(1, len(zlib.compress(raw, 9)))


def page_problem(p: OcrPage) -> str:
    """'' when the page looks sane, else a failure code."""
    text = "\n".join(b.content or "" for b in p.blocks)
    if not text.strip():
        return OCR_EMPTY
    if len(text) > MAX_PAGE_CHARS:
        return OCR_OVERSIZE
    if len(text) >= LOOP_MIN_CHARS and compression_ratio(text) > LOOP_RATIO:
        return OCR_LOOP
    return ""


def apply_guards(doc: OcrDocument) -> List[int]:
    """Mark insane pages FAILED in place (their blocks are dropped). Returns the page numbers newly failed."""
    newly: List[int] = []
    for p in doc.pages:
        if not p.ok:
            continue
        code = page_problem(p)
        if code:
            p.status, p.error, p.blocks = PAGE_FAILED, code, []
            newly.append(p.page)
    return newly
