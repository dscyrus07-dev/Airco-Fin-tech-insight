# R11 — verify the unbuilt UI + first real OCR measurement

Branch `devin/r11-verify` @ a3e7ac0. All data synthetic (`tools/ocr_eval/corpus.py`,
geometry-asserted at build). No real statements touched. Nothing pushed.

**FRONTEND BUILDS CLEAN — 0 fixes needed. Served: blocks 27/27, lines 21/27, lines+SKIP_VL 21/27
(×3 runs each, identical). Zero side flips anywhere. This is the first accuracy measurement that
means anything — every prior number was taken against a corpus no human could read.**

## Part 0 — housekeeping

| check | result |
|---|---|
| delete broken `frontend/node_modules` (~400 pkgs, empty `.bin`) | done |
| `npm ci` | 1,264 packages, clean |

## Part 1 — the unverified frontend commit, verified

| check | command | result |
|---|---|---|
| lint | `npm run lint` | **PASS** — 0 errors, 0 warnings |
| types | `npx tsc --noEmit` | **PASS** — 0 errors |
| unit | `npm test` (vitest) | **PASS — 76/76**, incl. all 7 new a3e7ac0 tests ("never labels a scanned statement as verified" passes) |
| build | `npm run build` | **PASS** — Next 16.4.2, 19 routes prerendered |
| existing v2/legacy snapshots | vitest | unchanged paths still pass |

**Fixes I made to a3e7ac0: none.** It compiled, linted, typed and tested clean as written.

## Part 2 — the headline: OCR re-measured on a readable corpus

Corpus `tmp/r11_corpus` — 27 statements (9 categories × 3), `check_header_geometry` passed.
Eyeball check on rendered crops: money titles sit over their own columns on both layouts
(`docs/ocr/eval/r11/split_clean_200_00_p1.png`, `signed_clean_200_01_p1.png`).

Same corpus, same service, 3× per configuration:

| config | served | exact amounts | side flips | invented (chain-pass) | chain+ref pass | p95 s/page |
|---|---|---|---|---|---|---|
| blocks (VLM markup) run 1/2/3 | **27/27** each | 100.00% | 0 | 0 | 100% | 6.3–6.9 |
| lines (PP-OCRv5) run 1/2/3 | **21/27** each | 100.00% | 0 | 0 | 100% | 6.2–12.9 |
| lines + `OCR_SKIP_VL=1` run 1/2/3 | **21/27** each | 100.00% | 0 | 0 | 100% | **0.84–1.53** |

Zero run-to-run variation in serving or accuracy — only p95 jitter (jpeg/low_contrast 12.5s in
lines run 2, VL contention).

### Not served (identical every run)

| id | code | dropped | header titles |
|---|---|---|---|
| skew_00/01/02 | `LOW_CONFIDENCE_COLUMNS` | 0 | - |
| rotated_180_00/01/02 | `NO_DATES` | 0 | - |

- **rotated_180 fails on lines, serves on blocks.** The VLM markup path reads rotated pages fine;
  PP-OCRv5 produces garbage token boxes without the orientation classifier — same R9 finding,
  still honest refusal (NOT misreads).
- **skew refuses on both lines configs** at column-confidence gate — the recogniser reads the
  words but cannot place them in columns reliably; engine refuses rather than guesses.

### Gates (per category, per config)

- blocks + lines(+VL): `exact_amounts`, `side_flips`, `invented_in_chain_passing`, `chain_and_reference_pass_rate` **all PASS**; `p95_seconds_per_page` **FAIL everywhere** (~6–12s vs 4.0).
- lines + `OCR_SKIP_VL=1`: **all gates PASS** on all 7 served categories incl. p95; rotated_180/skew FAIL `exact_amounts` only because nothing was served (correct no-data fail — not misreads).

### Hand-verify (independent comparator, not the harness scorer)

5 served statements per config, every debit/credit/balance row-matched to `manifest.json`:

| config | statements | rows | mismatches | side flips |
|---|---|---|---|---|
| blocks | clean_200_00, blur_01, jpeg_02, dpi_150_00, rotated_180_01 | 200 | **0** | **0** |
| lines+VL | clean_200_02, dpi_150_01, blur_02, jpeg_00, noise_02 | 200 | **0** | **0** |
| lines+novl | clean_200_01, dpi_300_00, blur_00, low_contrast_02, noise_00 | 200 | **0** | **0** |

Reports: `docs/ocr/eval/r11/*.md|json`. Verifier script: `tmp/r11_verify_sides.py`.

**Read of the result:** on geometry-correct synthetic input, both layers are perfect on every
degradation except rotation/skew for PP-OCRv5 — and those refuse honestly rather than misread.
`OCR_SKIP_VL=1` is now the interesting tier: identical served set at ~7× speed, but note the VL is
the second-reader verifier — SKIP_VL trades the cross-check for latency. Still synthetic-only;
real scans NOT run; REVIEW cap stands.

