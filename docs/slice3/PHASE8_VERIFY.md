# Phase 8 — independent verification of Waves 6 + 7

Scope: verify Waves 6 (anchor recovery, `2f54fd7`) and 7 (coverage, `0898e79`) on
`devin/wave6` in `wt-trackA`. Independent = re-derivation from raw PDF bytes
(pdfplumber), corpus hash checks, mutation gates, and reproducibility re-routes —
not trusting engine self-reports. Artifacts: `comparison/phase8/`.

## 1. Corpus immutability

- 400/400 sampled corpus PDFs re-hashed: **0 mismatches** (`corpus_immutable.json`).
  The unified corpus is unchanged since wave baselines were computed.

## 2. Registry integrity

- 72 layouts across 33 banks, 0 duplicate layout_ids (`verify_static.json`).
- `header_only_ok`: **empty** — no layout may route on header alone.
- `anchor_full`: 18 layouts (12 gated in W6 + federal L1/L2/L3, axis L3/L4,
  hdfc L_B added in W7).
- Codec round-trip verified for `header_wraps`/`date_left_pad` on all 72 specs.

## 3. Reproducibility rerun

Re-routed 721 files under committed code and diffed vs recorded artifacts
(`rerun.jsonl` → `rerun_diffs.json`):

- **716/721 identical** (status, layout, row count, rowhash, verdict).
- **5 diffs, all intended W7 deltas**, adjudicated individually:
  - `1efb09b1`, `1a24d813` (federal): VERIFIED→REVIEW — the new `anchor_full`
    cap on federal L3. Baseline predates the policy; the cap is the point.
  - `a8a70884` (union): FAILED→REVIEW — `row_order:auto` selected the chain-
    proven direction (baseline hardcoded `reverse` failed honestly).
  - `1267af6f`, `da2f4eca` (union): NO_ROWS→v2 FAILED — W7 date/amount widen
    recovered rows; verdict is honest FAILED.
- **0 unexplained drift.**

## 4. Mutation gates (anchor sensitivity)

For every VERIFIED file on newly-anchored layouts, 5 mutations on normalized
rows (first/last amount +1, first-row side flip, drop first, drop last) must all
fail — proving the anchor/check machinery actually sees tampering.

- Wave 6: 12 `anchor_full` layouts clean (results in `comparison/wave6/`).
- Wave 7: **46/46 new VERIFIED files × 5/5 mutations → FAILED**
  (`mutations_federal.txt`): federal L2/L3 42 files, hdfc L_B 4 files.
- 230/230 mutations caught. None silently verified.

## 5. Wrong-bank scan

All 15,679 recorded records cross-checked: folder bank vs layout bank
(`verify_static.json.folder_vs_layout_mismatch`):

- 2 mismatches, both **REVIEW-capped with independent evidence**:
  - `ccca9c20`: folder "Kotak" → central_bank layout; `detector:central_bank:MEDIUM`
    + `bank_evidence:region` — file is mis-filed, not mis-routed.
  - `84c3abcc`: folder "Axis" → south_indian layout; `detector:south_indian:VERY_HIGH:65`
    + `bank_evidence:detector`.
- **0 wrong-bank VERIFIED.** REVIEW on evidence-backed disagreement is the
  designed behavior.

## 6. Evidence gates (live re-probe under committed code)

- `0186b828` (Kotak folder, kotak header match, `detector:UNKNOWN`, no markers)
  → `bank_unconfirmed` ✓
- `014e58bd` → `foreign_bank` ✓
- `bank_unconfirmed`=456 in the 14,445-file baseline — sampled files carry
  competitor-bank tokens or none (`BANK_UNCONFIRMED_ANALYSIS.md`).
- `allow_header_only` remains off; nothing routes on header alone.

## 7. Independent re-derivation of new VERIFIED anchors

pdfplumber line-scan (no engine code) for all **46** W7 VERIFIED files
(`g2_w7.txt`): printed opening balance matches engine `summary.opening` on every
file (2 verifier artifacts adjudicated: `4033b0ca` re-run clean MATCH;
`d032c98a` verifier picked an off-line amount — printed is literally
`Opening Balance 0 Cr` = engine 0). HDFC closings derive from the 6-number
`STATEMENT SUMMARY` block (verifier label-scan can't label it — verifier limit,
engine capture confirmed in W7).

## 8. Honest-category audit (14,445-file baseline)

All refusal/review categories populated and attributable:

| category | files | disposition |
|---|---|---|
| VERIFIED | 7,177 | gated by anchors/checks; W7 +46 |
| REVIEW | 1,851 | honest caps: single-ended anchors, warnings |
| FAILED | 467 | chain/side/schema breaks — kept, not forced |
| bank_unconfirmed | 456 | evidence gate working |
| foreign_bank | 131 | competitor-marker refusal working |
| no_layout | 2,018 | 171 recovered in W7; rest evidence-less/unparseable |
| NO_ROWS | 47→~24 | W7 widens recovered ~23 |
| locked/scanned | 2,196 | environment limits |

## 9. Secrets scan

212 regex hits over wave artifacts — all file-path strings (corpus paths contain
"PIN"-like tokens). **0 actual secret terms** (password/otp/api-key/bearer/
aadhaar/pan). Artifacts carry sha prefixes, counts, statuses only.

## 10. Test suite

182/182 statement_engine tests pass under committed code.

## Known limitations / hardening items

- `run_checks` on 0 rows can return VERIFIED — dead corner only (router
  short-circuits `NO_ROWS` before checks; not reachable via `route_pdf`).
  Worth a defensive guard anyway.
- ICICI L3/L4 wrap family (~140 files) needs a new spec; parked — stale-balance
  exports can only ever yield honest FAILED/REVIEW.
- Union fused single-token headers + ICICI balance-less `amount type` cluster
  (~345) unrepresentable without parser changes; parked by design.
- `bank_unconfirmed` files need an explicit `header_only_ok` policy decision —
  none granted.

## Verdict

Waves 6+7 verified: reproducible (716/721 identical, 5 intended deltas),
anchors real (46/46 re-derived, 230/230 mutations caught), no wrong-bank
VERIFIED, evidence gates live, honest categories populated, corpus immutable.
PASS.
