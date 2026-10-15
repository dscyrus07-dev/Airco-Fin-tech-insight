# N2 results — table-shape capabilities, per bank

Base `c352a25` (N1 tip, engine `8e75997`), branch `devin/n2-engine-tables`. All measures shadow-mode
(`measure2.py`), same sha8 lists before/after. Nothing promoted; every new layout stays shadow-only.
Capability documentation: `docs/engine/N2_TABLE_CAPABILITIES.md`.

## Totals (same file sets)

| Bank | Files | v2 before → after | VERIFIED | REVIEW | FAILED | fallback | unsupported |
|---|---|---|---|---|---|---|---|
| dcb | 16 | 15 → 15 | 7 → 7 | 0 → 0 | 8 → 8 | 0 → 0 | 1 → 1 |
| dbs | 137 | 120 → **127** | 110 → **116** | 4 → 11 | 6 → **0** | 12 → **5** | 5 → 5 |
| bank_of_maharashtra | 30 | 26 → 26 | 21 → **25** | 5 → **1** | 0 → 0 | 1 → 1 | 3 → 3 |
| uco | 9 | 9 → 9 | 0 → 0 | 3 → 3 | 6 → 6 | 0 → 0 | 0 → 0 |
| hsbc | 91 | 22 → **31** | 0 → 0 | 22 → 22 | 0 → 9 | 12 → **3** | 57 → 57 |
| dhanlaxmi | 11 | 4 → **9** | 0 → 0 | 4 → **9** | 0 → 0 | 7 → **2** | 0 → 0 |
| idbi | 104 | 68 → 68 | 17 → 17 | 22 → 22 | 29 → 29 | 26 → 26 | 10 → 10 |
| equitas_sfb | 40 | 32 → 32 | 4 → 4 | 23 → 23 | 5 → 5 | 4 → 4 | 4 → 4 |

The only regression diffs on the full 734-file corpus are the 4 bom REVIEW→VERIFIED promotions below —
the named expected change, all audit-clean.

## Per bank

### bank_of_maharashtra — `anchor_scan="document"` (mid-document summary anchors)

- `anchor_scan="document"` + count-bearing segment summary (`Total Transaction Count`, per-account
  `Opening/Closing Balance` blocks between tables).
- 4 of the 5 waiting REVIEWs promote to **VERIFIED**: `1511f656` (290 rows), `0ea90a40` (289),
  `76bb6cd2` (635), `c499d608` (813). Row counts unchanged — only the evidence tier improved.
