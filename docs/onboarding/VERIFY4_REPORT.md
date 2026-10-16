# VERIFY4 — independent verification: dbs, federal, dhanlaxmi (+ indusind informational)

Base: `integration/v2-waves` tip `74968f0` (work branch `devin/verify-4`, `5fbbb92`).
Method: same as V3 — wiring audit, fresh shadow recount, live E2E on rc (real
auth/jobs), independent 40-file audits, shadow + live confusion, wrong-bank
overrides, mutation, UI, 1,099-file regression vs `bedc4bf`.
Rules kept: no product-code changes, nothing pushed, `RETENTION_DRY_RUN=true`,
corpus read-only, no secrets/PII in outputs.

## Bank verdicts

| bank | files | gates | result |
|---|---|---|---|
| dbs | 137 (132 readable) | det 97.7%R · yield 97.7%R · V-share 89.9% · xbank 0 VERIFIED accepts · audit 40 | **NO-GO** — blocked by defect V4-3 (null-balance crash on REVIEW rows) |
| federal | 344 (292 readable) | det 94.9%R · yield 92.8%R · V-share 85.6% · xbank 0 VERIFIED accepts (8 REVIEW-flagged collisions) · audit 40 | GO |
| dhanlaxmi | 11 | det 100% · yield 100% · REVIEW-only ceiling (no VERIFIED corpus) · totals reconciled | GO as review_required |
| indusind | 136 (130 readable) | det 96.9%R · yield 92.3%R · V-share 76.7% (< 80 gate) | INFORMATIONAL — NO-GO (below VERIFIED-share gate) |

## Wiring (all candidates)

- `detectors/<id>.json` present; `banks/<id>.json` present.
- `DETECTOR_TO_SPEC_BANK` maps each id to itself (v2_router.py).
- `SUPPORTED_BANK_PROCESSORS` aliases `<id>` + `<id> bank` → `<id>`.
- `frontend/types/index.ts` `BankName` has display names.
- `bank_status.json`: `dbs`/`federal` absent (default servable when allowlisted);
  `dhanlaxmi` = `coming_soon` (must move to `review_required` or verified to serve);
  `indusind` = `coming_soon` (correct — stays).
- No product-code gaps found; no fixes made.

## Recount (fresh shadow run, tip `74968f0`, 1,450 files)

| bank | n | unread | det%R | yield%R | V | R | F | V-share |
|---|---|---|---|---|---|---|---|---|
| bandhan | 19 | 1 | 94.4 | 88.9 | 8 | 8 | 1 | 50.0 |
| central_bank | 45 | 7 | 84.2 | 71.1 | 2 | 25 | 5 | 7.4 |
| csb | 17 | 1 | 87.5 | 68.8 | 1 | 10 | 3 | 9.1 |
| dbs | 137 | 5 | 97.7 | 97.7 | 116 | 13 | 0 | 89.9 |
| dcb | 16 | 1 | 100.0 | 46.7 | 7 | 0 | 8 | 100.0 |
| dhanlaxmi | 11 | 0 | 100.0 | 100.0 | 0 | 11 | 0 | 0.0 |
| equitas_sfb | 40 | 4 | 88.9 | 75.0 | 4 | 23 | 5 | 14.8 |
| federal | 344 | 52 | 94.9 | 92.8 | 232 | 39 | 6 | 85.6 |
| hsbc | 91 | 57 | 91.2 | 64.7 | 0 | 22 | 9 | 0.0 |
| idbi | 104 | 10 | 72.3 | 41.5 | 17 | 22 | 29 | 43.6 |
| indusind | 136 | 6 | 96.9 | 92.3 | 92 | 28 | 6 | 76.7 |
| ippb | 5 | 0 | 80.0 | 80.0 | 0 | 4 | 0 | 0.0 |
| kvb | 83 | 9 | 5.4 | 4.1 | 3 | 0 | 1 | 100.0 |
| standard_chartered | 232 | 35 | 97.0 | 87.8 | 171 | 2 | 18 | 98.8 |
| uco | 9 | 0 | 100.0 | 33.3 | 0 | 3 | 6 | 0.0 |
| ujjivan_sfb | 33 | 0 | 75.8 | 63.6 | 1 | 20 | 4 | 4.8 |
| yes | 128 | 31 | 91.8 | 70.1 | 34 | 34 | 21 | 50.0 |

(unread = locked/scanned; det%/yield%R computed on readable subset; V-share =
V/(V+R) on v2-routed files.)

### N5 disagreements (fresh recount vs N5_RESULTS.md)

- `federal`: N5 table 291 files 232V/39R/6F/14fb — fresh 344 files
  232V/39R/6F/15fb + 52 unreadable (51 locked, 1 scanned). V/R/F identical;
  fallbacks 15 vs 14 (extra `bank_unconfirmed`); det 94.9%R vs claimed 95.2%
  (readable-basis reconciles it).
