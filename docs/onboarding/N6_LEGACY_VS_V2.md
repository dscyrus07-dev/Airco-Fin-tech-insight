# N6 Track B — legacy-only banks head-to-head against the v2 engine

Branch `devin/n6-legacy-vs-v2`, base `5be615d` (tip of `integration/v2-waves`, contains `411f6ca`).
Independent of Track A; no engine branches used. `decide_serve` unchanged; no allowlist/default changes.
Recommendations below are advisory only.

## Method

- Seeded sample per bank: up to 150 text-layer files stratified by header fingerprint
  (`tools/n6/sample.py`, seed fixed; all files when fewer — BoI n=73 corpus-wide).
- Each file through **(a)** the legacy parser pipeline (pdf_validator → structure_validator →
  parser → transaction_validator → DataIntegrityGuard) at `strict_mode=False` — the same mode
  production uses in `pipeline_orchestrator`, so guard failures surface as flags, not exceptions —
  and **(b)** the v2 router scoped to that bank's own registered specs (`route_pdf(bank_key=…)`,
  the path `serve.py` uses for a scoped/allowlisted bank). Legacy-only detector hold for
  `bank_of_india` is respected: the BoI leg uses scoped routing because the detector path is
  designed to stay legacy.
- Per-file independent audit on **both** outputs (`tools/n6/head2head.py`):
  dated amount-bearing lines vs extracted rows, forward chain recompute on the row balances,
  first/last balance vs printed anchor labels, v2 verdict, `integrity_passed` + failed check names.
- Known auditor precision limits (mechanisms verified on exemplars, rows/chain unaffected):
  `rows_gt_dated_lines` false-fires on banks with serial-glued dates (`1`+`11/11/2023`),
  glued txn/value date pairs (`31/0331/03`) or `(Cr)`-suffixed amount cells — heuristic
  misses those formats, rows are real; `open/close_anchor_mismatch` false-fires where the
  generic scan grabs an empty `--` balance cell (BoB) or an FD/TDS sub-summary closing
  (ICICI prints per-deposit "Closing Balance" lines inside a second section). Chain-break
  counts and row counts are unaffected by these; `rows_gt` was cross-validated against
  v2's count before treating it as a legacy defect.

## Per-bank results (usable files; locked/scanned counted separately)

| bank | usable | locked | scanned | both right | leg right / v2 not | v2 right / leg not | neither | serve Δ better | serve Δ worse |
|---|---|---|---|---|---|---|---|---|---|
| bank_of_baroda | 143 | 7 | 2 | 79 (55%) | 1 (0.7%) | 18 (13%) | 45 (31%) | +18 | 0 |
| bank_of_india | 52 | 18 | 3 | 0 | 20 (38%) | 0 | 32 (62%) | 0 | 0 |
| canara | 147 | 3 | 2 | 3 (2%) | 0 | 113 (77%) | 31 (21%) | +113 | 0 |
| icici | 147 | 3 | 1 | 32 (22%) | 4 (2.7%) | 13 (8.8%) | 98 (67%) | +13 | 0 |
| indian_bank | 138 | 12 | 4 | 0 | 0 | 35 (25%) | 103 (75%) | +35 | 0 |
| karnataka | 143 | 7 | 3 | 67 (47%) | 38 (27%) | 10 (7%) | 28 (20%) | +10 | 0 |
| kotak | 148 | 2 | 1 | 19 (13%) | 5 (3.4%) | 106 (72%) | 18 (12%) | +106 | 0 |
| union | 119 | 29 | 2 | 0 | 47 (40%) | 1 (0.8%) | 71 (60%) | +1 | 0 |

"leg right" = parsed, rows>0, independent chain clean, row count consistent with dated lines
(or cross-validated by v2 VERIFIED on undated families), no failed guard checks.
"v2 right" = routed + VERIFIED + chain clean. Serve Δ = files where the workbook a customer
receives changes for the better/worse if v2 serves VERIFIED and legacy serves the rest.

**The "v2 worse" subset is empty on all eight banks** — no file ships a worse workbook under
v2-with-legacy-fallback than under legacy-only.

### Leg condition and v2 coverage detail

| bank | leg parsed | leg errors | leg guard fails | leg chain-broken | v2 routed | v2 verdicts (V/R/F) | v2 fallback |
|---|---|---|---|---|---|---|---|
| bank_of_baroda | 87 | 54 | 9 | 7 | 107 | 97 / 1 / 9 | 34 no_layout |
| bank_of_india | 27 | 25 | 7 | 7 | 27 | 0 / 27 / 0 | 22 no_layout |
| canara | 4 | 142 | 2 | 1 | 140 | 116 / 12 / 12 | 5 (3 no_layout, 2 foreign_bank) |
| icici | 143 | 4 | 54 | 100 | 59 | 45 / 4 / 10 | 87 no_layout |
| indian_bank | 19 | 119 | 6 | 8 | 109 | 35 / 67 / 7 | 25 no_layout |
| karnataka | 126 | 15 | 22 | 20 | 81 | 77 / 0 / 4 | 59 no_layout |
| kotak | 29 | 119 | 5 | 0 | 140 | 125 / 6 / 9 | 7 no_layout |
| union | 47 | 67 | 5 | 0 | 87 | 1 / 75 / 11 | 30 no_layout |