## Part 3 — B4/B6 infrastructure fixes (`backend/app/services/message_queue.py`)

- **B4 consumer reconnect**: fresh asyncio event loop per cycle + bounded exponential backoff with
  jitter (`retry_in_s` logged per attempt, `max_retries` bound). Proven: RabbitMQ killed mid-run →
  `attempt 1 retry_in_s=6.4` → `10.4` → `21.4` → **reconnected and resumed consuming**. R10's
  post-`docker pause` connect/shutdown spin is gone.
- **B6 DLQ bound**: `dead_letter_queue` declared durable + `x-max-length=10000` +
  `x-message-ttl=604800000` (7d, matches the retention promise). Dead-letter publishes preserve
  headers, add truncated `x-death-reason`, persistent delivery, and log `dlq_depth`.
  Proof: poison payload consumed 3× then dead-lettered, `dlq_depth:1` logged; `rabbitmqctl
  list_queues` shows both args set. When the DLQ fills, RabbitMQ dead-letter-drops oldest
  (queue-length overflow) — poison evidence ages out instead of growing unbounded.

## Part 4 — copy and the spec question

- **B7 20 MB wording**: `upload.py` and `upload_async.py` now emit `"File is larger than 20 MB."`
  — identical to `analysis_service.py` (untouched, Claude's file). All three doors say the same thing.
- **B8 HelpCenter "scans cannot be read"**: left as-is per instructions — accurate for what a user
  can do today; pending until OCR serves real statements.
- **B9 sheets/formulas** (investigated, not "fixed"):
  - Workbook has **9 sheets always** (`lite_excel_generator.py` sheet order, unchanged since the
    initial commit) + a 10th `Statement Check` appended for engine-produced results. Nothing in
    repo history ever emitted 14.
  - **Zero formula cells ever**: `lite_excel_generator` writes only materialized values
    (0 `=`-formula writes); `formula_excel_engine.py` is a vestigial name — a thin wrapper that
    calls the same Lite generator ("Phase 5" consolidation per its docstring). A client opening
    the workbook gets correct static values; editing a cell recalculates nothing. Product question.

## Part 5 — the UI, end to end (mock path, real API + real UI)

Stack `-p devin_r11`: postgres/redis/rabbitmq/fakes3/keycloak/auth-service/backend(mock fixtures,
patched files mounted)/frontend(r11 image, Keycloak 8180 baked). Walked with Playwright:
details → bank pick → upload `partial_tail_5p.pdf` (5p, page 5 unread) → mode → processing → report.

Result screen shows, all confirmed in DOM + screenshot (`tmp/r11-product/shots/10_result_full.png`):

- ⚠ **`Categorization Complete — Partial`** heading (amber icon, not green check)
- amber banner: "**This report is incomplete.** Page 5 could not be read — transactions from those
  pages are NOT in this report. The figures were read from an image… see the Statement Check sheet"
- amber badge: "**Scanned · incomplete · needs review** · Page 5 could not be read…"
- "88 transactions" + "**100% categorized of rows read**" (qualified)
- "The independent check flagged points to review" strip
- 9-sheet list, Download Excel/JSON — **no "VERIFIED" or unqualified "complete" anywhere**

a3e7ac0's disclosure works end-to-end on the real product path. No defects found in the result
surface this round.

## Changes made on `devin/r11-verify`

| file | change | why |
|---|---|---|
| `backend/app/services/message_queue.py` | backoff reconnect loop, bounded retries, DLQ `x-max-length`/`x-message-ttl`, `dlq_depth` logging | B4/B6 |
| `backend/app/api/routes/upload.py` | size msg → "File is larger than 20 MB." | B7 |
| `backend/app/api/routes/upload_async.py` | same | B7 |
| `docs/ocr/eval/r11/` | 9 run reports + json + geometry crops | P2.8 |

No `a3e7ac0` fixes needed — zero compile/lint/type/test errors.

## What remains unverified

- **Real scanned statements were NOT run** — every number above is synthetic-corpus only.
  27/27 does not lift the REVIEW cap and does not establish production accuracy.
- rotated_180/skew on the lines layer: refuses honestly; no fix attempted (service-side knob
  `use_doc_orientation_classify` flagged in R9, unchanged).
- `OCR_SKIP_VL` removes the second-reader cross-check; the gate numbers look identical but the
  verification guarantee is weaker — flagged, defaults unchanged.
- auth-service reported Docker-unhealthy in the isolated stack while Uvicorn ran (same as R10);
  UI flow unaffected via direct Keycloak. Not investigated.
- p95 gate fails on both VL configs (~6–12s/page). If VL verify stays required for serving,
  latency on real docs is a product-level question, not a correctness one.

## Teardown

`devin_r11` compose stack + `r11_ocr`/`r11_vllm`/`r11_mqtest`/`r11_rmq` removed, `devin_r11_ocr`
network removed, VRAM 860 MiB (baseline). `tmp/r11*` artifacts retained locally for evidence.
