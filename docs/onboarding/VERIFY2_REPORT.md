# VERIFY2 — independent end-to-end verification of `au_sfb` and `bank_of_maharashtra`

Checker role: nothing taken from `PROMOTE_RESULTS.md` on trust; every number below was
re-measured with independent tooling (`tools/verify2/`). No product code changed.
Branch `devin/verify-2`. Verified tip: `54f51ab4` on `integration/v2-waves`
(contains required marker `54f51ab`).

## Verdict

| bank | engine-level gates | served output | verdict |
|---|---|---|---|
| `au_sfb` | all pass | **corrupted workbook on a VERIFIED file** | **NO-GO** |
| `bank_of_maharashtra` | all pass | clean on tested files, but defect trigger present in 6 corpus files | **NO-GO** |

Blocker is not a layout spec: it is a shared serve-path defect in
`backend/app/services/banks/_shared/base_processor.py`. After classification the
pipeline rebuilds row order using a composite content key; `eng_map.setdefault`
collapses duplicate keys and unconsumed engine rows are appended back. Any file
containing legitimately identical transactions (same date/description/ref/amounts/balance)
can gain phantom rows in the served workbook.

**Defect (MAJOR):** AU `7b2023ab` — engine returns 140 transactions; served
workbook `Transactions` sheet contains 142 rows: 2 trailing phantom duplicate
debit rows. Consequences: workbook closing balance -39,457.19 vs printed anchor
344.63; `validation.integrity_passed: false` while `Statement Check` reports
`Verdict: VERIFIED / Needs review: no / Independently verified: yes`. The
customer-facing workbook overstates debits and reports a wrong closing balance
while labelling the statement clean.

**Trigger prevalence:** duplicate composite keys found in 9/46 candidate corpus
files — AU `428c8b8d` (3), `7b2023ab` (1), `fa6131ab` (1); BOM `1511f656` (1,
REVIEW), `3902c72c` (1), `4e0bed94` (3), `6c9414f7` (1), `e775dd3a` (1),
`a9818bbf` (2). Demonstrated on `7b2023ab`; latent for the other 8.

**Proposed served list:** unchanged — `hdfc,sbi,axis,idfc,paytm,citibank,city_union`.
Do not add candidates until the order-rebuild leak is fixed and re-verified.

## 1. Boundaries and hygiene

- Diff `c550bac..54f51ab`: only onboarding LayoutSpecs/tests/docs/compose +
  known intended changes (IPPB bare marker `f870876`, Statement Check note
  `d58bcf8`). No changes to `checks.py`, registry logic, the 15 existing banks'
  specs/detectors, legacy parsers, `process_statement`, verdict policy, guards,
  `serve.py`, or flag defaults.
- Registry additions additive (new spec ids only). `dbs` L1 gained
  `opening_balance_re` — dbs is an onboarding bank; permitted.
- PII/secret scan of diff + new docs: clean (synthetic references and container
  IDs only).
- Tests on tip: statement_engine suite **391 passed**; frontend `tsc` clean;
  vitest **43/43**; backend import smoke OK (87 specs). Pre-existing non-engine
  failures identical on `c550bac` (8 fixture/env failures: missing axis/canara/
  icici sample PDFs, hdfc rule-engine count, api-key event loop).

## 2. Re-measurement (shadow mode, own runner)

| bank | claim | re-measured | delta |
|---|---|---|---|
| au_sfb | 16/17 read, 16 VERIFIED, 1 unroutable | 16 V2 VERIFIED + 1 `no_layout` | none |
| bank_of_maharashtra | 26/27 routed, 21V+5R | 21 VERIFIED + 5 REVIEW + 1 `no_layout` + 3 locked | none |

- AU unroutable file `4e1287dd`: confirmed zero own-bank evidence (narration-zone
  `AUBL`-ish substrings + foreign-bank tokens only) — correct refusal, corpus
  problem not a defect.
- Independent audit (own seed, spec-independent anchors): **37/37 VERIFIED files
  clean** — dated amount-bearing lines ≥ rows, forward chain reconciles, implied
  opening/closing match printed anchors. The two BOM sign-regex artifacts in the
  promotion report were reproduced in my own tooling too; anchors verified to
  match exactly — harmless tool artifact, no wrong workbook numbers.
- 5 BOM REVIEW files: all reconcile with printed anchors. REVIEW is honest but
  avoidable — summaries sit on final/second-to-last page, outside the engine's
  page-1/last-page anchor scan (engine gap). One also non-monotonic dates.
  Workbook numbers for `0ea90a40` verified correct end-to-end.