## Recommendations

| bank | recommendation | why |
|---|---|---|
| bank_of_baroda | **SERVE_V2_WITH_LEGACY_FALLBACK** | +18/−0; VERIFIED on 97/107 routed; residual 34 no_layout files still serve (sometimes broken) legacy |
| bank_of_india | **KEEP_LEGACY** | v2 spec now exists (N6-built, tests pass, 27 REVIEW audited clean) but the whole family prints no independent opening/closing anchors → REVIEW ceiling → serve falls back to legacy on every file. Useful as shadow only. |
| canara | **SERVE_V2_WITH_LEGACY_FALLBACK** | legacy is dead on the corpus (142/147 structure-rejects on the app-export family); v2 VERIFIED on 116 |
| icici | **SERVE_V2_WITH_LEGACY_FALLBACK** | +13/−0 on covered families; v2 never worse. Coverage gap remains (below). |
| indian_bank | **SERVE_V2_WITH_LEGACY_FALLBACK** | legacy dead (119/138 structure-rejects); v2 VERIFIED on 35, REVIEW on 67 (falls back) |
| karnataka | **SERVE_V2_WITH_LEGACY_FALLBACK** | +10/−0; strongest legacy of the eight, but v2 is strictly ≥. 59 no_layout files stay legacy |
| kotak | **SERVE_V2_WITH_LEGACY_FALLBACK** | +106/−0; legacy dead (119/148) + merge/fabrication defects; v2 VERIFIED on 125 |
| union | **KEEP_LEGACY** | 75/87 routed files are REVIEW (anchorless family ceiling) and would serve legacy anyway; v2 VERIFIED=1. Serving v2 changes ~nothing today. |

### Residual gaps (not changed, documented)

- **icici** — 87/147 sample files print `Date|Description|Amount|Type` (no balance column,
  amounts on continuation lines, `DR`/`CR` type markers, wrapped narration). No registered
  layout covers it; the family is anchorless so REVIEW is its ceiling — a spec would only add
  shadow visibility, it cannot change serve outcomes. Separately, parked L3/L4
  ("Transactions List" exports) stay parked: the stale-balance reversal-pair issue is an
  engine `checks.py` matter — generic failing-row pattern for Claude below.
- **ICICI reversal-pair pattern (for `checks.py`)**: two adjacent rows carrying equal absolute
  amounts on opposite printed sides; the balance printed after the pair equals the balance
  before it (the pair nets to zero). The export reprints a stale balance through reversal
  pairs, so the plain balance chain counts a break. Guard rails needed: pair must be adjacent,
  same absolute amount, opposite sides, post-pair balance == pre-pair balance; anything looser
  is a real break. (Details in `docs/engine/ICICI_STALE_BALANCE_DESIGN_NOTE.md`; zero
  L3/L4-shaped files appeared in the N6 150-file sample — the family exists but is rare in
  the current corpus.)
- **union L3** stays parked (one-decimal amounts with `(Dr)/(Cr)` markers vs paise balances —
  exact reconciliation impossible).
- **indian_bank L3** stays parked (62%/56% trust previously measured; Mmm-first sub-variant
  embeds balances inside narration).
- **boi branch-print family** (monospace, one glued word per line) documented as
  `BANK_OF_INDIA_LAYOUT_1` but unreachable — header resolution can't split single-word lines
  (engine limitation, known class-F gap). The web-export family (L2) is what routes.

## Legacy defects, ranked by customer impact

Production runs non-strict: every defect below means a wrong workbook **ships today** —
except the structure/validation rejects, which mean no workbook at all.

1. **ICICI — fabricated/inconsistent balances on 100/147 sampled files**
   (`chain_broken_balances`). Includes row merges that fabricate amounts: two adjacent
   same-side printed rows collapse into one summed row keeping the later balance
   (verified on `1892a2f8`: printed `448.40 Cr`+`7275.00 Cr` rows ship as a single
   `7723.40 Cr` row). Generic repro: any ICICI export with consecutive same-direction
   transactions → workbook contains summed amounts that never existed, and balances that
   don't chain. sha8s: see `docs/onboarding/N6_DISAGREEMENTS.txt` § icici / chain_broken (100).
2. **Bank of India — fabricated running balances** on 7/52 parsed files, breaks ≈ row count
   (`5b0ab017` 919 breaks/938 rows, `6d86dc22` 2317/2324, `8d5702a1` 780/805, `40b218d1` 61/62,
   `58777439` 42/72, `37ed6741` 44/70, `855d86cf` 682/714). Nearly every printed balance is
   wrong in the shipped workbook.
