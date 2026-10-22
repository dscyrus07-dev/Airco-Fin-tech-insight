# R5 (Devin) — UI redesign 830d161 + Universal OCR tier T4 (6eedd52, 486fb9c)

Branch `devin/r5b-verify` (local, off `integration/v2-waves` @ `486fb9c`). Nothing pushed.
Stack: compose project `devin_r5` (containers `r5b_*`), host keycloak/auth reused read-only.
Corpus untouched; no passwords.txt; no OCR APIs; no GPU; sha8 + counts only.

## Part 1 — Backend tests (real environment, in Docker)

| check | command | result | evidence |
|---|---|---|---|
| Build backend image | `docker build -t r5b-backend -f backend/Dockerfile backend` | PASS | image built from python:3.11-slim, deps installed |
| Full suite @486fb9c | `docker run -v repo:/repo -w /repo/backend r5b-backend pytest tests/` | **26 failed, 894 passed, 19 skipped** | failure list saved |
| Full suite @830d161 (baseline) | same, worktree `wt-r5base2` @830d161 | **26 failed, 862 passed, 19 skipped** | failure list saved |
| Regression compare | diff of failure sets | **IDENTICAL — zero regressions** | +32 passed = the 32 new OCR tests |
| OCR suite | `pytest tests/statement_engine/ocr/ -v` | **32/32 PASS** incl. `test_ocr_analysis.py` (4 tests) and all synth-dependent modules — all load and pass in a real container | 3.19s |
| OCR-off byte-identity | unit: `test_mode_defaults_off`, `test_text_pdf_never_touches_ocr`, `test_flag_off_scanned_file_behaves_as_before`; suite-level: identical failure sets; live: text-PDF flow unchanged on the OCR-off airco stack | PASS | see OCR suite output |

Note (infra): the backend image alone cannot run the full suite — `tests/statement_engine/extraction/test_n1/n2/n3_header_caps.py` and `test_universal.py` need `tools/onboarding/synth` (repo root, outside the backend-only build context) and `reportlab` (not in requirements.txt). Tests were run with the repo mounted into the container (`-v repo:/repo -w /repo/backend`), which uses the image's real deps. Infra fix suggestion: copy `tools/` in the Dockerfile or move `synth` under `backend/tests`.

## Part 2 — OCR integration with fixtures (mock mode, real API flow)

Fixtures generated with `tests/statement_engine/ocr/synthetic.py` (image-only PDFs via PIL; fixture JSON named `<sha256(pdf)>.json` in `infra/docker/r5b_fixtures/`, mounted read-only at `/fixtures`).