- Gates: AU det 16/17 (the miss is the evidence-less file — correct refusal);
  BOM det 27/27. Yield AU 94.1%, BOM 96.3% (≥90). VERIFIED share AU 100%,
  BOM 80.8% (≥80). Audit clean. **All engine-level gates pass for both banks.**

## 3. Cross-bank confusion

383 files, ≤10 per folder across 50 folders (all 15 existing + onboarded banks +
look-alikes: boi/bob/central/indian/iob/uco; equitas/ujjivan/fincare; APGB vs
APGV), both directions through detection and layout acceptance:

- **0 foreign accepts** under `au_sfb` specs; **0** under `bank_of_maharashtra`.
- Also 0 for `dbs`, `airtel_pb`, `uco` new/changed specs.
- False refusals: none observed for candidate folders.

## 4. Regression

650-file seeded stratified sample across the 13 available pre-existing bank
folders (only 13 exist in corpus), `c550bac` vs tip, `ONB_EXTRA_SERVE_BANKS` set
as the stack uses it:

- 613 files measured on both sides; 37 unmeasurable (non-bank docs/locked).
- **3 diffs, all legitimate**: karnataka-folder files containing own `UCBA` IFSC
  and zero karnataka text — misfiled UCO statements now correctly attributed to
  `UCO_LAYOUT_3` with honest FAILED verdicts.
- Bank, layout, tier, fallback, rows, verdict identical otherwise: **0 true
  regressions**.
- Synthetic probes (wrong-bank narration, truncated, clean complete, summary
  after transactions): **78 tests pass identically on base and tip**.

## 5. End-to-end on the onb stack (real HTTP)