- `dbs`: N5 131 files 116V/11R/3fb — fresh 137 files 116V/13R/3fb + 5 unreadable
  (3 locked, 2 scanned). +2R on the enlarged folder.
- `indusind`: N5 129 files 92V/28R/6F/3fb — fresh 136 files same V/R/F +
  4fb/6unsup; V-share 76.7% (N5 line said 71%, summary said 77% — fresh 76.7%).
- `dhanlaxmi`: identical 11R.
- `standard_chartered`: N5 196 files 171V/2R/18F/5fb — fresh 232 files
  171V/2R/18F + 6fb/35unsup (folder grew; same verdict counts).
- Shadow cross-bank: 10 v2 routings of foreign-folder files — 8× csb→federal
  (all REVIEW-flagged, unbranded exports — not clean accepts), 1× idbi→icici
  (FAILED), 1× ujjivan_sfb(Visakhapatnam Co-op)→idbi (**VERIFIED, 85 rows — real
  wrong-accept on non-candidate bank**). N5 claimed 0/x on its sampled legs.

## Live E2E on rc (real auth/jobs, bank served via STATEMENT_ENGINE_V2_SERVE_BANKS)

42 corpus files driven analyze→confirm→process→poll→download (dbs 14,
federal 17, dhanlaxmi 11 — every outcome class incl. locked/scanned/fallback):

- 25 completed jobs: verdict == shadow verdict on all; workbook tx_rows ==
  engine rows on all; formula_errors = 0 on all; download HTTP 200 on all;
  `anchored: true` in engine_meta; Statement Check sheet reads
  Engine=v2 / Verdict=<matching> / "independently verified: yes".
- `integrity_passed`: 25 polled — 23 true, **2 false** (`2af0dfdf`,
  `2fae0724`, both REVIEW-path files — honest flagging, classified, not clean).
- Honest refusals (no job / no workbook): 4× UNSUPPORTED_SCANNED_PDF,
  5× PASSWORD_REQUIRED (locked), 6× UNKNOWN_BANK (unbranded exports).
- Honest routing failures: 6 files confirmed-as-candidate whose content could
  not route to the spec → `bank_routing … not yet supported`, no workbook
  (the fallback/unbranded set — correct behaviour).
- **Defect**: dbs REVIEW files `4b87612b`, `4e83e770` → job failed
  `[bank_processor] float() … 'NoneType'` — serve.py:383 → models.py:50
  `float(None)` on null-balance REVIEW rows. Honest failure, no workbook.

## Independent audit (audit2: dated lines vs rows, chain recompute, anchors)

- dbs 40/40: 2 files 1 chain_break each (single sparse-balance drift; rows
  match dated lines 133/133, 118/118 — classify: minor).
- federal 40/40: anchor-label mismatches are scanner artifacts — verified
  `0aa5bac0` manually: implied close 56.12 = last printed balance; the "closing"
  anchors the scanner found were per-section totals, and `GRAND TOTAL` lines
  reconcile. (Engine anchor check `anchored:true` on e2e records.)
- dhanlaxmi 11/11 REVIEW files: anchors weak/absent — consistent with the
  REVIEW-only ceiling claim.
- indusind 40/40: 18 no-printed-anchors + 12 open-mismatch — consistent with
  V-share shortfall.

## Confusion (live routing, forced candidate spec, in-process)

- dbs / federal / dhanlaxmi: 417 foreign files each force-routed —
  `verdict_accepts = 0` for all three (no foreign file produces a VERIFIED
  result under the candidate spec).
- Federal's 15 unbranded exports on live rc: 11 refused at analyze
  (`UNKNOWN_BANK`, no confirm), 1 REVIEW→honest job outcome, 3 infra timeouts
  re-run — none presented clean.
- Live override probe: airtel_pb file confirmed-as-dbs → job failed honestly
  (`bank_routing` refused). Reverse: dbs file confirmed-as-hdfc → failed
  `PDF does not appear to be an HDFC Bank statement`. Forward overrides on
  review-path foreign files → BLOCKED or refused (no clean workbook).

## Mutation testing

Real-PDF text-layer tamper (PyMuPDF redaction+reinsert on true corpus files):
- dbs `24a626a2` (VERIFIED, 36 rows): 3 mutants (amount/date-slot/balance) —
  all 3 detected dbs REVIEW, confirmed, then failed honestly at routing
  (tampered text broke the spec match → no route → unsupported raise).
- federal `1e86c913` (VERIFIED, 29 rows): amount + balance mutants failed
  honestly at routing; **date mutant → REVIEW workbook** (VERIFIED→REVIEW
  flip — correct, not clean).