| check | result | evidence |
|---|---|---|
| analyze → confirm(OVERRIDE other) → process, clean 2-page fixture | PASS | job completed; `statement_engine`: engine=ocr, verdict=REVIEW, needs_review=true, **anchored=false**, review_codes=[OCR_READER]; ocr block: tier=T4, pre_cap_verdict=VERIFIED, check_results schema/chain/side=pass, pages_ok=[1,2] |
| verdict never VERIFIED | PASS | verdict=REVIEW with `detail: "capped from VERIFIED"` |
| workbook downloads + Statement Check OCR section | PASS | 200, 15,758 bytes; sheets: Summary, Monthly Analysis, Top 5 Credits/Debits, Bounce And Penal, Salary, Loan Repayment, Credit Card Payments, Transactions, **Statement Check** (10 total). Statement Check: Engine=ocr, Verdict=REVIEW, Independently verified=no, Review reasons=OCR_READER, Pages read=1,2, Pages NOT read=none |
| transactions categorized (words.json), not 0% | PASS | stats: total_transactions=24, classified=24, coverage_percent=100.0 |
| failed page listed + OCR_PARTIAL_PAGES + incompleteness stated | PASS | 3-page fixture with page 3 failed: ocr.failed_pages={"3":"OCR_TIMEOUT"}, partial=true, codes=[OCR_READER, OCR_PARTIAL_PAGES]; Statement Check "Pages NOT read"=3 (OCR_TIMEOUT); Note: "Some pages could not be read. This workbook does NOT contain every transaction in the statement..." |
| shadow records block, job fails as before | **PARTIAL** | orchestrator-level (direct `process_statement` in-container): ocr block recorded in `statement_engine.ocr` (tier T4, OCR_READER, capped) while the job fails with the pre-existing legacy error (PDFIntegrityError "insufficient text content") — verified. **Via the real API the shadow job never starts**: analyze refuses scanned files when mode != serve (`_ocr_servable()` requires serve), so nothing reaches the orchestrator. See bugs F5. |
| service unreachable / fixture missing → OCR_* code, no silent T3 | PASS | no-fixture file → job failed `[ocr_reader] Scanned statement could not be read (OCR_NO_FIXTURE)`; mock dir missing → same OCR_NO_FIXTURE; analyze stayed UNKNOWN with manual bank pick |
| >20 MB rejected in analyze AND process paths | PASS | 36,375,058-byte scanned PDF: analyze → doc state ERROR "File is larger than 20 MB."; confirm → NOT_CONFIRMABLE; process → skipped NOT_PROCESSABLE |
| analysis-time OCR: capped at MEDIUM | PASS | scan_hdfc fixture (OCR text names HDFC): analyze detected hdfc, confidence=MEDIUM (capped), requires_confirmation=true, message "Probably HDFC Bank. Please confirm. This statement is a scan, so we will read it with OCR..." |
| weak match never verified / no text → manual pick | PASS | clean fixture (no real bank text): detected=None, state UNKNOWN, requires_confirmation=true — user picks the bank |
| OCR failure/timeout → manual pick | PASS | slow mock (8s > 5s budget): analyze returned in 7.6s, state UNKNOWN, detected=None, requires_confirmation=true |
| no OCR content in logs/audit | PASS | backend logs: 0 hits for narration/amount tokens; audit metadata = `to_block()` which carries only verdict/codes/pages/counts/timings/check-results (code-verified `ocr/reader.py:56`) |

## Part 3 — ocr-service container (build only)

| check | result | evidence |
|---|---|---|
| Build ocr-service/Dockerfile | **FAIL (environment)** | base image `ccr-2vdh3abv-pub.cnb.cool/paddlepaddle/paddleocr-vl:latest` unresolvable from this network (DNS failure). Build never reached the pip layer. |
| Dependency resolution | **PARTIAL / NOT RUN** | `paddleocr==3.7.0` wheel downloads fine (verified via `pip download` in-container). Full resolution of `paddleocr[doc-parser]==3.7.0` + paddlepaddle: NOT RUN — PyPI/files.pythonhosted.org connectivity from this network currently times out (host and container). |
| `tests/test_helpers.py` | **4/4 PASS** | run in-container (fastapi/uvicorn/pymupdf installed at runtime) |
| /health with models not loaded | **BUG (F3)** | startup event calls `MODELS.load()` unguarded; `import paddleocr` failure → "Application startup failed. Exiting." → /health never answers. Expected: stay up, report not-ready. |
| compose config (base + ocr override) | PASS | `docker compose config`: backend deploy=null (no GPU), ocr-service has no published ports (internal reach only), `STATEMENT_ENGINE_OCR_MODE` default `off`, GPU reservation only on ocr-service, single `airco-network` |

## Part 4 — Frontend (830d161)

| check | command | result | evidence |
|---|---|---|---|
| npm ci | `npm ci` | PASS | 603 packages |
| lint | `npm run lint` | **FAIL → fixed** | 2 errors (`react-hooks/set-state-in-effect`) in AnimatedNumber.tsx:26 + ProgressPanel.tsx:33 — fixed by cherry-picking `abfd5aa` from devin/r5-verify; lint now clean |
| build | `npm run build` | **FAIL → fixed** | `HelpCenter.tsx:7: Module not found: Can't resolve '@/hooks/useBankCatalog'` (hook lives at `app/hooks/useBankCatalog.ts`; `@` = frontend root). Fixed import to `@/app/hooks/useBankCatalog` (commit on this branch). Build now green (Next.js 16.4.2, tsc in build OK). |
| tsc | `npx tsc --noEmit` | PASS | clean |
| vitest | `npx vitest run` | PASS | 8 files, **69/69** (incl. lib/gamification tests) |
| browser walk | Playwright | PASS | login → dashboard → upload flow renders; accordions open; gamification panel shows |
| accordions closed-state not tabbable | PASS | aria-expanded=false, 0 tabbable elements inside both panels |
| keyboard focus visible | PASS | focused button outline: solid |
| responsive 375/768/1280 | PASS | no horizontal scroll at any width (scrollWidth == clientWidth) |
| prefers-reduced-motion | PASS | accordion open height 0→529 instantly (no tween); globals.css forces 0.001ms durations |
| console errors | PASS | none |
| screenshots | — | `tmp/r5b_screens/`: p4_dashboard_1440/375/768/1280.png, p4_guide_open.png, p4_limits_open.png (synthetic content only) |

