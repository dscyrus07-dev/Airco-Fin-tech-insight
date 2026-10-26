# R12 — Live rebuild on :3000 with OCR on

**The app is LIVE on http://localhost:3000 with OCR ON (serve mode, vLLM-backed PaddleOCR-VL).**
**Frontend gate: PASS — lint 0 errors, tsc 0 errors, vitest 84/84, `next build` clean; zero fixes needed.**
**User's synthetic test files: `C:\Users\admin\Desktop\scanned-statement-tests\` (9 category dirs + `manifest.json`).**

Built from `devin/r12-live` @ `c60cf90` in the separate worktree `X:\Airco Projects\wt-r5`.
The user's checkout (`X:\Airco Projects\Airco Insights fintech`) was never touched. Nothing was pushed.
Keycloak was never restarted, reconfigured, or recreated; no volume or data was deleted.

---

## Step 1 — frontend gate (PASS)

| Check | Command | Result |
|---|---|---|
| install | `npm ci` | clean (1,264 packages) |
| lint | `npm run lint` | 0 errors |
| type-check | `tsc` | 0 errors |
| unit tests | `npm test` (vitest) | **84/84 pass**, 9 files — incl. all 8 new (4 `ReviewTable.test.tsx`, 4 `ocrCatalog.test.ts`) |
| production build | `next build` | compiled, no errors |

No fixes were required; `c60cf90` compiled as written.

## Step 2 — backend and service tests, in Docker, no stubs (PASS)

The production backend image ships no pytest; pytest 9.1.1 + reportlab were vendored from the
host (pure-Python wheels) into a throwaway container on the live image — no image change.

| Suite | Result |
|---|---|
| `backend/tests/statement_engine` (+ tools mount) | **578/578 pass** |
| `backend/tests/test_analysis_service.py` | **26/26 pass** — loads and passes in full, no stub |
| `ocr-service/tests` | **9/9 pass** |

One stale test fixed (test-only): `test_helpers.py` asserted the `/v1/ocr` handler signature
before `e2b26a1` added the `vl` param — the assertion now allows `vl`. No behaviour change.

## Step 3 — configure and rebuild (PASS)

Runtime configuration actually in effect:

| Component | Setting |
|---|---|
| backend | `STATEMENT_ENGINE_OCR_MODE=serve`, `STATEMENT_ENGINE_OCR_URL=http://ocr-service:8090`, `STATEMENT_ENGINE_OCR_TEXT_LAYER` unset (default thorough), `STATEMENT_ENGINE_V2_MODE=serve` (allowlist already in `infra/docker/.env`: 29 keys) |
| ocr-service | `OCR_VL_SERVER_URL=http://ocr-vllm-server:8080/v1`, `OCR_DPI=200` |
| ocr-vllm-server | `vllm/vllm-openai:v0.32.0`, `OCR_VL_MAX_NEW_TOKENS=2048`, gpu-mem-util 0.45, max-model-len 16384; `OCR_SKIP_VL` **not set** |
| frontend | rebuilt `airco-frontend:r12` with `NEXT_PUBLIC_UNIFIED_ENTRY=1` and `NEXT_PUBLIC_KEYCLOAK_URL=http://localhost:8095` (see Keycloak note) |

`GET /api/statements/banks` (authenticated, via the real UI session) returns exactly:

```json
"ocr": {"enabled": true, "reading_modes": ["thorough","fast"], "default_reading": "thorough", "max_pages": 60}
```

With `V2_MODE=serve` the same endpoint now reports the full taxonomy (was 13 legacy /
26 coming soon under `off`): **verified 23, review_required 5, legacy 2
(Bank of India, Union Bank of India), coming_soon 9, unsupported 5** — exactly the
product list. `standard_chartered` is in the allowlist but has no `scb` spec key, so it
correctly stays in coming_soon. The bank-support panel renders all five groups from the
catalog plus a separate **"Universal OCR parser (any scanned statement)"** section
(60-page limit, always needs review) — OCR is never counted as a bank.

