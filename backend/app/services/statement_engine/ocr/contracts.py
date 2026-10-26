"""OCR data contracts (T4). Pure data, no I/O, no model imports.

The ocr-service returns one OcrDocument per request. Nothing in this package invents a confidence value:
`OcrLine.score` is the recogniser's own score (PP-OCR `rec_scores`); VLM blocks carry none.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

PAGE_OK = "ok"
PAGE_FAILED = "failed"


@dataclass(frozen=True)
class OcrBlock:
    """One layout region from PaddleOCR-VL: label (table, text, paragraph_title, header, footer, ...),
    bbox in page pixels [x0, y0, x1, y1], and content (plain text, or HTML for tables)."""

    label: str
    bbox: Sequence[float]
    content: str

    @property
    def is_table(self) -> bool:
        return self.label == "table" or "<table" in (self.content or "").lower()


@dataclass(frozen=True)
class OcrLine:
    """One PP-OCR text line (independent verifier): text, box [x0, y0, x1, y1] in page pixels, recogniser score 0..1."""

    text: str
    box: Sequence[float]
    score: float


@dataclass
class OcrPage:
    page: int                                   # 1-based page number in the source PDF
    width: float = 0.0                          # rendered image size, pixels
    height: float = 0.0
    status: str = PAGE_OK                       # ok | failed
    error: str = ""                             # failure code when status == failed
    blocks: List[OcrBlock] = field(default_factory=list)
    lines: List[OcrLine] = field(default_factory=list)   # verifier output; may be empty
    elapsed_s: float = 0.0
    markup_error: str = ""                      # why the VL markup was dropped by a guard ("" = kept or never present)

    @property
    def ok(self) -> bool:
        return self.status == PAGE_OK


@dataclass
class OcrDocument:
    pages: List[OcrPage] = field(default_factory=list)
    engine: str = ""                            # e.g. "PaddleOCR-VL-1.6"
    verifier: str = ""                          # e.g. "PP-OCRv5" ("" when not run)
    dpi: int = 0
    elapsed_s: float = 0.0
    error: str = ""                             # whole-request failure code ("" when the request succeeded)

    @property
    def failed_pages(self) -> List[int]:
        return [p.page for p in self.pages if not p.ok]

    @property
    def ok_pages(self) -> List[int]:
        return [p.page for p in self.pages if p.ok]


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def page_from_dict(d: Dict[str, Any]) -> OcrPage:
    blocks = [OcrBlock(str(b.get("label") or ""), [_f(x) for x in (b.get("bbox") or [0, 0, 0, 0])][:4],
                       str(b.get("content") or ""))
              for b in (d.get("blocks") or []) if isinstance(b, dict)]
    lines = []
    for ln in d.get("lines") or []:
        if not isinstance(ln, dict):
            continue
        score = ln.get("score")
        if score is None:
            continue                            # never invent a score
        lines.append(OcrLine(str(ln.get("text") or ""), [_f(x) for x in (ln.get("box") or [0, 0, 0, 0])][:4], _f(score)))
    return OcrPage(
        page=int(d.get("page") or 0), width=_f(d.get("width")), height=_f(d.get("height")),
        status=PAGE_FAILED if d.get("status") == PAGE_FAILED else PAGE_OK, error=str(d.get("error") or ""),
        blocks=blocks, lines=lines, elapsed_s=_f(d.get("elapsed_s")),
        markup_error=str(d.get("markup_error") or ""),
    )


def document_from_dict(d: Dict[str, Any]) -> OcrDocument:
    return OcrDocument(
        pages=[page_from_dict(p) for p in (d.get("pages") or []) if isinstance(p, dict)],
        engine=str(d.get("engine") or ""), verifier=str(d.get("verifier") or ""),
        dpi=int(d.get("dpi") or 0), elapsed_s=_f(d.get("elapsed_s")), error=str(d.get("error") or ""),
    )


def page_to_dict(p: OcrPage) -> Dict[str, Any]:
    return {
        "page": p.page, "width": p.width, "height": p.height, "status": p.status, "error": p.error,
        "elapsed_s": p.elapsed_s, "markup_error": p.markup_error,
        "blocks": [{"label": b.label, "bbox": list(b.bbox), "content": b.content} for b in p.blocks],
        "lines": [{"text": ln.text, "box": list(ln.box), "score": ln.score} for ln in p.lines],
    }


def document_to_dict(doc: OcrDocument) -> Dict[str, Any]:
    return {"engine": doc.engine, "verifier": doc.verifier, "dpi": doc.dpi, "elapsed_s": doc.elapsed_s,
            "error": doc.error, "pages": [page_to_dict(p) for p in doc.pages]}
