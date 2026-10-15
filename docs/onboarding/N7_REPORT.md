# N7 — integrate, rebuild `onb`, independently verify candidates end to end

Branch: `devin/n7-integrate` · base: `integration/v2-waves` tip `5be615d` ·
worktree `X:/Airco Projects/wt-n7` · checker role: no product changes except
merge-conflict resolutions (all listed). Nothing pushed. Counts/verdicts/sha8
only — no statement content anywhere.

Gate check at start: `[N4] DONE 5f6c237` (all ACCEPT → zero `n4-revert-*`
branches needed, condition vacuous), `[N5] DONE` absent from
`docs/AGENT_STATE.md` (process defect — N5 reported DONE at branch tip
`37f970f`, report + tip verified), `[N6] DONE 475479f`, `[N8] DONE 760b563`.
All satisfied → proceeded without waiting.

## Part A — integration

Merges in required order:

| merge | commit | conflicts | resolution |
|---|---|---|---|
| `devin/n5-bank-wave` | `0ae26c7` | `docs/AGENT_STATE.md` | chronological union of N1–N5 lines + N7 START |
| `devin/n6-legacy-vs-v2` | `c5018a2` | `docs/AGENT_STATE.md`; `extractors/registry.py` | AGENT union; registry = **union** of N5 imports/specs + N6 BoI `BANK_OF_INDIA_LAYOUT_2` |
| `devin/n8-compliance-hygiene` | `cbe70ab` | `docs/AGENT_STATE.md` | union (N8 completion + N7 markers) |

Registry union kept: N5 `DHANLAXMI_LAYOUT_2/3`, Federal, IndusInd, DBS layouts;
N6 `BANK_OF_INDIA_LAYOUT_2`. `BANK_OF_INDIA_LAYOUT_1` stays parked (branch-print
glued-monospace engine gap, unchanged).

No product code written; no N4 reverts needed (N4 marked every capability ACCEPT).

## Part A — suites (integrated tip)

| suite | result |
|---|---|
| statement-engine unit (`tests/statement_engine`, `tests/banks` engine) | **508 passed** |
| `app.main` import smoke | OK |
| broader backend | 336 passed, 18 skipped, 3 failures — all **pre-existing/environmental** vs base tip (missing `samples/` axis fixture absent from worktree; HDFC JSON `Salary Credits` vs `Salary` expectation; asyncio event-loop test harness on Windows) |
| frontend `tsc` | 0 errors |
| frontend eslint | 0 errors |
| frontend vitest | 58/58 (7+51) |
| frontend `next build` | OK (22 audit vulns carried over — N8 finding, unfixed per scope) |

## Part A — zero-change regression, 1,099/1,099 files (base `5be615d` vs integrated)

Fields compared per sha8: status, fallback_reason, layout, rows, verdict.
`tools/n7/diff_reg.py`; shard records `tools/n7/.local/{base,integ}_shard*.jsonl`.

**41 diffs — all gate-safe and named:**

| group | n | what | disposition |
|---|---|---|---|
| bank_of_india | 15 | `no_layout`→`bank_unconfirmed`/`foreign_bank` (status stays fallback, 0 rows) | N6 expected — spec registered, gate still refuses |
| bank_of_maharashtra | 5 | `REVIEW`→`VERIFIED` | N5 improvement; **re-audited: 0 chain breaks on all 5**, same-bank layout, VERY_HIGH detector |
| icici | 13 | `no_layout`→`bank_unconfirmed` (10) / `foreign_bank` (3) | N5 detector evidence now fires; the 3 `foreign_bank` = IDBI layout tried and **rejected** — no wrong accept |
| pnb | 5 | `no_layout`→v2 routed to new `pnb_*_2l/3l` layouts → REVIEW | N5 new layouts; REVIEW is the safe verdict |
| paytm | 2 | `no_layout`→`bank_unconfirmed` | detector evidence present, still refused |
| au_sfb | 1 | `no_layout`→`bank_unconfirmed` | same |

Zero files changed verdict downward; zero wrong-bank routings; zero
silent output changes on served banks.

## Part B — onb rebuild + candidate set

Rebuilt **only** `onb-backend`/`onb-frontend` images from the integrated tip
(`docker compose -p onb … build`). `onb_redis`/`onb_rabbitmq` left running
(18h+ uptime, untouched); all protected stacks (`airco*`, `keycloak*`,
`ue_*`, `demo_*`) untouched — ids/uptimes recorded before/after below.

N5 produced **zero** READY/REVIEW_ONLY candidates (all `SHADOW_ONLY`), so the
candidate set = N6's six `SERVE_V2_WITH_LEGACY_FALLBACK` banks.

`ONB_EXTRA_SERVE_BANKS=bob,canara,icici,indian_bank,karnataka,kotak` appended
to the unchanged 14-bank default. `GET /api/statements/banks` on the rebuilt
stack: all six report `support_state=verified, v2_served=true`
(22 servable / 44 total).

## Part B — end-to-end verification

