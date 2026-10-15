# Night Summary — N1–N9 consolidated results

All work local-only, nothing pushed. Branches: `devin/n*` off
`integration/v2-waves` (tip `5be615d`). Final integrated state lives on
`devin/n9-final` (`bedc4bf` + DONE marker `5c35947`).

## Phase results

| # | Scope | DONE sha | Headline result |
|---|---|---|---|
| N1 | Dr./Cr. side markers, multi-line headers, untitled date column | `8e75997` | All four capabilities landed; IDBI L3, YES L5, CBI L4, PNB L2/L3 registered **shadow-only**; regression 734 files / **0 diffs**; 32-file audit clean; cross-bank 0 |
| N2 | Balance-less tables, per-account sub-tables, mid-doc summaries | `f8828a0` | `no_running_balance`, segments, document anchor scan, checkpoint/inline/sparse balances; DBS L3, IDBI L6, DHANLAXMI L2, HSBC L2 registered **shadow-only**; regression 734/4 diffs = BoM upgrades only (audit-clean); parked: hsbc undated sub-rows, equitas interleaved-wrap |
| N3 | Date-as-section-heading layouts (Federal family) | `13c2dd7` | section-date row grouping + derive-side-from-balance + 8 spec fixes; FEDERAL L4/L5 registered; **federal 130→228 VERIFIED** (fallback 113→15); audit 98 chain-clean; regression 734/1 diff (legit own-IFSC rescue) |
| N4 | Adversarial audit of N1–N3 | `5f6c237` | **Every capability ACCEPT**, zero reverts needed (no `n4-revert-*` branches created) |
| N5 | Re-measure ~20 banks on new abilities, largest first | `37f970f` | 12 STEP commits; 1,099-file regression vs N3 — one named BoM change (`6f562db1` REVIEW→VERIFIED, re-audited clean); 502 tests; **0 cross-bank false accepts**; verdicts: 3 ready-candidates (au_sfb, bom, airtel_pb already served), rest shadow_only/review_only |
| N6 | Legacy vs v2 head-to-head, 8 legacy banks | `475479f` | **SERVE_V2_WITH_LEGACY_FALLBACK**: bob, canara, icici, indian_bank, karnataka, kotak · **KEEP_LEGACY**: bank_of_india, union · `v2_worse=0` on all banks · BoI L2 spec built; regression 15 named diffs |
| N8 | Retention, robustness, API security, secrets, hygiene | `760b563` | Found the release-blocking defects (see below); analyze timeouts NOT reproduced; ~35.7 GB reclaimed; secrets purge rehearsed on a copy (355 commits, 0 residue) |
| N7 | Integrate + rebuild onb + verify candidates | `fd1b800` | N5+N6+N8 merged (4 conflicts, all documented); **6/6 GO**: bob, canara, icici, indian_bank, karnataka, kotak; 36 e2e serve jobs 0 flags; mutation 24/24; confusion 0; onb restored to default; shipped `bank_status.json` byte-identical |
| N9 | Final cross-check, validation, workflow, cleanup, live rc | `bedc4bf` | rc stack live; **RELEASE: GO WITH CAVEATS**; details below |

## Final verified state (N9 measurements)

- **rc stack live**: `http://localhost:3600` (frontend) + `http://localhost:8601` (backend), own redis+rabbitmq, host Keycloak + remote DB. Left running and healthy.
- **Served list (20)**: hdfc, sbi, axis, idfc, paytm, citibank, city_union, au_sfb, bank_of_maharashtra, airtel_pb, iob, apgv, south_indian, pnb, bob, canara, icici, indian_bank, karnataka, kotak — default 14 + six N7 GO banks, via env var only; shipped defaults unchanged.
- **Truth cross-check**: 44 bank ids × 5 sources (shipped `bank_status.json`, live API, UI semantics, PRODUCT_STATUS, measured evidence) = **0 disagreements**.
- **Suites**: engine 508/508 · other backend 345 pass + 8 fails all reproduced identically at base `411f6ca` · frontend tsc + eslint + vitest 59/59 + `next build` green · `app.main` import ok.
- **Regression** `integration/v2-waves` tip vs final: 1,099/1,099 files, 41 diffs — every one a previously named, gate-safe change; 0 unexplained, 0 downward verdicts.
- **Confusion matrix**: 0 wrong accepts (3 UCO misfiles in the karnataka folder correctly refused).
- **Independent audit** (own seed, spec-independent): 358/358 sampled VERIFIED files hold; 0 balance-chain breaks.
- **Workflow on rc** (real auth, real jobs, Chromium): 31 PASS — sign-in/out, expired-token honesty, batch, override + warning, unsupported/locked/scanned/unknown handling, verified + review workbooks, honest failure + retry, two-user isolation, kill-restart, refresh mid-job, 3 widths, keyboard, a11y (1 real defect fixed), log scan clean.
- **Demo kit**: 25 fully synthetic PDFs ("Test Holder") covering all 20 served banks + locked/scanned/truncated/wrong-bank/unknown; `LIVE_DEMO.md` 10-minute path.
- **Cleanup**: 27 archive tags, 28 merged branches deleted (all verified ancestors), 21 worktrees removed, ~6.7 GB docker cache reclaimed; protected stacks untouched.

## Scoreboard

| state | start of night | after N9 |
|---|---|---|
| verified-servable | 7 | **16** |
| review-required servable | 0 | **4** |
| legacy servable | 7 | **2** |
| coming_soon (greyed, reason) | — | 17 |
| unsupported (greyed, reason) | — | 5 |

## Open defects (for Claude — backend-owned)

**Critical**: unauthenticated `GET /api/jobs/{id}` + `/download` (200 with
full workbook) · `GET /download/{file_id}` serves `/app/tmp` workbooks with
no auth · statement content + secrets persist forever in
`raw_transactions`/`statement_metadata`/`processing_jobs`/`job_events`/DLQ
(7-day promise broken) · committed KC client secret + test password
(rotate both).

**Major**: `X-Airco-User-*` header spoof on optional-auth upload ·
pypdf 5.1.0 / python-multipart 0.0.6 / next advisories · no rate limit, no
page cap · secrets in queue/Redis payloads · saturation head-of-line
blocking (25 parallel uploads → 0 client successes at 30 s, all jobs land).

**Minor**: `guest:guest` in AMQP connect log line · `/app/tmp` paths + S3
keys in `/api/jobs` payload · bob auto-detection thin · error bodies leak
temp paths · filenames in INFO logs · localStorage keeps apiKey/userDetails
forever.

## Deliverable map

| artifact | location |
|---|---|
| N7 report | `docs/onboarding/N7_REPORT.md` + `tools/n7/` |
| N8 reports | `docs/compliance|operations|security/N8_*.md`, `tools/n8/`, `docs/operations/CLEANUP_COMMANDS.md` |
| N9 final report | `docs/onboarding/N9_FINAL_REPORT.md` + `tools/final/` + `infra/docker/docker-compose.rc.yml` |
| live stack docs | `docs/operations/LIVE_STACK.md`, `LIVE_DEMO.md` |
| demo kit | `tools/final/demo_pdfs/` (25 synthetic PDFs + README) |
| markers | `docs/AGENT_STATE.md` ([N1]…[N9] DONE lines) |

**Verdict**: RELEASE **GO WITH CAVEATS** — verified 20-bank serve list is
correct, honest, and reproducible; N8 criticals gate any real-user exposure.