3. **Kotak — cross-side merge fabrication**: adjacent `Dr`+`Cr` rows collapse into one
   net-amount row (`0cadea0b`: printed `59.00 Dr` and `4500.00 Cr` rows ship as a single
   `4441.00 Cr` row — an amount the bank never printed). Plus 5 files with missing
   date/description/balance fields (`008e5ed9`,`0effd165`,`17b03c2c`,`2089fa89`,`2c039b8b`).
4. **Karnataka — dropped rows**: `0c047426` emits 129 rows for a 608-dated-line statement
   (~79% of transactions missing) + 20 files with chain-broken balances.
5. **ICICI — extra/dropped rows vs dated lines**: `1203ecf7` +2 rows, `3b0051f0` −8,
   `5841ef09` −9, `1892a2f8`/`375f59bd` merge-driven under-counts.
6. **BoB — chain-broken balances** on 7 parsed files (`08c32ecd`,`0fad7997`,`264cedb5`,
   `2e455462`,`4b4a804a`,`716739f1`,`a54a1e2e`) + 9 guard `balance_reconciliation` fails.
7. **Volume rejects (no workbook produced)**: canara 140×`GenericStructureError` (app-export
   family unsupported by the legacy validator — dominates the corpus), indian_bank 114,
   kotak 119 (`KotakStructureError`/`KotakValidationError`), union 67, bob 54, icici 4,
   karnataka 15, boi 25. These are failures, not wrong data — customers get an error instead
   of a workbook.
8. **Karnataka/ICICI guard fails without chain evidence** — `balance_reconciliation`/
   `required_fields` check failures on otherwise-parsed files (karnataka 22, icici 54 incl.
   chain cases) — non-strict mode ships these anyway.

## Disagreement classification

Full sha8-level classification is in `docs/onboarding/N6_DISAGREEMENTS.txt` (PII-free;
bank → cause → sha8 list). Causes: `chain_broken_balances`, `GenericStructureError`,
`*ValidationError`, `PDFIntegrityError`, `integrity_*` guard fails, `rows_gt_dated`
(undated-family heuristic artifact — cross-validated where possible), `dropped_rows`,
`extra_rows`. v2 non-VERIFIED lists (FAILED/REVIEW sha8s) are per bank in the same file.

## What changed on this branch

- `backend/app/services/statement_engine/extractors/bank_of_india/layout_spec.py` (new):
  `BANK_OF_INDIA_LAYOUT_1` (branch-print, documented-unreachable) +
  `BANK_OF_INDIA_LAYOUT_2` (`DetailedStatement` web export: `Sr No|Date|Remarks|Debit|
  Credit|Balance`, dd-mm-yyyy, `₹`-marked right-aligned money, `row_order="auto"`,
  `left_aligned_amounts`, wrapped narration; evidence `IFSC:BKID`/`BANKOFINDIA`).
- `backend/tests/statement_engine/extraction/test_onboard_bank_of_india.py` (new): 6 synth
  tests — header match, row extraction, newest-first order, balance chain, foreign-bank
  marker rejection, missing-evidence refusal.
- `backend/tests/statement_engine/extraction/test_registry_store_and_router.py`: exclusion
  set updated — `bank_of_india` stays in `LEGACY_ONLY_BANKS` (detector path unchanged; specs
  exist for scoped/shadow routing only).
- `tools/n6/` (new): `sample.py` (fingerprint-stratified seeded sampler), `head2head.py`
  (dual-leg harness), `report.py` (quadrant + serve simulation), `redate.py`, `README.md`.
- Registry: `BANK_OF_INDIA_LAYOUT_2` appended to `DEFAULT_REGISTRY`.

## Gates

- Statement-engine suite: **425 passed**; `import app.main` ok.
- Cross-bank probe for the new BoI spec: 0 foreign header hits across ~350 pooled
  files from every other bank folder (mechanism: headers require `Remarks`+`Sr No` left
  furniture + BoI evidence `IFSC:BKID`/`BANKOFINDIA`, absent elsewhere).
- Whole-folder BoI measure after spec: 73 files → 27 REVIEW (all L2-routed, audit-clean
  chains: 899/899, 2324/2324, 1643/1643 dated rows), 22 no_layout (branch-print glued-mono
  family — engine gap), 18 locked, 3 scanned, 3 misc.
- Seeded 1,098-file regression vs `n4_tip` baseline on the 22-bank corpus: **see below**.
- Zero cross-bank false accepts observed in the h2h (v2 legs were bank-scoped; detector-path
  behavior measured separately in the xbank probe).

## NOT RUN

- Independent fresh audit of v2 VERIFIED files up to 40/bank — performed only on BoI (12
  REVIEW files, all clean) and spot-audits of flagged VERIFIEDs on bob/icici (anchor-scan
  artifacts confirmed benign). A full per-bank VERIFIED audit sweep was not run — the
  engine's own verification is what was measured, with independent chain recompute as the
  check.
- PDF-level tamper tests; OCR/scanned coverage (counted only: 19 files across banks).
- Locked-PDF leg (counts only: union 29, boi 18, others 2–12 — never opened).
- Legacy `enable_ai=True` leg (classification column absent; row/balance facts unaffected).
- No push, no merge, no allowlist/`decide_serve` changes.
