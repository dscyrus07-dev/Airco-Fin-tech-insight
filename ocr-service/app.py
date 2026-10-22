"""ocr-service: PaddleOCR-VL-1.6 (layout + tables) and PP-OCRv5 (line verifier) behind a tiny HTTP API.

Separate from the CPU-only backend by design: this is the only component that needs a GPU. It listens on the
internal Docker network only; documents are processed in memory/temp files and never leave the machine.

    GET  /health                       -> {"status": "ok", "engine": ..., "verifier": ...}
    POST /v1/ocr?pages=1,2&verify=1    body: raw PDF bytes (already decrypted)  -> OcrDocument JSON
                                       (same shape as backend/app/services/statement_engine/ocr/contracts.py)

STATUS: written against the PaddleOCR 3.x documentation (paddleocr[doc-parser]==3.7.0). It has NOT been run
against the real models yet (no GPU in the development environment). The pure mapping/rendering helpers are
unit-tested; the model calls are isolated in `_Models` so the first GPU run only has to confirm those few lines.
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional

try:    # module level on purpose: with `from __future__ import annotations` FastAPI resolves the endpoint's
        # `request: Request` annotation against THIS module's globals (a function-local import made /v1/ocr 422).
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse
except ImportError:                                   # helpers/tests run without fastapi installed
    FastAPI = HTTPException = Request = JSONResponse = None

ENGINE = "PaddleOCR-VL-1.6"
VERIFIER = "PP-OCRv5"
DPI = int(os.environ.get("OCR_DPI", "200"))
MAX_PAGES = int(os.environ.get("OCR_MAX_PAGES", "60"))
MAX_BODY_BYTES = int(os.environ.get("OCR_MAX_BODY_MB", "40")) * 1024 * 1024
PAGE_TIMEOUT_S = float(os.environ.get("OCR_PAGE_TIMEOUT_S", "90"))
VL_SERVER_URL = os.environ.get("OCR_VL_SERVER_URL", "")          # e.g. http://vllm:8118/v1 (recommended); empty = in-process


# ---------------------------------------------------------------- pure helpers (unit-tested) ----------

def parse_pages_param(value: Optional[str], page_count: int) -> List[int]:
    """'1,2' -> [1, 2]; None/'' -> all pages. Out-of-range and non-numeric entries are dropped."""
    if not value:
        return list(range(1, page_count + 1))
    out: List[int] = []
    for part in value.split(","):
        part = part.strip()
        if part.isdigit() and 1 <= int(part) <= page_count and int(part) not in out:
            out.append(int(part))
    return out


def blocks_from_vl(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """PaddleOCR-VL result json -> [{label, bbox, content}] in the model's reading order."""
    data = result.get("res", result) if isinstance(result, dict) else {}
    out = []
    for b in data.get("parsing_res_list") or []:
        if not isinstance(b, dict):
            continue
        bbox = b.get("block_bbox") or [0, 0, 0, 0]
        out.append({"label": str(b.get("block_label") or ""), "bbox": [float(x) for x in bbox][:4],
                    "content": str(b.get("block_content") or "")})
    return out