- dhanlaxmi `205400fa` (REVIEW, 61 rows): same — 2 honest fails, date mutant
  REVIEW (never clean).
- Verdict: **0 clean-VERIFIED accepts across 9 real-file mutants**; gate held.
Earlier synthetic-PDF mutants (12) also all failed honestly at routing.

## UI (rc :3600, unified flow)

- Catalog `/api/statements/banks` → 25 usable banks / 44 total; groups render:
  Verified (19), Review required (4), Legacy parser (2), Coming soon (14),
  Not supported (5). Support-panel count = API count (25).
- dbs / federal / dhanlaxmi appear in **Verified** as selectable options;
  indusind absent from selectables, shown Coming-soon/greyed with reason.
- Full unified flow per candidate (DBS, Federal, Dhanlaxmi): upload → Details
  hint → analyze → REVIEW banner → per-doc Confirm → "Confirmed as X. Ready to
  process" → Process confirmed → report → Download Excel button. All 3 pass.
- Widths 1280 and 360: no horizontal scroll at 360.

## Regression

1,099/1,099 files tip vs `bedc4bf`: 41 diffs, **0 downward** — 5 pnb
fallback→v2 REVIEW upgrades, 5 bank_of_maharashtra REVIEW→VERIFIED, 31
fallback_reason rewording (no_layout→bank_unconfirmed). Identical explained
set to the FN run; nothing new.

## Defects

- V4-1 (minor, `74968f0`): analyze labels served-candidate docs
  `detail_state=UNSUPPORTED_BANK` when they need confirmation even though the
  bank is served — misleading label only; process leg serves v2 rows correctly.
- V4-2 (info, shadow): 8 csb-folder unbranded exports route to a federal
  layout as REVIEW (layout collision, flagged not clean).
- V4-3 (major, `74968f0`): **v2 REVIEW rows with `balance=None` crash the
  workbook path** — `statement_engine/serve.py:383` `t.to_dict()` →
  `pipeline/models.py:50` `float(self.balance)` →
  `TypeError: float() argument must be a string or a real number, not 'NoneType'`.
  Repro: dbs sha8 `4b87612b`, `4e83e770` (REVIEW rows with null balances).
  Job fails honestly — no workbook — but a served bank must serialize REVIEW
  rows; block GO until fixed and reverified.
- V4-4 (major, non-candidate): corpus file `0e8ceb69` (folder `ujjivan_sfb`,
  actually **Visakhapatnam Co-operative Bank**) routed to an idbi layout and
  marked **VERIFIED, 85 rows** — true wrong-bank accept, pre-existing on a
  non-candidate bank; tighten the idbi layout/detector before any idbi serve.

## Recommendations

- **dbs stays shadow-only** until V4-3 is fixed: serialize `balance=None` as
  blank/null (or drop the balance column for null-balance REVIEW rows) in
  `pipeline/models.py:50`, then re-verify the two repro sha8s end-to-end.
  All dbs gates otherwise pass (97.7%R det/yield, 89.9% V-share, 0 xbank
  accepts, audit clean modulo 2 benign sparse-balance chain drifts).
- Add bank markers/coverage for federal's unbranded AC_STATEMENT exports
  (15 files) — currently refused honestly; serving them needs evidence.
- idbi spec should not VERIFIED-accept the Visakhapatnam Co-op layout
  (`0e8ceb69`) — tighten layout or detector before any future idbi serve.
- dhanlaxmi: keep `review_required` posture — REVIEW-only is the honest
  ceiling for this corpus.

## Proposed bank_status.json diff (proposed only — not applied)

```diff
 banks: {
-  "dhanlaxmi": {"state": "coming_soon", "reason": "..."}
+  "dhanlaxmi": {"state": "review_required", "reason": "V2 rows serve under review cap; corpus has no readable balance anchors for VERIFIED."}
 }
```

## Proposed served list

`hdfc,sbi,axis,idfc,paytm,citibank,city_union,au_sfb,bank_of_maharashtra,airtel_pb,iob,apgv,south_indian,pnb,bob,canara,icici,indian_bank,karnataka,kotak,federal,dhanlaxmi`

(federal → verified group; dhanlaxmi → review_required group; **dbs omitted —
shadow-only until V4-3 fixed**. If V4-3 is patched and the two repro files
re-verify clean, append `dbs` to the list.)

## NOT RUN

- Live full-path confusion uploads of all 417×3 files through process
  (queue-bound ~14h); replaced by forced-spec `route_for_serve` shadow runs
  covering identical routing logic + sampled live overrides (0 accepts both).
- dhanlaxmi VERIFIED audit (corpus contains no VERIFIED files — 11/11 REVIEW;
  audit ran on all 11 REVIEW files instead).
- OCR/scanned-content verification (forbidden by rules; scanned files are
  refused before OCR by design).
