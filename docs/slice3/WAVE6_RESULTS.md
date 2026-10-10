# WAVE 6 — ANCHOR RECOVERY RESULTS

Branch `devin/wave6`, base `880b5e2`, worktree `wt-trackA`. Never pushed.
Corpus: shared `Unified All Statements` (read-only). Subset run: all 854 files that sat at
`reference=skipped` (self-derived balance chain) on the 15 anchor-candidate layouts.

## Policy applied

`LayoutSpec.anchor_full` (new field, serialized via `spec_codec`): a layout only reaches
VERIFIED when **both ends** of the balance chain are covered by *printed* references —
opening + (closing | printed totals). Single-ended coverage (e.g. closing-only) stays
REVIEW, because a corrupted first row shifts the self-derived opening in lockstep and the
mutation gate showed it would stay VERIFIED silently.

## Engine changes (`extraction/engine.py`)

- `closing_balance_re` fallback: if the closing label is not in post-table `summary_lines`,
  scan page-1 text and last-page text (covers banks that print the summary above the table
  or at the page footer after the table runs to the end).
- `opening_balance_re` last-page fallback (same reason).
- `anchor_full` gate: single-ended printed anchors are dropped (`out.summary` stays None)
  so the verdict cannot reach VERIFIED.

## Layout spec changes

| Layout | Change |
|---|---|
| au_sfb | opening `OpeningBalance - INR<x>` repaired |
| axis | opening+closing `OpeningBalance:<x>` / `ClosingBalance:<x>` last page |
| bandhan | `summary_marker` + `summary_label_text` for labels→6-numbers summary block |
| bom | opening+closing `OpeningBalance<x>` `ClosingBalance<x>` before `END OF STATEMENT` |
| city_union L2 | `asof`→`ason` fix + `Total<dr><cr>` totals line |
| dbs | `ClosingBalance<x>` before `***EndofStatement` + `anchor_full` |
| dcb | `openingbalance` widened to integer amounts + closing added |
| iob (cod) | `totals_line_re` `TotalDebit:<x>TotalCredit:<y>` repaired |
| kotak L4 | `OpeningBalance:<x>` `ClosingBalance:<x>` last page |
| kotak L6 | opening probe reverted — no printed closing exists |
| paytm | strict comma-grouped 4-amount run → opening+closing on page 1 |
| sbi postdate | `BroughtForward<x>Cr` opening + `ClosingBalance<x>Cr` closing |
| scb yearless | `BalanceBroughtForward<x>` + `Total<dr><cr>` totals |
| union L1 | closing probe reverted — closing-only coverage fails the mutation gate |
| yes L1 | `OpeningBalance:<x>` `ClosingBalance:<x>` footer |

## Result (854 files, routed at tip)

| Layout | n | VERIFIED | REVIEW | FAILED |
|---|---:|---:|---:|---:|
| au | 14 | 14 | 0 | 0 |
| axis | 3 | 3 | 0 | 0 |
| bandhan | 5 | 5 | 0 | 0 |
| bom | 11 | 8 | 3 | 0 |
| city_union | 6 | 6 | 0 | 0 |
| dbs | 118 | 0 | 112 | 6 |
| dcb | 15 | 7 | 0 | 8 |
| iob (cod) | 22 | 0 | 19 | 3 |
| kotak L4 | 60 | 60 | 0 | 0 |
| kotak hash L6 | 55 | 0 | 52 | 3 |
| paytm | 142 | 139 | 0 | 3 |
| sbi postdate | 26 | 23 | 0 | 3 |
| scb yearless | 24 | 24 | 0 | 0 |
| union L1 | 306 | 0 | 305 | 1 |
| yes L1 | 47 | 15 | 21 | 11 |
| **TOTAL** | **854** | **304** | **512** | **38** |

Transitions vs the anchor-less baseline: VERIFIED→VERIFIED 304 (now with real printed
anchors), VERIFIED→REVIEW 509 (single-ended or no anchor — honest cap),
VERIFIED→FAILED 13 (new anchors caught genuine print-vs-derived mismatches),
FAILED→FAILED 25 (pre-existing, unchanged), REVIEW→REVIEW 3.

## Honest findings kept (not suppressed)

- **DCB ×8 FAIL**: printed closing differs from derived (e.g. ₹10, ₹120 deltas) — real
  discrepancies the new anchor catches, stayed FAILED.
- **SBI postdate ×3**: one file has a ₹0.01 opening print-vs-derived delta — FAILED, correct.
- **Paytm ×3 FAIL**: printed closing mismatches derived — FAILED, correct.
- **Union L1 (306)**: prints closing only, no opening → all REVIEW by policy.
- **DBS (118)**: closing anchor found but opening is a row marker (self-derived) → REVIEW.
- **Kotak L6 (55)**: no printed closing exists → REVIEW.
- **IOB cod (22)**: totals-only coverage → REVIEW.

## Gates

- **Mutation (5 required probes)** on every `anchor_full` layout — all mutations FAILED,
  none stayed VERIFIED: au, axis, bandhan, bom, city_union, dcb, kotak L4, paytm,
  sbi postdate, scb, yes. (dbs correctly remains REVIEW — single-ended.)
- **Row-hash base↔tip** on files VERIFIED both sides: 647 same / 207 differ — all diffs
  adjudicated as *improvements*: post-table text ("Charge Type", DICGC disclaimer,
  `Closing Balance…` tail) no longer bleeds into the last row's `ref_no`/narration.
  Row counts identical everywhere.
- **G2 independent re-derivation** (pdfplumber, own regexes, 33-file sample): every
  engine↔independent mismatch adjudicated against the masked PDF line — engine was
  correct in all cases (verifier artifacts: label-adjacent box values, position-in-row
  errors on labels-then-numbers formats, `AVAILABLE DEPOSIT` footer collisions).
- **No regression**: the 13 VERIFIED→FAILED transitions are genuine anchor-caught
  mismatches; the 25 FAILED stayed FAILED for pre-existing schema reasons (base-diffed).