Time-to-ready: backend recreate ~15 s to `/health` 200; ocr-service cold start ~70 s
(worker loads PP-OCRv5 + layout models, connects to vLLM, `warmup:"ok"`); vLLM server
several minutes on first start (model load), already warm in this stack.
VRAM while idle with both models loaded: **9,182 MiB / 12,288 MiB**.

## Step 4 — real-model verification (PASS)

2-page synthetic scan POSTed to `ocr-service` inside the app network:

| Mode | Engine | Verifier | Blocks | Lines | Time | s/page |
|---|---|---|---|---|---|---|
| `vl=1` (Thorough) | PaddleOCR-VL-1.6 | PP-OCRv5 | 6 | 217 | 19.6 s | ~9.8 |
| `vl=0` (Fast) | PP-OCRv5 | **"" (empty)** | **0** | 217 | 1.7 s | ~0.8 |

`vl=0` contract confirmed on real models: no blocks, lines only, engine PP-OCRv5, empty verifier.

**Analysis-time bank detection** (real `/api/statements/analyze`, same 2-page scan): **4.03 s —
inside the 5 s budget** (previously ~7.6 s). Bank = `UNKNOWN` → user confirmation still
required, exactly as designed (the UI said so and offered the manual bank pick).

## Step 5 — the user's journey, real UI, Playwright (PASS)

All four journeys driven end-to-end through `http://localhost:3000` (login → upload →
review → process → report). Screenshots in `tmp/r12/shots/` (review choice `*_02_review*`,
reading pick `*_03_reading*`, result `*_10_result*`); workbooks saved alongside.

| Journey | Review screen | Result |
|---|---|---|
| `clean_200` + **Thorough** | amber "Scanned statement: read with OCR", Thorough (default) selected | `Scanned · needs review`, 40 txns, workbook `Second-reader amount check \| ran`, `Read with PaddleOCR-VL-1.6 + PP-OCRv5`, `80 / 0 / 0` confirmed/low-conf/not-confirmed |
| `clean_200` + **Fast** | radio flipped to Fast | `Scanned · needs review`, 40 txns, workbook `Second-reader amount check \| not_run`, `Read with PP-OCRv5`, review reasons include `OCR_VERIFIER_NOT_RUN` — never claims confirmation |
| `rotated_180` + **Fast** | radio flipped to Fast | **Honest refusal**: `Some statements could not be processed: rotated_180_00.pdf — [ocr_reader] Scanned statement could not be read (NO_DATES)`. No fabricated report, no download |
| `rotated_180` + **Thorough** | default | `Scanned · needs review`, 40 txns — the VL reader handled the rotation Fast refused |

Every result workbook contains the **Statement Check** sheet (Engine `ocr`, Verdict
`REVIEW`, "This result is never marked as verified."). No screen ever showed a VERIFIED
badge for a scanned file. The only "Verified" string on the dashboard is the
support-catalog label "0 Verified engine" — a bank-support count, not a result badge.

**Text-PDF regression (PASS):** `demo_hdfc.pdf` (text layer) → review screen shows the
detected bank card, **no reading choice** (zero `ocr-reading-*` radios) → Confirm →
`Categorization Complete`, 12 txns, standard 9-sheet workbook (no Statement Check sheet —
identical to pre-OCR behaviour for the legacy path). Re-verified after `V2_MODE=serve`:
HDFC now routes through the v2 engine and still completes normally — detected "very high",
12 txns, 100% categorized, workbook downloads.

**HelpCenter (PASS):** "Good to know" now reads *"Scanned statements are read with OCR
(up to 60 pages). Figures read from an image can be misread, so these results are always
marked 'needs review'; check them against the statement."* and the tip reads *"Scanned
statements can be read too: they take longer and are always marked for review."* — copy
follows `catalog.ocr.enabled` as designed.

## Step 6 — auth-service (NO ISSUE)