Real HTTP flow per file: analyze → confirm/override → process → poll →
download → workbook checks (`tools/n7/e2e_n7.py`; timing captured per stage).
Every served job's `engine_meta` asserted = `engine:v2, mode:serve`.
Independent validation joined each record to the integrated-tip shadow records
and to spec-independent audits (`audit2.py` — generic-label anchor scan +
chain recomputation, 108 files): `tools/n7/validate_n7.py`.

### Per-candidate evidence summary

(see `tools/n7/.local/e2e_*.jsonl`, `neg_*.jsonl`, `ovc_*.jsonl`)
Completed serve jobs (v2 VERIFIED / v2 REVIEW / legacy-fallback / OVERRIDE→VERIFIED):

| bank | v2 VERIFIED | v2 REVIEW | legacy fallback | OVERRIDE→V | UI | notes |
|---|---|---|---|---|---|---|
| bank_of_baroda | 3 | — | — | 3 | ✓ | weakest auto-detect; OVERRIDE path proven |
| canara | 5 | — | — | — | ✓ | IFSC `CNRB` drives detection |
| icici | 5 | — | — | — | ✓ | topup lane cut at restore (see NOT RUN) |
| indian_bank | 5 | 2 | — | — | ✓ | REVIEW wbs carry honest reasons |
| karnataka | 6 | — | 2 | — | ✓ | incl. redo after token-expiry fix |
| kotak | 3 | — | 1 | 1 | ✓ | fallback on 1,159-txn file |

Totals: **31 v2 VERIFIED + 2 v2 REVIEW + 3 legacy-fallback = 36 completed
serve jobs; validator flags: 0** (detected==folder, verdict==shadow run,
wb rows==engine rows, zero formula errors, integrity consistent on every
completed record).

### Key negative results (all honest refusals, zero wrong accepts)

- locked PDF → `PASSWORD_REQUIRED` (no password given → no processing)
- scanned PDF → `UNSUPPORTED`/`UNSUPPORTED_SCANNED_PDF`, `BLOCKED`
- wrong-bank override (candidate file → other candidate bank) → job proceeds
  through the *selected* pipeline; mismatch guard + spec routing produce
  FAILED/refused rather than a wrong VERIFIED workbook
- union (non-enabled, legacy-only) → routed to legacy path, not v2
- UNKNOWN-detected file → `BANK_REQUIRED` at CONFIRM (explicit selection
  required — no silent acceptance)
