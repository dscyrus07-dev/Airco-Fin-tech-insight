# VERIFY3 — end-to-end re-verification after the row-leak fix

Base: `integration/v2-waves` tip `659d2b1` (contains `6705992` pnb 'Amount(INR)' variant and
`8102889` the marker-substring fix for SOUTHINDIANBANK ⊃ INDIANBANK). Branch `devin/verify-3`
(reports + tooling only; no product code changed). Stack: `onb` (:3400/:8401) rebuilt from tip.

GO means: safe to add to the default served list (`STATEMENT_ENGINE_V2_SERVE_BANKS`).

## Verdict per bank

| Bank | Result | Evidence |
|---|---|---|
| au_sfb | **GO** | 5 files e2e VERIFIED (912/696/140/91/7 rows, wb==engine every time); defect file `7b2023ab` fixed (140 rows, closing 344.63 == printed anchor); odd no-own-evidence file honestly UNKNOWN; BOM-confirm refused |
| bank_of_maharashtra | **GO** | 7 files e2e: 4 VERIFIED (252/289/477/160) + 3 REVIEW (290/281/813); AU-confirm refused |
| airtel_pb | **GO (thin corpus — recommendation)** | 3 VERIFIED (700/807/70); other 3 corpus files unidentifiable → override → honest job failure (no silent wrong data) |
| iob | **GO review-only** | 3 real + 1 synth REVIEW, `needs_review`, `NO_INDEPENDENT_ANCHOR`; UI notice renders |
| apgv | **GO review-only** | 3 real (62/455/965) + 1 synth REVIEW; APGB→apgv override refused; apgv→`apgb` rejected `BANK_NOT_SUPPORTED` |
| south_indian | **GO review-only** | 3 real REVIEW (705/378/409); full-brand synth detects `south_indian`, never `indian_bank` (marker fix proven) |
| pnb | **GO review-only** | 3 real REVIEW (279/415/1171) + synth; `Amount(INR)` variant serves |

Proposed default list (recommendation):
`hdfc,sbi,axis,idfc,paytm,citibank,city_union,au_sfb,bank_of_maharashtra,airtel_pb,iob,apgv,south_indian,pnb`

## §2 The defect, closed

`7b2023ab` (AU, original 142-vs-140 leak): workbook `Transactions` = **140 rows = engine rows**,
closing balance **344.63 == printed anchor**, Statement Check **VERIFIED**, **Needs review no**.

Duplicate-key corpus (`tools/verify2/dupkeys.py` over the 3 candidates, files with dup_keys>0):
10 processed e2e — `7b2023ab` 140, `428c8b8d` 696 (3 dup), `544c29ce` 807 (4), `d9ed04ad` 70 (4),
`bb24712d` 700 (1), `1511f656` 290 (1), `3902c72c` 252 (1), `4e0bed94` 289 (3), `6c9414f7` 477 (1),
`a9818bbf` 160 (2). **0 row mismatches** vs `stats_txn`; `e775dd3a` (1 dup) analyze timed out twice — NOT RUN.

### Guard false-alarm check — PASS (0 alarms)

`apply_row_count_guard` fired **0 times** on 34 correct served workbooks: 3×7 default banks
(hdfc 129/279/3661, sbi 149/279/299, axis 340/318/651, idfc 121/59/667, paytm 807/367/696,
citibank 123/328/1191, city_union 478/150/451 — all exact) + all candidate/review-bank serves.

Negative control: direct call with rows 5 vs engine 3 → `needs_review=True`, `anchored=False`,
`WORKBOOK_ROW_COUNT_MISMATCH` (plus existing unit test `test_serve.py`). A real-stack forced
mismatch was NOT RUN — no way to corrupt a served workbook without code changes.

## §3 Per-bank e2e totals

70 unique files through analyze→confirm→process→download: **43 completed jobs — 29 VERIFIED,
13 REVIEW, 1 legacy-serve. 0 row mismatches, 0 formula errors, 0 `WORKBOOK_ROW_COUNT_MISMATCH`.**

Negatives — all refused honestly, nothing silent:
| Case | Outcome |
|---|---|
| AU file confirmed as bank_of_maharashtra | job FAILED `bank_routing` (v2 route under wrong spec refused) |
| BOM file confirmed as au_sfb | same honest failure |
| APGB file confirmed as apgv | doc UNKNOWN → override → honest failure (OTHER_BANK_MARKERS) |
| APGV file confirmed as `apgb` | confirm rejected `BANK_NOT_SUPPORTED` |
| Locked PDF (`devin_locked_axis`) | REVIEW state, no processing |
| Scanned PDF | UNSUPPORTED, no processing |
| Garbage file | ERROR, no processing |
| synth_rbl (non-enabled) | UNSUPPORTED, no confirm path |
| Unknown bank (`4e1287dd`) | UNKNOWN, confirm requires selection; au_sfb override → honest failure |
| airtel unidentifiable ×3 | confirm `BANK_REQUIRED`; override → honest job failure |