`airco_auth_service` is **healthy** in the live stack (47 h uptime, healthcheck passing).
The R10/R11 "unhealthy" observation was in an isolated test stack; here it does not affect
login — login works end-to-end through `localhost:3000`.

## Keycloak host-port workaround (important for the user)

Docker Desktop's host-side port proxies for `:8080` (Keycloak) and `:80` (nginx) are
**wedged** — the containers are healthy and reachable inside the Docker network (verified
from the backend), but no host connection gets through. `:3000` and `:8000` (v4) work.

**Keycloak was NOT restarted or reconfigured.** Instead a temporary relay container
(`airco_kc_relay`, `nginx:alpine`) was added on the app network publishing
`127.0.0.1:8095 → keycloak:8080`. The frontend was rebuilt with
`NEXT_PUBLIC_KEYCLOAK_URL=http://localhost:8095`. Keycloak's pinned hostname keeps token
`iss=http://localhost:8080/realms/airco-insights`, so backend JWT validation needed **no
env change** — issuer and audience still match the original configuration.

Side effects to know:
- Login redirects go to `:8095` and return cleanly; sessions are normal.
- If Docker Desktop self-heals `:8080`, the relay can simply be removed and the frontend
  rebuilt with `NEXT_PUBLIC_KEYCLOAK_URL=http://localhost:8080`.
- `localhost:8000` still has a dead `wslrelay` listener on `::1` (IPv6). It does not affect
  the app: all browser calls go through same-origin `/api/*` route handlers inside the
  frontend container, which reach `backend:8000` over the Docker network. Direct
  `curl http://localhost:8000` from the host is flaky — use `http://127.0.0.1:8000`.

**Cookie/header fix applied after the first report:** browsers share cookies across every
`localhost:*` port, so a long-lived dev browser can exceed nginx's default 8 KB request
header limit (`400 Request Header Or Cookie Too Large`) and Node's ~16 KB limit (`431`).
Fixed in both places: `large_client_header_buffers 4 32k` on the relay
(`tmp/r12/kc_relay.conf`, bind-mounted) and `NODE_OPTIONS=--max-http-header-size=32768`
on `airco_frontend`. Verified end-to-end with ~20 KB of cookies: `:3000` → relay →
dashboard. Note `proxy_buffer_size` must NOT be raised while `proxy_buffering off` is set —
nginx 1.31.6 treats the single buffer as the whole pool and fails config validation.

**Docker Desktop restarted (user-approved):** the wedged `:8080` and `:80` port-proxies
healed — Keycloak is now reachable natively at `http://localhost:8080` (admin console
included; its clients whitelist `:8080` redirect URIs). The `airco_kc_relay` on `:8095`
is kept running: the frontend still targets it, so app login survives even if the
`:8080` proxy decays again. Post-restart verified: all 11 containers healthy
(`airco_nginx` healthy for the first time — needed the `frontend` network alias on the
hand-run frontend container), `vl=1`/`vl=0` results identical to pre-restart
(6 blocks/217 lines; 0 blocks/217 lines), `:3000` login → dashboard works.

## Changes made this round (all committed on `devin/r12-live`)

| File | Change | Reason |
|---|---|---|
| `infra/docker/docker-compose.ocr.yml` | healthcheck `python` → `python3` | image ships only `python3`; container was permanently "unhealthy" despite serving fine — now `healthy` |
| `ocr-service/tests/test_helpers.py` | allow `vl` in handler signature assertion | stale test, `vl` added by `e2b26a1` |
| `backend/app/services/message_queue.py` | probe DLQ args on a side channel; fall back to a passive declare with one warning when the existing queue is unbounded | the live `dead_letter_queue` already exists unbounded; queue args are immutable, so a bounded redeclare raised 406 and spun the consumer forever. Now: consumes fine, logs once, queue stays unbounded until an admin deletes+recreates it |
| frontend image | rebuilt with `NEXT_PUBLIC_UNIFIED_ENTRY=1` + relay URL | build args only; the unified upload→review flow (where the reading choice lives) is behind this flag, default off |