## Part 5 — Security/compliance spot checks

| check | result | evidence |
|---|---|---|
| 7-day purge covers OCR/scanned jobs | PASS | `retention_purge._PURGE_ORDER` sweeps RawTransaction, JobEvent, ReportGenerationLog, DownloadLog, StatementMetadata, ProcessingJob, ApiRequestLog, ErrorLog by created_at; temp-dir staged uploads + generated reports purged (`purge_temp_dir`); S3 objects via file_history purge; expired analyses via Redis TTL. OCR jobs are ordinary ProcessingJobs → same path. Live dry-run log shows nonzero would_delete across tables. |
| OCR service: decrypted PDF over internal network only, nothing persisted | PASS (structural) | ocr-service publishes no ports (compose); `/v1/ocr` writes the body to a NamedTemporaryFile and `os.unlink`s it in `finally` (app.py:171-178); nothing else is written to disk. Real-service network behaviour NOT RUN (no GPU build). |
| diff grep for secrets/tokens/hardcoded URLs | PASS | no secret patterns (sk-/ghp_/AKIA/xox/PRIVATE KEY: 0 hits); URLs are localhost/test endpoints, the documented `http://ocr-service:8090` default and an env-example `http://vllm:8118/v1` |

## Bugs found

| id | severity | where | reproduction | proposed fix |
|---|---|---|---|---|
| F1 | major (build blocker) | `frontend/app/components/experience/HelpCenter.tsx:7` | `npm run build` on 830d161: Module not found `@/hooks/useBankCatalog` | import from `@/app/hooks/useBankCatalog` — **applied** (frontend fix, disclosed) |
| F2 | minor (lint) | `AnimatedNumber.tsx:26`, `ProgressPanel.tsx:33` | `npm run lint`: 2 × react-hooks/set-state-in-effect | derive during render / event-driven state — **applied** via cherry-pick `abfd5aa` |
| F3 | major (for GPU rollout) | `ocr-service/app.py:158-160` (startup event → `MODELS.load()`) | start service without paddleocr installed → "Application startup failed. Exiting." → /health unreachable | wrap `MODELS.load()` in try/except; on failure keep serving `/health` with `status:"loading"` (or "error") + a `load_error` field; retry/backoff. NOT applied (service code — Claude's call) |
| F4 | minor (infra) | `backend/Dockerfile` build context | in-image pytest cannot collect test_n1/n2/n3/test_universal (needs repo-root `tools/onboarding/synth`) and lacks `reportlab` | copy `tools/` into the image or move `synth` under `backend/tests`; add test extras to a requirements-dev. NOT applied |
| F5 | minor (design) | `analysis_service.py:76-81` (`_ocr_servable` requires mode==serve) | with OCR_MODE=shadow, analyze refuses scanned files → the orchestrator's shadow block-recording is unreachable via the API (verified: confirm → NOT_CONFIRMABLE) | if shadow should observe real traffic, let analyze run the detection probe in shadow too (record-only). NOT applied (policy) |
| F6 | info | `serve.py` SERVE_TIMEOUT_S=30 vs 100+ page files | a 123-page Federal file takes ~25s single-request; under concurrency it can exceed 30s (observed as route timeouts during parallel measurement) | consider per-page-budget or raising the timeout for large files. NOT applied |

## Prompt-vs-build mismatches

- The prompt expects "the 14 sheets plus the Statement Check sheet" — this build's workbook has **10 sheets total** (9 + Statement Check). The Statement Check OCR section requirements all pass. (Sheet count is generator-defined; no OCR-specific sheet is missing.)

## NOT RUN (with reasons)

- Real ocr-service image build + model run: vendor base registry unreachable from this network; no GPU per rules. Accuracy/speed targets (>=99.5% amounts, <=0.1% side flips, p95 <= 4 s/page) **NOT VERIFIED — no real model was run**; all OCR evidence is synthetic-fixture based.
- Full pip dependency resolution for ocr-service: PyPI connectivity from this network timed out during the session.
- Real scanned-statement e2e (corpus has no image-only bank statements; OCR forbidden on corpus files by the task rules).
- Upside-down/orientation-classification behaviour (needs the real service).

## Verdict

**OCR T4 (486fb9c): no regressions, honest failure modes verified end-to-end in mock mode — ready for the GPU-host phase behind the flag (off by default).**
**Frontend (830d161): NOT mergeable as-is** — the HelpCenter import breaks `next build` (fix applied on this branch; the same fix exists on `devin/r5-verify` as `abfd5aa`).

---

## Addendum — real GPU run on this machine (RTX 3060 12GB, driver 13.3/CUDA-13 UMD)

The committed Dockerfile could not build here (vendor registry DNS-unreachable), so a variant was
built per the Dockerfile's own "replace BASE" note: `nvidia/cuda:12.6.2-runtime-ubuntu22.04` +
`paddlepaddle-gpu==3.3.1` (official cu126 index) + `paddleocr[doc-parser]==3.7.0` + pymupdf/fastapi/uvicorn
(`ocr-service/Dockerfile.gpu-test`, harness only). PyPI was throttled from this network; the Tsinghua
mirror unblocked the build. Image builds PASS (~2GB paddle wheel + ~1GB CUDA deps).

| step | result |
|---|---|
| service start (unpatched app.py) | **CRASH — first error line**: `ImportError: libgomp.so.1: cannot open shared object file` (missing OS lib in the CUDA base; fixed in the variant by adding `libgomp1`) followed by `ERROR: Application startup failed. Exiting.` — live confirmation of F3's failure mode (unguarded startup; /health unreachable) |
| service start (with libgomp1) | PASS — models auto-download (PP-LCNet doc-ori, UVDoc, PP-DocLayoutV3, PaddleOCR-VL-1.6, PP-OCRv6 det/rec), `/health` → `{"status":"ok","engine":"PaddleOCR-VL-1.6","verifier":"PP-OCRv5"}`, **5.0 GB VRAM** resident |
| POST /v1/ocr (unpatched) | **422 on EVERY call — new bug F7 (critical)**: `{"detail":[{"type":"missing","loc":["query","request"],"msg":"Field required"}]}` — `app.py` has `from __future__ import annotations` while `Request` is imported only INSIDE `create_app()`; FastAPI resolves the string annotation against module globals, fails, and demotes `request: Request` to a required query param. The service's only endpoint can never serve. Reproduced with TestClient. Fix: move `from fastapi import Request` to module level (verified: endpoint then resolves; 422 → normal handling). NOT applied to the repo (Claude's file). |
| real OCR call (runtime-patched copy, harness only) | PASS — blank-page PDF: 200, 0 blocks (correct); statement-image PDF: 200 in 40.6s — page 2 ok (7 blocks incl. the full table HTML + 72 verifier lines, 17.2s), **page 1 failed OCR_TIMEOUT at 23.2s** (default 20s page budget; cold first pass) |
| real OCR doc → backend engine | honest refusal: `LOW_CONFIDENCE_COLUMNS` (direct `infer()` on the same pages: `NO_DATED_ROWS — fewer than 4 dated lines on first page`) — the failed page 1 (0 words) breaks the reader's first-page column inference; the VLM also prints dates without leading zeros (`3/04/2026`). No garbage served. **First real integration gap for the GPU phase.** |

Measured (single RTX 3060, 2-page synthetic): ~17-23 s/page — the p95 <= 4 s/page target is NOT met on
this hardware; page-1 cold passes exceed the default 20 s `OCR_PAGE_TIMEOUT_S`. Accuracy targets still
NOT verified (no ground-truth comparison run).

GPU-run checklist for the first real deployment (from this run): add `libgomp1` (or use a base that has
it), move the `Request` import to module level (F7), expect ~20 s/page on consumer GPUs and size
`OCR_PAGE_TIMEOUT_S` accordingly, and expect the universal reader to refuse when page 1 fails OCR
(needs a partial-tolerant inference path or a page-1 retry).
