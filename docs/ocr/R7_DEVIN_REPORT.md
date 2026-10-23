# R7 (Devin) — ocr-service hardened for real traffic (service-side only)

Branch `devin/r7-service-hardening` (local, off `devin/r6-ocr-gpu` @ `a5c27ea` which carries the R6 work on
`integration/v2-waves` @ `f40047d`). Nothing pushed. Scope: `ocr-service/app.py` + tests only — no engine,
grid, reader, serve, verdict, or legacy-parser code touched (F10/F11/F13 are Claude's, in flight).

## Part 0 — housekeeping

`docker rm -f r6_vllm r6_ocr_vllm r6_ocr` → VRAM **1,313 MiB** (baseline).

## Part 1 — F9: runaway generation can never wedge the service

**Design**: `_Supervisor` owns ONE persistent worker process (`spawn` ctx — fork would inherit a broken CUDA
context). The worker loads the models once and serves page jobs over a duplex `mp.Pipe`; events (ready /
load_error) travel a second one-way pipe. The HTTP process never imports paddle — it renders pages, submits
jobs, and enforces the budget itself: `conn.poll(PAGE_TIMEOUT_S)`; on expiry it **SIGKILLs the worker and
respawns** (the page reports `OCR_PAGE_TIMEOUT`; other pages continue — they wait for the respawn via a
condvar, not billed to their budget). A worker that dies on its own (pipe EOF) is detected the same way.
Admission is a bounded semaphore (`OCR_MAX_INFLIGHT=2`, beyond → `503 OCR_BUSY`; one GPU job at a time —
stated choice: hard cap + 503, never unbounded queueing). `MAX_RESPAWNS=6` bounds a flapping worker →
permanent `failed: RespawnLimit`.

Bugs found and fixed while implementing (this is why the acceptance loop is short):
- `_submit` sent jobs while `state=respawning` onto a dying pipe → now state-checked under `_cond` (returns
  `down`, page gets `OCR_WORKER_DOWN`, next page re-awaits readiness).
- **Real deadlock**: `_spawn` took `_cond→_job_lock` while `_submit`'s kill path took `_job_lock→_cond` →
  froze the service with zero workers. Fixed: the kill runs only after `_job_lock` is released, and
  `_kill_and_respawn(proc)` kills only the exact process the timed-out job ran on (concurrent respawns are
  left alone).

| acceptance | command | result | evidence |
|---|---|---|---|
| a. runaway + health throughout | 10 s page budget vs ~14 s pages (every page is a runaway); `/health` sampled every second | **PASS** | page fails `OCR_PAGE_TIMEOUT` at ~10-15 s; **`/health` answered in ~3 ms on every one of ~250 samples** across kills, respawns, and the warmup runaway; request wall 42 s bounded. `respawns:2` recorded |
| b. next request after kill+respawn | warm-up-image runaway killed at its 60 s cap → respawn → normal 2-page request | **PASS** | next request 200, both pages `ok` (15.1/14.4 s); recovery ≈ **60-80 s** (full model reload from cache) |
| c. 20 consecutive page jobs | `POST /v1/ocr?pages=1|2` ×20 | **PASS** | 20/20 `ok`, 0 failures, 0 kills, 12.2-14.7 s/page, 271.7 s total |
| d. old failure mode | R6 evidence (not re-run) | cited | R6: health unreachable for minutes while `_worker_vlm` held the GIL; 24/27 statements OCR_TIMEOUT in the full run |

## Part 2 — F8: bounded warm-up, off the event loop

Warm-up is now a **job through the same worker pipe** (`_maybe_warmup` after `ready`), bounded by
`OCR_WARMUP_BUDGET_S=60` through the exact kill path pages use. If it overruns → worker killed+respawned,
`warmup:"timeout"` recorded, and the service **stays ready** (attempted once — `_warmup_attempted`).

Evidence (live): the tiny warm-up image **ran away on this GPU twice** (>60 s generation) → killed at the
cap → `health: {"worker":"ready","warmup":"timeout","status":"ok"}` — F8 fully exercised, not hypothetical.
When it succeeds: `warmup:"ok"`.

Time-to-ready: **~95-151 s** (vs 158 s before) — bounded by model LOAD, not warm-up; warm-up no longer
blocks readiness nor can hang the service. Page 1 never pays a cold start past the budget: pages are a flat
~13-15 s warm (the warm-up benefit preserved).

## Part 3 — F12: honest health

`/health` probes `OCR_VL_SERVER_URL + /models` (cached `OCR_VL_PROBE_TTL_S=5` s, 1.5 s timeout) when a server
backend is configured.

| case | health | POST /v1/ocr |
|---|---|---|
| R6 matrix 1.3a good service | 200 `{"status":"ok","worker":"ready","warmup":"ok"}` | 200, pages ok |
| R6 matrix 1.3b load failure (unwritable cache) | — | — **NOT RUN** (rebuild + ~3 min boot for a path proven twice; the load-error path is unchanged code: `load_error` event → `failed` + class name, tested in `test_model_load_failure_is_recorded_not_raised`) |
| **bad `OCR_VL_SERVER_URL`** | **503** `{"status":"error","error":"VLServerUnreachable:URLError","warmup":"failed:RuntimeError"}` | **503 `OCR_VL_SERVER_UNREACHABLE`** (new: the endpoint probes too — cached, costs nothing) |
| worker respawning | 503 `{"status":"loading","worker":"respawning"}` | 503 `OCR_MODELS_NOT_READY` |

## Part 4 — bound the generation at source

**Available and implemented**: `PaddleOCRVL.predict(max_new_tokens=N)` is a predict-time param → in
`vllm-server` mode it becomes `max_completion_tokens` (server-enforced). paddlex default is **8192** —
that was the runaway bound all along (≈800 s of generation at ~10 tok/s — the multi-minute wedges).

Set `OCR_VL_MAX_NEW_TOKENS=2048` (env-configurable; `0` = paddlex default). Direct A/B on the busiest
synthetic table page (65 `<td>` cells, 72 verifier lines):

| cap | page result |
|---|---|
| 8192 (default) | **ran away → killed at the 90 s budget** (elapsed 100.9 s, 0 blocks) |
| **2048** | **completed in 24.1 s, all 65 cells + 72 lines — zero truncation** |

A 40-row statement table needs ≈1,000-1,500 tokens/block; 2048 has ~35% headroom. The cap doesn't just
contain runaways — the same page that ran away at 8192 completes normally at 2048 (the degenerate tail is
cut before it starts looping). The backend's compression-ratio guard (`ocr/guards.py`) is untouched — this
is generation-side, not a post-hoc duplicate. Streaming/early-termination hooks: paddlex exposes none to the
pipeline caller (`predict` returns complete results); said so, not faked.

## Part 5 — evaluation (Claude's fix NOT landed → stability measurement)

`integration/v2-waves` tip is still `f40047d` — no F10/F11/F13 commit exists; per instructions this is a
**service-stability** run only (accuracy remains unmeasured, see below).

Full corpus (27 statements, `tmp/r6_corpus2`), hardened **in-process** service, one run:

- **46/54 pages returned** inside the 105 s client budget — vs **2/27 statements** in R6's run.
- **4 kills** during the run (runaway pages), `respawns:4`, service `ready` throughout, health ~3 ms.
- Codes: `ENGINE_ERROR` ×15 (F11, expected), `TOO_FEW_ROWS` ×8, `OCR_TIMEOUT` ×4 (client budget expired
  while pages queued behind respawns — the honest cost of a ~150 s reload).
- Per-page-slot p50 30.3 s / p95 60 s (includes respawn waits — reported, not hidden).
- Accuracy: **0/27 served — unmeasured by design** (engine fix pending; F10/F11 refusal dominates).

Artifacts: `docs/ocr/eval/report_r7_stability_inprocess.{json,md}`.

## Part 6 — regression

| check | result |
|---|---|
| `ocr-service/tests/` in Docker | **9/9 pass** (incl. new supervisor tests: kill+respawn, load-error, warmup-timeout) |
| `backend/tests/statement_engine/ocr/` in Docker | **32/32 pass** (needed `pip install reportlab` — the known F4 test-packaging gap from R5b) |
| `OCR_MODE` unset → identical to baseline | **PASS by construction** — zero backend code changed this round |
| default (non-vLLM) compose path | ocr-service Dockerfile unchanged, image builds clean (16.2 GB); vLLM override file unchanged and opt-in |

## What is now safe / not safe in production

- **Safe**: the service can front real traffic — a runaway page costs one page + ~60-80 s of reload while
  other requests and `/health` keep working; bad VL server config fails honestly at 503; warm-up can never
  hang startup; generation is bounded at source.
- **Not safe**: (1) accuracy is still unproven — every real-model statement hits F11 (`KeyError: 'credit'`)
  or `TOO_FEW_ROWS` until Claude's engine fix lands; (2) under repeated kills, a document's remaining pages
  wait ~150 s per respawn — the client's own budget will expire first (honest failure, but callers should
  expect it); (3) 4 s/page gate remains unmet on a 3060 (in-process ~13-15 s/page, vLLM p95 6.6 s).

## Bugs reported (Claude, engine-side — unchanged from R6, still blocking)

| id | sev | status |
|---|---|---|
| F11 | major | `anchors.py:324` `KeyError: 'credit'` — reproduced on 15/27 statements this run; Claude fixing |
| F10 | major | edge-column drop → LOW_CONFIDENCE_COLUMNS — partially mitigated by the corpus margin fix; Claude fixing grid alignment |
| F13 | minor | `infer.py:575` `None:.2f` masks failure codes — seen as ENGINE_ERROR masking; Claude fixing |
| F12 | — | **fixed here** (health + endpoint probe) |
| F9/F8 | — | **fixed here** (worker process + kill switch; bounded worker-side warm-up) |

## Config surface added (all env, defaults safe)

`OCR_LOAD_BUDGET_S=300`, `OCR_WARMUP_BUDGET_S=60`, `OCR_MAX_INFLIGHT=2`, `OCR_MAX_RESPAWNS=6`,
`OCR_VL_MAX_NEW_TOKENS=2048`, `OCR_VL_PROBE_TTL_S=5`.