No engine files touched. No secrets changed or printed.

## How to switch OCR off again

In the backend environment (`.env` used by compose, or `-e` flags):

```
STATEMENT_ENGINE_OCR_MODE=off
```

then recreate only the app services:

```
cd infra/docker
docker compose -p airco -f docker-compose.yml -f docker-compose.local.yml up -d --no-deps backend frontend
docker stop airco-ocr-service-1 ocr_vllm_server   # optional: frees ~9 GiB VRAM
```

The catalog then reports `"ocr": {"enabled": false, …}` and the UI hides the reading
choice and reverts to the "scans cannot be read" copy automatically.

## Rollback (pre-R12 image IDs recorded before rebuild)

| Container | Previous image ID | Current image |
|---|---|---|
| `airco_backend` | `cf6d9762125c` | `airco-backend` (`d95074448571`) |
| `airco_frontend` | `5a5aaad5be18` | `airco-frontend:r12` (`c4a9a22530d4`) |
| `airco_auth_service` | `f446c4287f8c` (unchanged) | `f446c4287f8c` |
| `airco_nginx` | `df221db836e1` (unchanged) | `df221db836e1` |
| `airco_rabbitmq` | `606d8c0d6b3c` (unchanged) | `rabbitmq:3-management-alpine` |
| `airco_redis` | `858f009f9709` (unchanged) | `redis:7-alpine` |

New containers added by this round (remove to roll back): `airco-ocr-service-1`,
`ocr_vllm_server`, `airco_kc_relay`.

To restore a previous image: `docker rm -f airco_backend` then `docker run` /
`compose up` pointing at the recorded image ID, or `docker tag <id> airco-backend` first.

## User test checklist