- crossfile (other candidate's file) → detected as its own bank, processed as such

### Cross-bank confusion matrix (1,099 files, integrated registry)

`tools/n7/confusion.py` — folder bank vs routed spec bank.
**Wrong accepts: 0.** The only foreign-bank routings were 3 `UCBA`-IFSC UCO
statements misfiled inside the karnataka folder — detected UCO VERY_HIGH,
parsed under the UCO spec, and correctly FAILED by completeness/integrity.
Two icici files similarly probed by the new IDBI layout were **rejected**.

### Workbook validation (all downloaded workbooks)

- Transactions rows == engine rows on every completed job
- zero formula errors (`#REF`/`#VALUE`/… scan across all sheets)
- `integrity_passed` true (or job FAILED honestly — none shipped bad output)
- implied opening/closing vs printed anchors checked by `audit2.py` where
  anchors exist (0 anchor violations on VERIFIED files; BoM files carry no
  printed anchors — noted, chains clean)

### Mutation tests

`tools/n7/mutate.py` — 12 downloaded workbooks (2/candidate), two mutants
each (one middle-row amount +1.00, one row deleted), re-checked by the
independent validator: **24/24 flagged** (chain break, row-count mismatch,
or anchor violation — none shipped silently).

### UI (Playwright, preinstalled Chromium) — `tools/n7/ui_n7.mjs`

- all 6 candidates: `verified` + `v2_served` in catalog; each UI flow
  detected its bank and reached a report (bob verdict label not captured —
  job queued behind lanes when the 5-min UI wait elapsed; API-side job
  completed VERIFIED)
- mixed batch (iob + yes + federal + hdfc + canara): review tag, two
  not-enabled/coming-soon labels, both enabled files detected
- 360px and 1280px: no horizontal scroll; **0 console errors**
- union/bank_of_india still `legacy`; federal/yes `coming_soon`

### Performance (serve path)

p50/p95 per bank and >120s files: `tools/n7/perf.py` on the e2e records
(process time includes the full downstream pipeline + WAN S3 puts, not just
v2 extraction). Measured:

| bank | analyze p50/p95 (s) | process p50/p95 (s) | files >120s |
|---|---|---|---|
| bank_of_baroda | 8.7 / 13.1 | 185.4 / 365.3 | 12ca1446 (185), 0a16b8f3 (385) |
| canara | 10.0 / 24.8 | 300.2 / 381.0 | 5 files, max 395 |
| icici | 9.8 / 13.4 | 291.7 / 409.2 | 4 files, max 414 |
| indian_bank | 6.2 / 11.4 | 128.9 / 372.2 | 6 files, max 380 |
| karnataka | 9.0 / 13.0 | 128.8 / 280.7 | 4 files, max 281 |
| kotak | 10.4 / 10.7 | 322.5 / 322.5 | 008e5ed9 (322); 17b735d8 legacy 105 |

**Every bank has files >120s** — process time is dominated by the shared
downstream pipeline (WAN S3, report build), identical on legacy and v2
paths. No v2-specific regression observed vs legacy timings on similar
files.

## Part C — defects found during verification

Integration-specific (new):

| sev | defect | repro |
|---|---|---|
| minor | bob/kotak auto-detection thin — many corpus files land `UNKNOWN_BANK` and need explicit bank selection; OVERRIDE path serves correctly after selection | `03693e1c`, `073872a4` |
| minor | CONFIRM (no selection) on UNKNOWN docs returns `BANK_REQUIRED` — correct but means auto-confirm-all skips them silently in bulk flows | same |
| minor | `foreign_bank` fallback_reason now covers "new spec tried+rejected" too — reason taxonomy widened silently (N5 layouts) | `39e8d519` |

Carried (pre-existing, N8-documented — not fixed per scope): unauthenticated
job read/download (critical), `/download/{file}` no-auth (critical),
queue/Redis/DLQ secret+PII persistence (major), header-spoof auth (major),
vulnerable deps (major), no rate limit/page cap (minor+),
tmp-path error leaks, localStorage secrets.

## Claims audit

`tools/n7/claims_audit.md` — every re-measurable N5/N6 claim marked
TRUE / FALSE / UNSUPPORTED.

## Part C — verdicts

| candidate | verdict | basis |
|---|---|---|
| bank_of_baroda (`bob`) | **GO** | 6 VERIFIED serve jobs (3 auto + 3 OVERRIDE), 0 flags, mutations caught; auto-detect thinness is a detector-coverage limitation with a working explicit-selection path, not an integrity risk |
| canara | **GO** | 5 VERIFIED, IFSC-driven detection, clean matrix |
| icici | **GO** | 5 VERIFIED, clean matrix (foreign probes rejected) |
| indian_bank | **GO** | 5 VERIFIED + 2 honest REVIEW with printed reasons |
| karnataka | **GO** | 6 VERIFIED + 2 legacy-fallback serves (N6 fallback path proven); UCO misfiles refused |
| kotak | **GO** | 3 VERIFIED + 1 OVERRIDE→V + 1,159-txn legacy-fallback; thinnest coverage noted |

All six recommend `SERVE_V2_WITH_LEGACY_FALLBACK` exactly as N6 proposed:
the allowlist derives served status; no `bank_status.json` table rows
needed for GO banks (proposed patch `tools/n7/bank_status_proposed.patch`
documents this — **not applied** to the shipped table, verified unchanged).

**Proposed served list** (14 default + 6 candidates):

```
hdfc,sbi,axis,idfc,paytm,citibank,city_union,au_sfb,bank_of_maharashtra,airtel_pb,iob,apgv,south_indian,pnb,bob,canara,icici,indian_bank,karnataka,kotak
```

## Stack records

Protected stacks before: `onb_redis 18d6a0858d38` (healthy, 18h),
`onb_rabbitmq 1ebdd3205c82` (healthy, 18h), `onb_frontend c7c5d1baaf8e` (18h),
`onb_backend f7eaf7ebd751` (healthy); airco/keycloak stacks up 19–21h;
`ue_*` exited 25h ago (pre-existing).

After (close-out): `airco-agent-db-1 4579bf0eeef3` (21h healthy),
`airco_auth_service 8e2e980a8292` (19h healthy),
`aircoopsagentv2-{db,web,worker} 5055ff0ef8f8/f96d3ae63b09/5250e39f6347`
(21–22h), `keycloak fb9949a38cac` + `keycloak-postgres 9b188150407d`
(19h healthy), `onb_rabbitmq 1ebdd3205c82` + `onb_redis 18d6a0858d38`
(19h healthy — untouched throughout). `onb_backend 2571e65b1a9d` /
`onb_frontend aa23e07bc836` recreated at restore (expected — only the
two rebuilt containers changed identity across the session).

## onb restored to default

`ONB_EXTRA_SERVE_BANKS` removed; backend env verified post-restore:
`STATEMENT_ENGINE_V2_SERVE_BANKS` = the original 14-bank list
(hdfc…pnb), health `{"status":"ok","version":"2.0.0"}`.
Shipped `bank_status.json`: byte-identical (`git diff` empty).
Default served list not changed by N7.

## NOT RUN

- icici top-up lane (6 additional files) killed at restore cut — the five
  icici mains already cover the serve path; listed honestly rather than
  claimed.
- Remaining per-bank REVIEW/fallback-group corpus tails beyond the
  36 completed jobs (each such job costs ~2–6 min; tails truncated at
  the ~5h box).
- bob UI verdict label visible in screenshot (job still queued at the
  5-min UI cap; API-side VERIFIED + OVERRIDE records cover the same path).
- Second-authenticated-user isolation test (one Keycloak test user exists —
  N8 carried item).
- Wrong-bank override *accept* probes rely on the 3 UCO misfiles (only
  real foreign-layout corpus instances) + IDBI-rejection cases; synthetic
  foreign-bank override tests beyond these not run.
- Legacy `enable_ai=True` leg (N6-carried).
