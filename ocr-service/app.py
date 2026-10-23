"""ocr-service: PaddleOCR-VL-1.6 (layout + tables) and PP-OCRv5 (line verifier) behind a tiny HTTP API.

Separate from the CPU-only backend by design: this is the only component that needs a GPU. It listens on the
internal Docker network only; documents are processed in memory/temp files and never leave the machine.

    GET  /health                       -> {"status": "ok", "engine": ..., "verifier": ...}  (503 until ready)
    POST /v1/ocr?pages=1,2&verify=1    body: raw PDF bytes (already decrypted)  -> OcrDocument JSON
                                       (same shape as backend/app/services/statement_engine/ocr/contracts.py)

R7 hardening (F8/F9/F12): the models live in a PERSISTENT WORKER PROCESS (spawned once, models loaded once).
The HTTP process never imports paddle: it sends page jobs over a pipe and enforces the per-page budget itself.
A page that overruns gets its worker SIGKILLed and respawned — a runaway generation can hold the GIL inside the
worker but can never starve the HTTP process, so /health keeps answering and other documents still get served.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

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
LOAD_BUDGET_S = float(os.environ.get("OCR_LOAD_BUDGET_S", "300"))        # worker spawn + model load ceiling
WARMUP_BUDGET_S = float(os.environ.get("OCR_WARMUP_BUDGET_S", "60"))     # best-effort warm-up, then skipped
MAX_INFLIGHT = int(os.environ.get("OCR_MAX_INFLIGHT", "2"))              # documents; beyond -> 503 OCR_BUSY
MAX_RESPAWNS = int(os.environ.get("OCR_MAX_RESPAWNS", "6"))              # flapping worker -> permanent failure
VL_MAX_NEW_TOKENS = int(os.environ.get("OCR_VL_MAX_NEW_TOKENS", "2048"))  # bounds one generation; 0 = paddlex default
PROBE_TTL_S = float(os.environ.get("OCR_VL_PROBE_TTL_S", "5"))           # health probe cache for the VL server


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


# ---------------------------------------------------------------- worker process (owns the GPU) --------

def _worker_main(job_conn, evt_conn) -> None:
    """Spawned ONCE per model set. Loads the models, signals 'ready', then serves page jobs forever.
    Paddle imports live here only — the HTTP process never touches them."""
    try:
        from paddleocr import PaddleOCR, PaddleOCRVL  # noqa: only in the worker
        kwargs: Dict[str, Any] = {"use_doc_orientation_classify": True}
        if VL_SERVER_URL:
            kwargs.update(vl_rec_backend="vllm-server", vl_rec_server_url=VL_SERVER_URL)
        vl = PaddleOCRVL(**kwargs)
        ocr = PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False,
                        use_textline_orientation=False)
    except Exception as exc:
        evt_conn.send({"event": "load_error", "error": type(exc).__name__})
        evt_conn.close()
        return
    evt_conn.send({"event": "ready"})

    def vl_page(png_path: str) -> List[Dict[str, Any]]:
        kw = {"max_new_tokens": VL_MAX_NEW_TOKENS} if VL_MAX_NEW_TOKENS > 0 else {}
        res = vl.predict(png_path, **kw)
        first = list(res)[0]
        return blocks_from_vl(getattr(first, "json", first))

    def lines_page(png_path: str) -> List[Dict[str, Any]]:
        res = ocr.predict(png_path)
        first = list(res)[0]
        return lines_from_ocr(getattr(first, "json", first))

    while True:
        try:
            job = job_conn.recv()
        except (EOFError, KeyboardInterrupt):
            break
        cmd = job.get("cmd")
        if cmd == "shutdown":
            break
        try:
            if cmd == "warmup":
                import numpy as np
                import cv2
                img = np.full((200, 600, 3), 255, dtype="uint8")
                cv2.putText(img, "warm up 1,234.56", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
                    path = fh.name
                try:
                    cv2.imwrite(path, img)
                    vl_page(path)
                    lines_page(path)
                finally:
                    os.unlink(path)
                job_conn.send({"ok": True})
            else:
                out = {"ok": True, "blocks": vl_page(job["path"])}
                out["lines"] = lines_page(job["path"]) if job.get("verify") else []
                job_conn.send(out)
        except Exception as exc:
            try:
                job_conn.send({"ok": False, "error": type(exc).__name__})
            except Exception:
                break
    job_conn.close()


class _Supervisor:
    """Parent-side owner of the worker: spawn once, enforce the page budget, kill+respawn on overrun.

    state: loading -> ready | failed ; ready -> respawning -> ready | failed (kills bounded by MAX_RESPAWNS)
    All transitions are driven by a watcher thread so the event loop never blocks on the GPU.
    """

    def __init__(self, target=None, ctx=None) -> None:
        # spawn is required for real CUDA workers (a forked child inherits a broken CUDA context).
        # tests pass ctx=mp.get_context("fork") so in-line fake targets need no pickling.
        self._ctx = ctx or mp.get_context("spawn")
        self._target = target or _worker_main
        self._state = "loading"
        self._error = ""
        self._proc: Optional[mp.Process] = None
        self._job_conn = None
        self._cond = threading.Condition()
        self._job_lock = threading.Lock()            # one outstanding page job
        self.respawns = 0
        self.warmup = "pending"                      # pending | ok | timeout | skipped | failed:<class>
        self._warmup_attempted = False
        self._last_ready_at = 0.0
        self._probe_cache: Tuple[float, bool, str] = (0.0, True, "")

    # ----- state -----
    @property
    def state(self) -> str:
        with self._cond:
            return self._state

    @property
    def error(self) -> str:
        with self._cond:
            return self._error

    @property
    def ready(self) -> bool:
        return self.state == "ready"

    def start(self) -> None:
        self._spawn()

    def _spawn(self) -> None:
        with self._cond:
            if self.respawns > MAX_RESPAWNS:
                self._state, self._error = "failed", "RespawnLimit"
                self._cond.notify_all()
                return
            job_p, job_w = self._ctx.Pipe(duplex=True)
            evt_p, evt_w = self._ctx.Pipe(duplex=False)
            with self._job_lock:                        # conn swap is atomic wrt _submit's send
                self._job_conn = job_p
            # daemon=False: paddle internals may spawn helpers; the worker self-exits when the job
            # pipe EOFs (parent death), so it cannot outlive the service.
            self._proc = self._ctx.Process(target=self._target, args=(job_w, evt_w), daemon=False)
            self._proc.start()
            self._state = "loading" if self._state != "respawning" else "respawning"
            evt = evt_p
        threading.Thread(target=self._watch_ready, args=(evt,), daemon=True).start()

    def _watch_ready(self, evt) -> None:
        deadline = time.monotonic() + LOAD_BUDGET_S
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                self._mark_failed("LoadTimeout")
                return
            try:
                if evt.poll(min(left, 2.0)):
                    msg = evt.recv()
                else:
                    continue
            except (EOFError, OSError):
                self._mark_failed("WorkerExitDuringLoad")
                return
            ev = msg.get("event")
            if ev == "ready":
                with self._cond:
                    if self._state in ("loading", "respawning"):
                        self._state = "ready"
                        self._last_ready_at = time.monotonic()
                    self._cond.notify_all()
                self._maybe_warmup()
                return
            if ev == "load_error":
                self._mark_failed(str(msg.get("error") or "LoadError"))
                return

    def _mark_failed(self, error: str) -> None:
        with self._cond:
            self._state, self._error = "failed", error
            self._cond.notify_all()
        self._kill_proc()

    def _kill_proc(self) -> None:
        proc = self._proc
        if proc is not None and proc.is_alive():
            try:
                proc.kill()                            # SIGKILL — threads holding the GIL cannot outlive it
            except Exception:
                pass
            try:
                proc.join(timeout=5)
            except Exception:
                pass

    def _maybe_warmup(self) -> None:
        with self._cond:
            if self._warmup_attempted:
                return
            self._warmup_attempted = True
        def _run() -> None:
            res = self._submit({"cmd": "warmup"}, WARMUP_BUDGET_S)
            with self._cond:
                if res[0] == "ok":
                    self.warmup = "ok"
                elif res[0] == "timeout":
                    self.warmup = "timeout"
                else:
                    self.warmup = f"failed:{res[1]}"
        threading.Thread(target=_run, daemon=True).start()

    def _submit(self, job: Dict[str, Any], budget_s: float) -> Tuple[str, Any]:
        """Send one job, wait up to budget_s. On expiry or worker death: SIGKILL + respawn.
        Returns ("ok", result) | ("timeout", None) | ("error", class) | ("down", None).
        Lock order is always _cond -> _job_lock; the kill path runs AFTER _job_lock is released
        and only kills the exact proc this job ran on (a concurrent respawn is left alone)."""
        with self._cond:
            if self._state != "ready":                     # never queue a job onto a dying/respawning worker
                return ("down", None)
            conn, proc = self._job_conn, self._proc
        outcome: Tuple[str, Any]
        with self._job_lock:
            try:
                conn.send(job)
                if not conn.poll(budget_s):
                    outcome = ("timeout", None)
                else:
                    res = conn.recv()
                    outcome = ("ok", res) if res.get("ok") else ("error", str(res.get("error") or "Error"))
            except (OSError, EOFError):
                outcome = ("down", None)
        if outcome[0] in ("timeout", "down"):
            self._kill_and_respawn(proc)
        return outcome

    def _kill_and_respawn(self, proc) -> None:
        with self._cond:
            # only kill the worker this job actually ran on; if it is already gone (another
            # thread's kill landed first, or a respawn replaced it) there is nothing to do
            if self._proc is not proc or self._state in ("respawning", "failed"):
                return
            self.respawns += 1
            self._state = "respawning" if self.respawns <= MAX_RESPAWNS else "failed"
            if self.respawns > MAX_RESPAWNS:
                self._error = "RespawnLimit"
            self._cond.notify_all()
        self._kill_proc()
        if self.respawns <= MAX_RESPAWNS:
            threading.Thread(target=self._spawn, daemon=True).start()

    def run_page(self, png_path: str, verify: bool, budget_s: float = PAGE_TIMEOUT_S) -> Tuple[str, Any]:
        """Returns ("ok", {"blocks":..,"lines":..}) | ("timeout",None) | ("error",class) | ("down",None).
        Waits for readiness so pages queued behind a respawn still get served (within the load budget)."""
        if not self._await_ready(LOAD_BUDGET_S):
            return ("down", None)
        return self._submit({"cmd": "page", "path": png_path, "verify": verify}, budget_s)

    def _await_ready(self, timeout_s: float) -> bool:
        end = time.monotonic() + timeout_s
        with self._cond:
            while self._state in ("loading", "respawning"):
                left = end - time.monotonic()
                if left <= 0:
                    return False
                self._cond.wait(min(left, 1.0))
            return self._state == "ready"

    # ----- health -----
    def vl_server_probe(self) -> Tuple[bool, str]:
        """Probe the configured VL server (cheap, cached PROBE_TTL_S). F12: health must reflect the real path."""
        if not VL_SERVER_URL:
            return True, ""
        now = time.monotonic()
        ts, ok, why = self._probe_cache
        if now - ts < PROBE_TTL_S:
            return ok, why
        try:
            import urllib.request
            url = VL_SERVER_URL.rstrip("/") + "/models"
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                ok, why = resp.status == 200, ""
        except Exception as exc:
            ok, why = False, type(exc).__name__
        self._probe_cache = (now, ok, why)
        return ok, why

    def health_body(self) -> Tuple[dict, bool]:
        body: Dict[str, Any] = {"engine": ENGINE, "verifier": VERIFIER, "worker": self.state,
                                "warmup": self.warmup, "respawns": self.respawns}
        if self.state == "ready":
            ok, why = self.vl_server_probe()
            if ok:
                body["status"] = "ok"
                return body, True
            body["status"], body["error"] = "error", f"VLServerUnreachable:{why}"
            return body, False
        if self.state == "failed":
            body["status"], body["error"] = "error", self._error
            return body, False
        body["status"] = "loading"
        return body, False


SUPERVISOR = _Supervisor()


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
            kind, res = SUPERVISOR.run_page(path, verify)
            if kind == "ok":
                page["blocks"], page["lines"] = res.get("blocks", []), res.get("lines", [])
            elif kind == "timeout":
                page.update(status="failed", error="OCR_PAGE_TIMEOUT")      # worker was SIGKILLed + respawned
            elif kind == "down":
                page.update(status="failed", error="OCR_WORKER_DOWN")
            else:
                page.update(status="failed", error=f"OCR_PAGE_ERROR:{res}")
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
    inflight = threading.Semaphore(MAX_INFLIGHT)      # bounded admission; beyond -> 503 OCR_BUSY

    @app.on_event("startup")
    def _startup() -> None:
        SUPERVISOR.start()

    @app.get("/health")
    def health():
        body, ok = SUPERVISOR.health_body()
        return body if ok else JSONResponse(body, status_code=503)

    @app.post("/v1/ocr")
    async def ocr(request: Request, pages: Optional[str] = None, verify: int = 1):
        if not SUPERVISOR.ready:
            raise HTTPException(503, "OCR_MODELS_NOT_READY")   # loading/respawning/failed: never queue a dead worker
        ok, _ = SUPERVISOR.vl_server_probe()
        if not ok:
            raise HTTPException(503, "OCR_VL_SERVER_UNREACHABLE")   # configured VL backend is down (F12)
        if not inflight.acquire(blocking=False):
            raise HTTPException(503, "OCR_BUSY")
        try:
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
        finally:
            inflight.release()

    return app


app = create_app() if os.environ.get("OCR_SERVICE_AUTOSTART", "1") == "1" and __name__ != "__main__" else None