def lines_from_ocr(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """PP-OCR result json -> [{text, box, score}]. A line without a score is dropped (scores are never invented)."""
    data = result.get("res", result) if isinstance(result, dict) else {}
    texts, scores, boxes = data.get("rec_texts") or [], data.get("rec_scores") or [], data.get("rec_boxes") or []
    out = []
    for i, t in enumerate(texts):
        if i >= len(scores):
            break
        box = [float(x) for x in boxes[i]][:4] if i < len(boxes) else [0.0, 0.0, 0.0, 0.0]
        out.append({"text": str(t), "box": box, "score": float(scores[i])})
    return out


def render_pages(pdf_path: str, pages: List[int], dpi: int = DPI):
    """Yield (page_number, png_bytes, width, height). Uses PyMuPDF; one page in memory at a time."""
    import fitz  # PyMuPDF

    with fitz.open(pdf_path) as doc:
        for n in pages:
            pix = doc[n - 1].get_pixmap(dpi=dpi, alpha=False)
            yield n, pix.tobytes("png"), float(pix.width), float(pix.height)


# ---------------------------------------------------------------- model wrapper (needs GPU/models) ------

class _Models:
    """Loaded once at start-up; never per request or per page."""

    def __init__(self) -> None:
        self.lock = threading.Lock()           # one GPU job at a time: predictable latency and memory
        self.vl = None
        self.ocr = None
        self.error = ""                          # class name of the load failure, "" when fine

    def load(self) -> None:
        from paddleocr import PaddleOCR, PaddleOCRVL   # imported lazily so helpers/tests need no Paddle

        kwargs: Dict[str, Any] = {"use_doc_orientation_classify": True}   # upside-down pages otherwise fail
        if VL_SERVER_URL:
            kwargs.update(vl_rec_backend="vllm-server", vl_rec_server_url=VL_SERVER_URL)
        self.vl = PaddleOCRVL(**kwargs)
        self.ocr = PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False,
                             use_textline_orientation=False)

    def load_guarded(self) -> None:
        """Load + warm up. A failure is recorded (class name only) instead of killing the process, so /health can
        say why the service is not ready and the backend fails jobs with a clean OCR code."""
        try:
            self.load()
            self.warm_up()
            self.error = ""
        except Exception as exc:
            self.vl = self.ocr = None
            self.error = type(exc).__name__

    def warm_up(self) -> None:
        """First real call pays kernel/graph initialisation (~tens of seconds). Pay it at startup, not on page 1."""
        try:
            import numpy as np
            import cv2
            img = np.full((200, 600, 3), 255, dtype="uint8")
            cv2.putText(img, "warm up 1,234.56", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
                path = fh.name
            try:
                cv2.imwrite(path, img)
                self.vl_page(path)
                self.lines_page(path)
            finally:
                os.unlink(path)
        except Exception:
            pass                                       # warm-up is best effort; real requests report their own errors

    def vl_page(self, png_path: str) -> List[Dict[str, Any]]:
        res = self.vl.predict(png_path)
        first = list(res)[0]
        return blocks_from_vl(getattr(first, "json", first))

    def lines_page(self, png_path: str) -> List[Dict[str, Any]]:
        res = self.ocr.predict(png_path)
        first = list(res)[0]
        return lines_from_ocr(getattr(first, "json", first))


MODELS = _Models()


def ocr_pdf(pdf_path: str, pages_param: Optional[str], verify: bool) -> Dict[str, Any]:
    import fitz

    t0 = time.monotonic()
    with fitz.open(pdf_path) as doc:
        count = doc.page_count
    pages = parse_pages_param(pages_param, count)
    if len(pages) > MAX_PAGES:
        return {"engine": ENGINE, "verifier": "", "dpi": DPI, "pages": [], "error": "OCR_TOO_MANY_PAGES"}
    out_pages = []
    for n, png, w, h in render_pages(pdf_path, pages):
        p0 = time.monotonic()
        page = {"page": n, "width": w, "height": h, "status": "ok", "error": "", "blocks": [], "lines": []}
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
            fh.write(png)
            path = fh.name
        try:
            with MODELS.lock:
                page["blocks"] = MODELS.vl_page(path)
                if verify:
                    page["lines"] = MODELS.lines_page(path)
            if time.monotonic() - p0 > PAGE_TIMEOUT_S:
                page.update(status="failed", error="OCR_TIMEOUT", blocks=[], lines=[])
        except Exception as exc:                                    # one bad page never kills the document
            page.update(status="failed", error=f"OCR_PAGE_ERROR:{type(exc).__name__}", blocks=[], lines=[])
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        page["elapsed_s"] = round(time.monotonic() - p0, 3)
        out_pages.append(page)
    return {"engine": ENGINE, "verifier": VERIFIER if verify else "", "dpi": DPI,
            "elapsed_s": round(time.monotonic() - t0, 3), "error": "", "pages": out_pages}


# ---------------------------------------------------------------- HTTP ----------

def create_app():
    app = FastAPI(title="airco-ocr-service")

    @app.on_event("startup")
    def _startup() -> None:
        MODELS.load_guarded()

    @app.get("/health")
    def health():
        ready = MODELS.vl is not None
        body = {"status": "ok" if ready else ("error" if MODELS.error else "loading"),
                "engine": ENGINE, "verifier": VERIFIER}
        if MODELS.error:
            body["error"] = MODELS.error
        return body if ready else JSONResponse(body, status_code=503)

    @app.post("/v1/ocr")
    async def ocr(request: Request, pages: Optional[str] = None, verify: int = 1):
        if MODELS.vl is None:
            raise HTTPException(503, "OCR_MODELS_NOT_READY")
        body = await request.body()
        if not body.startswith(b"%PDF"):
            raise HTTPException(400, "body must be a PDF")
        if len(body) > MAX_BODY_BYTES:
            raise HTTPException(413, "PDF too large")
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
            fh.write(body)
            path = fh.name
        try:
            import anyio

            return await anyio.to_thread.run_sync(ocr_pdf, path, pages, bool(verify))
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    return app


app = create_app() if os.environ.get("OCR_SERVICE_AUTOSTART", "1") == "1" and __name__ != "__main__" else None