| File (in `C:\Users\admin\Desktop\scanned-statement-tests\`) | Pick | You should see |
|---|---|---|
| `clean_200\clean_200_00.pdf` | **Thorough** (default) | Amber "Scanned statement: read with OCR" box on the review screen → bank UNKNOWN, pick any bank (e.g. HDFC) → ~1–2 min → `Scanned · needs review`, workbook says second-reader check `ran` |
| same | **Fast** | Same box, flip to Fast → much faster result → `Scanned · needs review`, workbook says second-reader check `not_run` |
| `rotated_180\rotated_180_00.pdf` | **Fast** | Honest failure: "could not be read (NO_DATES)" — no fake report |
| same | **Thorough** | Reads successfully, `Scanned · needs review` |
| any text PDF (e.g. an original bank download) | — (no choice shown) | Detected-bank card, normal Verified-style completion |
| `blur`, `noise`, `low_contrast`, `dpi_150`, `dpi_300`, `jpeg`, `skew` | either | Synthetic stress cases — skew may refuse on Fast; none are real statements |

## What remains unverified

- The 4.03 s analysis figure is for a 2-page clean synthetic; larger/real scans will differ.
- `warmup:"ok"` reflects the synthetic probe only.
- `airco_nginx` shows `(unhealthy)` — pre-existing state (47 h), not caused by this round,
  not investigated since nothing on `:80` is part of the live path.
- The old wizard path (without `NEXT_PUBLIC_UNIFIED_ENTRY`) still works — verified earlier
  this session before the flag flip — but the reading choice only exists on the unified flow.
- Retention/deletion sweeps were not re-verified this round (R10/R11 evidence stands).

---

# R12 continuation — Universal OCR on real scanned statements

The user's two real scanned PDFs exposed the actual gaps. All fixes below are
bank-agnostic: the Universal Reader never sees bank-specific code.

## What was broken (real files)

| File | Symptom | Root cause |
|---|---|---|
| `987396_…pdf` (38-page HSBC scan) | `NO_DATES`, then `CHECKS_FAILED` (missing balances, footer text inside narrations) | Dates like `27Apr2022` (fused month name, no separator) were not a known shape; OCR also splits each transaction across 2–3 visual lines and ends pages on `Balance Carried Forward` + legal footer, which the row assembler misread as narration/rows |
| `1855601_…pdf` | UNKNOWN bank, empty evidence, forced manual bank pick | Scanned OCR evidence is inherently weak; the workflow hard-blocked on `bank.supported` even though Universal OCR needs no bank |

## Fixes (all in the generic engine/reader — no bank code)

- **`universal/lexicon.py`** — new date shapes `dmony_compact` (`27Apr2022`),
  `dmony_slash`, `dmy_dot2`, `ymd_slash`; `dmony_spc` now covers fused/spaced variants
  incl. 2-digit years. `AMOUNT_RE`/`PLAIN_AMOUNT_RE` tightened: bare integers capped at
  9 digits and comma groups required, so 10–16-digit UPI RRNs and account numbers in
  narrations can no longer be misread as amounts.
- **`universal/infer.py`** — date shape detection scans first 4 pages (individually then
  combined) instead of page 1 only. New margin-check retry: when dated lines rarely
  carry a balance (multi-line transactions), re-verify with
  `continuation_amounts + undated_rows_inherit_date` against the printed balance chain.
  `carry_forward_re` added to the inferred spec.
- **`extraction/rows.py`** — page-boundary rules: an open row (amounts still pending)
  survives `Balance Carried Forward` and is filled by the continuation line on the next
  page; `Carried Forward` breaks the page's table scan (footer text below it is dropped);
  `Brought Forward` seeds a balance checkpoint without truncating the page; an undated
  balance-bearing line is only treated as a new inherited-date row when the open row
  already has its balance.
- **`ocr/grid.py`** — `page_text` for the line layer groups OCR boxes into visual lines,
  so analysis-time bank detection sees real table rows. `_AMOUNT` tightened the same way.
- **`ocr/reader.py`** — `BLOCKS_FALLBACK`: when thorough-mode VL markup fails inference
  (`NO_DATES`/`NO_TABLE_HEADER`/…), retry on the coordinate-true PP-OCRv5 line boxes from
  the same OCR pass; adopted only if full inference+reconciliation passes (audited via
  `layer_note`).
- **`analysis_service.py` / `statements_analyze.py` / `ReviewTable.tsx`** — scanned docs
  may confirm with no identified bank (falls back to suggestion or `other`); the catalog
  gains `Other bank / Universal OCR` whenever universal serve or OCR is enabled; for
  scans the UI defaults to the `Universal OCR Parser (Any Bank / Format)` entry, demotes
  every bank to at most `review_required`, auto-opens evidence, and never offers a
  verified claim.

## Real-file outcomes (live stack, `airco_backend`)

| File | Reading | Result |
|---|---|---|
| `987396_…pdf` 38p | **Fast** | `success` — 255 txns, 98.8 % coverage, `REVIEW` (pre-cap `VERIFIED`), all 38 pages read, 10-sheet workbook with `Statement Check` (`Second-reader amount check: not_run`, never-verified note) |
| `1855601_…pdf` | **Fast** | `success` — 19 txns, 100 % coverage, `REVIEW` |
| `987396_…pdf` 38p | **Thorough** | `success` — 255 txns, 98.8 % coverage, `REVIEW`; VL markup failed reconciliation, so the reader adopted the PP-OCRv5 line layer (`layer_note: BLOCKS_FALLBACK:CHECKS_FAILED`, verifier `not_run`) — the fallback only engages after the lines pass full inference + checks |

## Regression

- `tests/statement_engine/` — **582 passed** incl. new tests:
  `test_open_row_survives_carried_forward_and_fills_on_next_page`,
  `test_brought_forward_line_does_not_truncate_the_page`,
  `test_fused_month_name_dates_infer`,
  `test_multiline_rows_amounts_on_wrap_line_infer`.
- Frontend: 84/84 vitest, `tsc` clean.
- HDFC text PDF under `V2_MODE=serve` still reads (no legacy regression).
