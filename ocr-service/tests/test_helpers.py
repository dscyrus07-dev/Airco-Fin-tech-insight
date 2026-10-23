import importlib.util, multiprocessing as _mp, os, sys, time
os.environ["OCR_SERVICE_AUTOSTART"] = "0"
spec = importlib.util.spec_from_file_location("ocr_app", os.path.join(os.path.dirname(__file__), "..", "app.py"))
m = importlib.util.module_from_spec(spec); sys.modules["ocr_app"] = m; spec.loader.exec_module(m)


def test_pages_param():
    assert m.parse_pages_param("1,2", 5) == [1, 2]
    assert m.parse_pages_param("", 3) == [1, 2, 3]
    assert m.parse_pages_param("0,9,x,2,2", 5) == [2]


def test_vl_mapping():
    r = {"res": {"parsing_res_list": [{"block_label": "table", "block_bbox": [1, 2, 3, 4], "block_content": "<table></table>"}]}}
    assert m.blocks_from_vl(r) == [{"label": "table", "bbox": [1.0, 2.0, 3.0, 4.0], "content": "<table></table>"}]
    assert m.blocks_from_vl({}) == []


def test_ocr_lines_drop_unscored_lines():
    r = {"rec_texts": ["a", "b"], "rec_scores": [0.99], "rec_boxes": [[0, 0, 1, 1], [0, 0, 1, 1]]}
    assert m.lines_from_ocr(r) == [{"text": "a", "box": [0.0, 0.0, 1.0, 1.0], "score": 0.99}]


def test_render_pages(tmp_path):
    fitz = __import__("pytest").importorskip("fitz")
    d = fitz.open(); d.new_page(width=200, height=100); p = str(tmp_path / "a.pdf"); d.save(p)
    got = list(m.render_pages(p, [1], dpi=72))
    assert got[0][0] == 1 and got[0][1][:4] == b"\x89PNG"


def test_endpoint_request_param_is_not_a_query_param():
    """F7: with `from __future__ import annotations` a function-local Request import made /v1/ocr demand ?request=."""
    __import__("pytest").importorskip("fastapi")
    app = m.create_app()
    route = [r for r in app.routes if getattr(r, "path", "") == "/v1/ocr"][0]
    assert [q.name for q in route.dependant.query_params] == ["pages", "verify"]


def _fake_worker(job_conn, evt_conn, page_delay=0.01, hang=False, load_error=None):
    if load_error:
        evt_conn.send({"event": "load_error", "error": load_error})
        evt_conn.close()
        return
    evt_conn.send({"event": "ready"})
    while True:
        try:
            job = job_conn.recv()
        except (EOFError, KeyboardInterrupt):
            break
        if job.get("cmd") == "shutdown":
            break
        if job.get("cmd") == "warmup":
            job_conn.send({"ok": True})
            continue
        if hang:
            time.sleep(3600)                    # runaway: never answers within the page budget
            continue
        time.sleep(page_delay)
        job_conn.send({"ok": True, "blocks": [{"label": "text", "bbox": [0, 0, 1, 1], "content": "x"}],
                       "lines": [{"text": "x", "box": [0, 0, 1, 1], "score": 0.9}]})
    job_conn.close()


def test_model_load_failure_is_recorded_not_raised():
    """F3: a failing model load must leave the process up so /health can report it."""
    s = m._Supervisor(target=lambda j, e: _fake_worker(j, e, load_error="ImportError"), ctx=_mp.get_context("fork"))
    s.start()
    assert s._await_ready(30) is False
    for _ in range(50):
        if s.state == "failed":
            break
        time.sleep(0.1)
    body, ok = s.health_body()
    assert s.state == "failed" and ok is False
    assert body["error"] == "ImportError"


def test_runaway_page_is_killed_and_worker_respawns():
    """F9: a runaway job must be hard-killed within ~budget and the worker respawned."""
    s = m._Supervisor(target=lambda j, e: _fake_worker(j, e, hang=True), ctx=_mp.get_context("fork"))
    s.start()
    assert s._await_ready(60)
    s._warmup_attempted = True                        # isolate the test from the warm-up job
    t0 = time.monotonic()
    kind, _ = s.run_page("/nonexistent.png", False, budget_s=2.0)
    elapsed = time.monotonic() - t0
    assert kind == "timeout" and elapsed < 8           # killed ~at the 2 s budget, not 3600 s
    assert s.respawns == 1
    # while respawning the supervisor reports not-ready; health stays cheap to answer
    body, ok = s.health_body()
    assert ok is False or s.state == "ready"           # fake worker reloads instantly in tests


def _flaky_worker(job_conn, evt_conn, hang_flag):
    """Sends ready, then hangs forever on the FIRST page job; every later job answers.

    The flag is shared memory, so the respawned worker (same target, same flag) is healthy:
    deterministic recovery without racing the spawn thread to swap _target."""
    evt_conn.send({"event": "ready"})
    while True:
        try:
            job = job_conn.recv()
        except (EOFError, KeyboardInterrupt):
            break
        if job.get("cmd") == "shutdown":
            break
        if job.get("cmd") == "warmup":
            job_conn.send({"ok": True})
            continue
        if hang_flag.value:
            hang_flag.value = 0
            time.sleep(3600)
            continue
        time.sleep(0.01)
        job_conn.send({"ok": True, "blocks": [{"label": "text", "bbox": [0, 0, 1, 1], "content": "x"}],
                       "lines": [{"text": "x", "box": [0, 0, 1, 1], "score": 0.9}]})
    job_conn.close()


def test_worker_comes_back_after_kill():
    """After a kill+respawn the next job succeeds (the respawned worker is healthy)."""
    ctx = _mp.get_context("fork")
    hang_flag = ctx.Value("i", 1)
    s = m._Supervisor(target=lambda j, e: _flaky_worker(j, e, hang_flag), ctx=ctx)
    s.start()
    assert s._await_ready(60)
    s._warmup_attempted = True
    kind, _ = s.run_page("/x.png", False, budget_s=1.0)
    assert kind == "timeout"
    kind, res = s.run_page("/x.png", True, budget_s=10.0)
    assert kind == "ok" and res["blocks"]


def test_warmup_timeout_marks_skipped_and_service_ready():
    """F8: a warm-up that overruns its cap must not block readiness."""
    def w(job_conn, evt_conn):
        evt_conn.send({"event": "ready"})
        while True:
            try:
                job = job_conn.recv()
            except (EOFError, KeyboardInterrupt):
                break
            if job.get("cmd") == "warmup":
                time.sleep(3600)
                continue
            job_conn.send({"ok": True, "blocks": [], "lines": []})
        job_conn.close()
    s = m._Supervisor(target=w, ctx=_mp.get_context("fork"))
    m.WARMUP_BUDGET_S = 1.0
    s.start()
    assert s._await_ready(60)
    for _ in range(100):
        if s.warmup != "pending":
            break
        time.sleep(0.1)
    assert s.warmup == "timeout"                       # bounded, best-effort, recorded
    for _ in range(50):
        if s.state == "ready":
            break
        time.sleep(0.1)
    body, ok = s.health_body()
    assert body["warmup"] == "timeout"
    m.WARMUP_BUDGET_S = 60.0