- `6f062db1` stays REVIEW (honest date-order finding, unrelated to anchors).
- Independent audit (`audit2.py`, generic label scan — not the spec's regexes): 4/4 clean —
  0 flags, 0 chain breaks, dated-amount lines == rows read, implied open/close match printed anchors.

### dbs — `DBS_LAYOUT_3` (balance-less sandwich) + `DBS_LAYOUT_1.segment_header_re` (multi-account)

- Balance-less variant (`DATE DETAILS OF TRANSACTION DEBIT CREDIT`, narration/amount/narration
  3-line record): `no_running_balance` + `leading_narration` — 9 files extract (66–850 rows) as
  REVIEW + `NO_RUNNING_BALANCE`. Never VERIFIED by construction.
- Multi-account exports: `Account No.` blocks open segments; per-segment opening/closing become
  tagged `pre`/`post` checkpoints; per-segment chains + printed transaction counts verify.
  All 6 previously-FAILED multi-account files (`2cce319e`, `6d986d74`, `ac939c61`, `e22fdd6a`,
  `e7494071`, `fa24a579`) → **VERIFIED** with dense segment ids `[0, 1]`.
- Net: VERIFIED 110→116, FAILED 6→0, fallback 12→5 (5 = postpaid/non-statement docs).

### dcb — per-segment printed counts + turnover totals

- `segment_header_re` (account blocks), `segment_count_re` reads the printed
  `Total Number of Transactions`-style pairs (debit count + credit count summed), `totals_line_re`
  reads `Turnover DR CR`.
- Counts + turnover verify on all 15 v2-routed files. The 8 FAILEDs are document-inconsistent:
  extraction is complete (counts and turnover pass), but the bank's printed closing contradicts its
  own table's running balance (e.g. closing `50.88` vs final row `0.88` — exactly one transaction off).
  Honest FAILED retained.

### dhanlaxmi — `DHANLAXMI_LAYOUT_2` (fp-A: amount-above-date + inline `Balance :`)

- `leading_amounts` (narration + `amount Dr/Cr` lines print ABOVE the dated line), `balance_inline_re`
  (`Balance : X` lines, incl. word-level when PDF grouping glues them onto dated lines),
  `chain_reorder_same_date` (bank prints same-date rows out of balance order).
- All fp-A files (`26a5b02e`, `e426952c`, `2fae0724`, …): fallback → REVIEW, schema clean.
  Reorderable windows explain every chain break → WARN + `SAME_DATE_DISORDER`, never VERIFIED.

### idbi — `IDBI_LAYOUT_6` (balance-less `Date | Description | Amount | Type`)

- Amount prints on a continuation line; `DR`/`CR` on the dated line → `continuation_amounts` +
  `pending_side` + `no_running_balance`.
- Direct extraction verified: 196 rows, REVIEW + `NO_RUNNING_BALANCE`, schema clean.
- Routing note: these exports carry **no bank-identifying text at all** (no `IDBI`, no IFSC) —
  detector returns `bank_unconfirmed`, so files correctly stay fallback. Evidence-gated detection
  is working as designed; not an engine gap.

### hsbc — `HSBC_LAYOUT_2` (UK variant, partial)

- Sparse in-column balances (`balance_optional`), `BROUGHT/CARRIED FORWARD` checkpoints
  (`balance_checkpoint_re`), label-first `Account Summary` anchors (`anchor_scan="document"`).
- 9 files now route v2 and produce honest FAILED: the variant prints **undated date-grouped
  sub-rows** (a dated header row followed by undated transaction lines) — interleaved
  date-group extraction is N3 scope. Fallback 12→3; extraction + anchors verified where dated.

### uco — no spec change

- 6 FAILEDs re-inspected: document-inconsistent (printed closing contradicts the bank's own
  summary arithmetic, e.g. `1.37` vs computed `221.37`). Honest FAILED retained; 3 REVIEW unchanged.

### equitas_sfb — parked (N3)

- The single-amount family that was expected to be N2 turns out to be an **interleaved-wrap**
  layout: narration cells overlap the next record's lines — N3 territory, parked.
- The 5 FAILEDs are genuine print inconsistencies (rows reconcile neither pairwise nor under
  reorder). Honest FAILED retained.

## Parked / N3

- HSBC UK undated date-grouped sub-rows (needs date-context inheritance across undated lines).
- Equitas interleaved-wrap family (narration cells overlap adjacent records).
- idbi balance-less family waits on detection evidence only — layout verified, bank markers absent
  in the exports themselves.

## Regression & safety

- **734-file corpus compare vs N1-tip baseline: 4 diffs** — all `bank_of_maharashtra`
  REVIEW→VERIFIED (the named expected change; all 4 audit-clean per above). No other status,
  layout, verdict, or row-count change anywhere in the corpus.
- Engine unit suite: **472 passed**. N2 capability + mutation tests: **26 passed**
  (`tests/statement_engine/extraction/test_n2_table_caps.py`; synth generators in
  `tools/onboarding/synth/table_shapes.py`).
- Cross-bank: the 734-file compare itself proves no foreign accepts — only the 4 bom files changed.
- Marker audit: short IFSC-shaped markers `DLXB`/`HBUK` removed from new specs; registry
  round-trip test green (regex flags serialized via inline `(?i)` where needed).
- New review codes wired end-to-end (`serve.py` → `statementEngine.ts` labels):
  `NO_RUNNING_BALANCE`, `SAME_DATE_DISORDER`, `CHECKPOINT_MISMATCH`, `BALANCE_DELTA_MISMATCH`,
  `SEGMENT_COUNT_MISMATCH`.

## Every engine file/function touched

- `extraction/layout_spec.py`: `no_running_balance`, `segment_header_re`, `segment_count_re`,
  `anchor_scan`, `balance_checkpoint_re`, `balance_inline_re`, `balance_optional`,
  `leading_amounts`, `leading_narration`, `continuation_amounts`, `chain_reorder_same_date`,
  `single_amount_default_side` (+ validation; `balance_column` optional when `balance_inline_re`).
- `extraction/spec_codec.py`: round-trip for all new fields.
- `extraction/anchors.py`: `classify_word` — money check before mid-band return; last-text-column
  guard exempts declared trailing columns right of the money edge.
- `extraction/rows.py`: `RawRow.segment`/`pending_side`; `assemble()` — segment headers, pre-start
  segment scan, tagged checkpoints, in-break count capture, inline balances, leading/pending-cell
  buffers, blank-amount drop, dense segment renumbering, `- 1,234.56 Cr` glued-token recovery.
- `extraction/normalize.py`: `NormalizedRow.segment`, balance-less normalize, default-side fill.
- `extraction/checks.py`: `check_chain` (sparse-balance deltas, `_same_date_repair` bounded DFS),
  `check_segments`, `check_checkpoints` (3-tuples, pre/post, segment-start openings),
  `check_delta`, `check_dates`/`check_date_outliers` segment resets, `decide` (soft reasons always
  computed, `NO_RUNNING_BALANCE` cap, `SAME_DATE_DISORDER`).
- `extraction/engine.py`: `_document_anchors`, document-scan wiring, `_checkpoint_amounts`,
  `run_checks` args, `derive` sparse-balance flows.
- `extraction/pdf_extractor.py`: extras expose new check details.
- `serve.py` + `frontend/lib/statementEngine.ts`: new review codes and labels.
- Specs: `DBS_LAYOUT_3`, `IDBI_LAYOUT_6`, `DHANLAXMI_LAYOUT_2`, `HSBC_LAYOUT_2`, dcb
  count/turnover fields, `DBS_LAYOUT_1.segment_header_re`; `registry.py` registrations.
- Tests/tools: `test_n2_table_caps.py` (26), `tools/onboarding/synth/table_shapes.py`.