SIB↔Indian Bank collision: shadow measure of 27 SIB + 153 Indian Bank corpus files — SIB layouts
only `south_*`/fallback prefixes, **0 cross-bank misroutes**. Full-brand SIB synth detects
`south_indian` (marker-substring fix verified live).

## §4 Regression

- 650-file corpus (13 banks): `54f51ab` vs tip — **0 diffs** (status/bank/layout/tier/rows/verdict).
- 84 extra files (3 candidates + citibank + city_union), measured on both revisions — **0 diffs**.
- spot40: fresh `54f51ab` measure == stored baseline — **0 diffs** (baseline reproducible).
- Total: **734 files, 0 diffs.**
- Synthetic probes: `probe_clean` VERIFIED 8/8; `probe_wrongbank_narr` VERIFIED 8/8 (SCBL in
  narration is not bank evidence); `probe_summary` VERIFIED; `probe_truncated` → v2 REVIEW
  (NO_INDEPENDENT_ANCHOR) → legacy serves with v2 advisory on the Statement Check sheet (by design).

## §5 UI with the enable list (onb :3400, Chromium)

Extras **set** (`ONB_EXTRA_SERVE_BANKS=au_sfb,bank_of_maharashtra,airtel_pb,iob,apgv,south_indian,pnb`):
- API: 22 servable / 44 `all_banks`; states: 3 candidates `verified`, 4 banks `review_required` — UI groups identical, all 7 selectable.
- Panel: "**22 banks supported · 17 coming soon · 5 not supported**"; all 5 groups render with all 7 banks listed; unsupported (Deutsche, RBL…) visible greyed. Review-row pickers: 5 optgroups, 22 disabled options.
- Full flows ×7: all detected, confirmed, processed. Result cards: VERIFIED badge for au/bom/airtel (`verifiedText`, no needs-review), persistent needs-review notice for iob/apgv/sib/pnb. Jobs confirmed VERIFIED/REVIEW server-side.
- No console errors; no horizontal scroll at 360/768/1280.

Extras **unset**: all 7 revert to `coming_soon`, not selectable; 15 servable; no console errors.

Mismatch between `all_banks` and UI display: **none observed**.

## Defects found (severity)

1. **MINOR (systematic, pre-existing): `validation.integrity_passed=false` on served workbooks** —
   `serve.py` passes `Decimal` expected balances/totals into `DataIntegrityGuard.validate`;
   float arithmetic raises `TypeError`, swallowed in non-strict mode → flag permanently false.
   Direct guard call with native floats = valid. Affects all v2 serves (repro: any e2e record's
   `validation.integrity_passed`). Does not affect verdict/rows; reconciliation passes.
2. **COSMETIC: wrong-bank/unroutable override error says "Bank 'X' is not yet supported"** —
   real cause is layout-route refusal (wrong bank or unverifiable file), not allowlist.
3. **MINOR: legacy-serve Statement Check shows `Needs review: no` beside `Advisory verdict:
   REVIEW`** (probe_truncated) — the advisory reasons are printed, but the needs-review cell
   doesn't reflect them.

## Docker findings

- `onb-backend` image built from tip contains `restore_statement_order`, `apply_row_count_guard`,
  `bank_status.json`; registered spec count == repository (97; repo-vs-image diff was line endings).
- Recreated with all 7 extras for the run, then **restored to default allowlist**
  (`hdfc,sbi,axis,idfc,paytm,citibank,city_union`; 15 servable). Other stacks untouched.
- `ONB_EXTRA_SERVE_BANKS` cleanly flips states both directions via the live API.

## Claims audit

- `[UB] iob/south_indian REVIEW_ONLY_SERVABLE` — confirmed e2e (real + synth + UI).
- `[UB] apgv REVIEW_ONLY_SERVABLE` + APGB non-collision — confirmed (incl. override refusal).
- `[UB] airtel_pb READY candidate 4/4 VERIFIED` — partially: 3/6 VERIFIED e2e, 3 unidentifiable
  (honest). Verdict path verified; corpus thin — recommend GO with that caveat.
- `[UI] DONE` grouped pickers / `all_banks` / review notices — confirmed live under extras + revert.

## NOT RUN

- Real-stack forced `WORKBOOK_ROW_COUNT_MISMATCH` (needs code injection; unit test + direct call cover it).
- `e775dd3a` e2e (analyze timed out twice); dup-key coverage stands at 10 files.
- `b7eb2e45` airtel override (analyze timeouts; override path covered by `60130945`/`82e92232`).
- Locked-PDF password flow (no passwords; `devin_locked_axis` correctly parked in REVIEW state).
- Full backend pytest suite (out of scope; prior phases' runs cover the touched areas).