Stack restarted only for `onb` with `ONB_EXTRA_SERVE_BANKS=au_sfb,bank_of_maharashtra`
(recorded). Backend image rebuilt from tip — the previous image was stale
(pre-Part-C, 81 specs vs tip's 87). `/api/statements/banks` verified: 7 defaults
+ 2 candidates `v2_served: true`; absent without the variable.

| sha8 | bank | detect | engine/verdict | rows eng/wb | sheets | chain | anchors | Statement Check | result |
|---|---|---|---|---|---|---|---|---|---|
| 7b2023ab | au | au_sfb | v2 VERIFIED | 140/**142** | 10 ✓ | 2 breaks | close mismatch | VERIFIED/nr no | **DEFECT** |
| f50a0f50 | au | au_sfb | v2 VERIFIED | 30/30 | 10 ✓ | ok | ok | ok | PASS |
| e613243c | au | au_sfb | v2 VERIFIED | 16/16 | 10 ✓ | ok | ok | ok | PASS |
| ad6970bb | au | au_sfb | v2 VERIFIED | 35/35 | 10 ✓ | ok | ok | ok | PASS |
| 39abd144 | au | au_sfb | v2 VERIFIED | 7/7 | 10 ✓ | ok | ok | ok | PASS |
| 4e1287dd | au | none | — | — | — | — | — | — | correctly unrouted (UNKNOWN) |
| 055add6c | bom | bom | v2 VERIFIED | 201/201 | 10 ✓ | ok | ok | ok | PASS |
| 0b9c23b9 | bom | bom | v2 VERIFIED | 339/339 | 10 ✓ | ok | ok | ok | PASS |
| ae282376 | bom | bom | v2 VERIFIED | 343/343 | 10 ✓ | ok | ok | ok | PASS |
| edaba8de | bom | bom | v2 VERIFIED | 48/48 | 10 ✓ | ok | ok | ok | PASS |
| 0ea90a40 | bom | bom | v2 REVIEW nr yes | 289/289 | 10 ✓ | ok | ok | REVIEW/nr yes/codes listed | PASS — honest REVIEW |
| 904ca49e | bom | bom | — | — | — | — | — | — | no_layout → job fails `bank_routing` honestly |
| 5d2d72d6 | bom | — | — | — | — | — | — | — | locked → PASSWORD_REQUIRED, no job |

Negatives (all correct):

- scanned `2afd8fc8` → UNSUPPORTED, no confirm path.
- unknown `45bab248` → UNKNOWN; confirmation refused `BANK_REQUIRED`.
- wrong-bank override AU→BOM (`7b2023ab`) and BOM→AU (`055add6c`): confirmation
  accepted at workflow level, processing fails `[bank_routing] ... not yet
  supported` — nothing wrong served.
- non-allowlisted override to `dbs` → `BANK_NOT_SUPPORTED`.
- non-allowlisted `canara` file → processed through legacy engine (by design).
- candidates on stack **without** the variable: absent from banks list;
  `f50a0f50` analyze → `UNSUPPORTED` ("This bank isn't fully supported yet").

## 6. Browser (Playwright, preinstalled Chromium)

- Single-file flow, both candidates: bank chip + `verified engine` option
  preselect correct; 17-bank dropdown; per-row Confirm works; Process button
  present (click timeout in runner is a harness artifact).
- Mixed 4-bank batch (hdfc/sbi/au/bom): all rows preselect correctly.
- UNSUPPORTED row: no bank select, no Confirm — as required.
- Widths 360/768/1280: no horizontal overflow.

## 7. Environment

- Before/after: `airco_auth_service`, `keycloak`, `keycloak-postgres`,
  `ue_backend/frontend/rabbitmq/redis` — identical container IDs, uninterrupted
  (40h/40h/40h/22h uptimes).
- `onb` stack: backend restarted twice (once to set `ONB_EXTRA_SERVE_BANKS`,
  once to remove it) and rebuilt once (stale image → tip). Restored:
  `STATEMENT_ENGINE_V2_SERVE_BANKS=hdfc,sbi,axis,idfc,paytm,citibank,city_union`.
  `onb_frontend/rabbitmq/redis` untouched. Left running on the **tip-built**
  backend image with default serve list — previous image no longer exists
  (rebuild overwrote the tag); flagged here since it differs from the image
  that was running at session start.

## 8. Claims audit

| claim (source) | verdict | evidence |
|---|---|---|
| AU 16/17 v2 VERIFIED, yield 94.1%, Vshare 100% (RESULTS/STATUS) | TRUE | independent re-measure identical |
| AU 1 file zero own-bank evidence, correctly unroutable | TRUE | `4e1287dd` inspected — correct refusal |
| AU audit 16/16 clean | TRUE | independent audit clean |
| AU cross 0/388 | TRUE | own 383-file run: 0 accepts |
| BOM 26/27 routed, 21V+5R, yield 96.3%, Vshare 80.8% | TRUE | identical |
| BOM audit clean; 2 sign-regex artifacts harmless | TRUE | reproduced artifact class; anchors match exactly |
| BOM cross 0/388 | TRUE | 0 accepts |
| 613-file regression: 0 true regressions, 3 misfiled-UCO diffs | TRUE | independently reproduced |
| 391 engine tests pass | TRUE | 391 pass on tip |
| `READY_TO_SERVE_CANDIDATE` label for au_sfb | **UNSUPPORTED — overruled** | served workbook corrupts a VERIFIED file (Defect §Verdict) |
| `READY_TO_SERVE_CANDIDATE` for bank_of_maharashtra | **UNSUPPORTED — overruled** | defect trigger present in 6 BOM corpus files; latent |
| candidates "safe via `ONB_EXTRA_SERVE_BANKS` for the user to try" (PR message) | FALSE implication for AU | trying AU serves wrong numbers on `7b2023ab` |

## 9. Defect list

| sev | sha8 | defect |
|---|---|---|
| MAJOR | `7b2023ab` | `base_processor` order-rebuild leaks duplicate-key rows: workbook 142 rows vs engine 140; phantom debit rows; closing balance -39,457.19 vs printed 344.63; `integrity_passed:false` while Statement Check says VERIFIED/no-review |
| MINOR | `904ca49e` | no_layout file confirmed by user → job fails `bank_routing` with legacy-style error rather than a routed refusal; honest but unfriendly |
| INFO | — | 5 BOM REVIEWs avoidable via mid-document anchor scan (engine gap); numbers in served workbooks are correct |

## 10. NOT RUN

- OCR (prohibited) — scanned/locked files covered only as negatives.
- Live mobile devices; Keycloak admin-side changes.
- Full-corpus regression (650-file stratified sample used instead).
- Demonstration of the row-leak on a BOM dup-key file (stack already restored;
  mechanism is shared and trigger verified present).

## Recommendations (labelled)

1. Fix `base_processor` order-rebuild for duplicate composite keys (track per-key
   queues/counts instead of `setdefault` + identity append), then re-run
   `tools/verify2/dupkeys.py`-flagged files E2E — only re-verify is needed, specs
   already pass all gates.
2. Add a workbook-vs-engine row-count assertion to serve-path validation so
   `integrity_passed:false` can never ship under a `VERIFIED` Statement Check.
