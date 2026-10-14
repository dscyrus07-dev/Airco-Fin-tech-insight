# N2 — Table-shape capabilities

Opt-in `LayoutSpec` capabilities added in N2 (`devin/n2-engine-tables`). All are configuration-driven; none is
bank-specific in the engine. Every capability refuses or downgrades rather than silently accept.

## `no_running_balance: bool = False`

The statement prints a single amount column with a `Dr`/`Cr` side marker but no running balance. The balance
chain cannot engage, so:

- `check_chain`/`check_side` return SKIPPED; `balance_column=""` is legal and is dropped from `amount_columns`.
- `decide()` caps the outcome at REVIEW with reason `NO_RUNNING_BALANCE` — never VERIFIED.
- Completeness evidence still runs: page-level unread-transaction scan, printed totals (`totals_line_re`) and
  printed per-segment counts where present.
- Review code `NO_RUNNING_BALANCE` (`serve.py`) → UI label in `statementEngine.ts`.

## `segment_header_re` / `segment_count_re` — per-account sub-tables

Multi-account exports reprint an account block (`Account No.: …`, `Total Number of Transactions …`) between
account tables.

- `segment_header_re` opens a new segment; rows carry `segment` (0-based dense ids — a preamble before the first
  block never appears in output).
- `segment_count_re` matches a printed count line; trailing integer words are read and, when two counts print
  (debit count + credit count), their sum is the segment count (side counts also recorded).
- `check_segments` compares printed counts against extracted rows per segment: FAIL → verdict cannot pass;
  WARN → REVIEW with `SEGMENT_COUNT_MISMATCH`.
- `check_chain`, `check_dates`, `check_date_outliers` reset at segment boundaries.
- Repeated headers inside the scan are skipped (`find_header` on each line) when `segment_header_re` is set.
- Account blocks that sit ABOVE a repeated header (page-top) are registered by a pre-scan pass so the segment
  still opens.

## `anchor_scan = "document"` — whole-document anchors

Default remains edge scan (page 1 opening / last page closing). `"document"` scans every page for the layout's
`opening_balance_re`/`closing_balance_re`/`totals_line_re`:

- First opening and last closing in statement order are used.
- Two distinct printed openings/closings → `anchor_conflict:*` warning → REVIEW (never silently pick).
- Multi-segment documents (`segment_header_re` set) legitimately print one opening/closing per segment; conflicts
  are NOT raised there — per-segment values are verified as checkpoints instead.
- Conflicts against the parsed summary block also warn.

## Non-row balance prints

- `balance_checkpoint_re` — a printed "balance carried/brought forward"-style line asserts the running balance
  at that row boundary. Same-boundary prints must agree. Tagged checkpoints (`"pre"` = segment opening asserts the
  next row's implied balance; `"post"` = segment closing asserts the chain's exit balance) come from
  `opening_balance_re`/`closing_balance_re` lines inside the table region when `segment_header_re` is set.
- `balance_inline_re` — a `Balance : X` continuation line attaches to the current row, incl. when PDF grouping
  glues it onto the dated line (word-level match). Layouts whose balance only exists inline are exempt from the
  balance-title requirement and `balance_column` is dropped from `amount_columns`.
- `balance_optional` — sparse in-column balance prints (checkpoint-style) where most rows carry no balance;
  chain verifies long-range deltas between consecutive balance-bearing rows; derive computes opening/closing
  through flows.

## Row-shape capabilities used here

- `leading_amounts` — record's amount (and narration) lines print ABOVE the dated line; non-dated lines ending
  at a dated line buffer as full cell dicts and merge into the row. A trailing `- 12,345.67 Cr` token glued into
  a text word is recovered from the raw line text.
- `leading_narration` — narration-only prefix lines above the dated line (three-line record "sandwich").
- Scan start walks back over leading lines (bounded to 3 for `leading_amounts`) so page-boundary records keep
  their prefixes.
- `continuation_amounts` + `pending_side` — a `Dr`/`Cr` marker in `side_marker_column` on the dated line is
  stashed until the amount arrives on a continuation line.
- `chain_reorder_same_date` — some banks print same-date rows out of balance order; when every chain/side break
  is provably explained by a reorderable same-date window (bounded DFS over `balance - cur == flow`), the checks
  downgrade FAIL→WARN → REVIEW with `SAME_DATE_DISORDER`. Never VERIFIED on reordered evidence.

## classify_word fixes

- A money-shaped word inside a middle text band still reaches its money column when its right edge aligns
  (single-amount exports flank the amount column with text columns).
- The trailing-column guard no longer drops words when the layout's last text column legitimately sits right of
  the money columns (e.g. a `Type` column holding DR/CR).

## Files / functions touched

- `extraction/rows.py`: `RawRow.segment`, `pending_side`; `assemble()` — segment headers, tagged checkpoints,
  segment counts inside page breaks, inline balances, `leading_amounts`/`leading_narration` buffers, pre-header
  segment scan, dense segment renumbering, blank amount cells.
- `extraction/checks.py`: `check_chain` (+`_same_date_repair`, sparse-balance deltas), `check_segments`,
  `check_checkpoints` (3-tuples, pre/post, seg-start openings), `check_delta`, `check_dates`/`check_date_outliers`
  segment resets, `decide` (always-computed soft reasons, NO_RUNNING_BALANCE cap, SAME_DATE_DISORDER reason).
- `extraction/anchors.py`: `classify_word` (mid-band amounts, trailing-column exemption).
- `extraction/engine.py`: `_document_anchors`, anchor-scan wiring, `_checkpoint_amounts`, run_checks args,
  `balance_optional`/`derive` sparse handling.
- `extraction/normalize.py`: `NormalizedRow.segment`, `single_amount_default_side`, balance-less normalization.
- `extraction/layout_spec.py` + `spec_codec.py`: all new fields round-trip.
- `extraction/pdf_extractor.py`: extras expose `same_date_disorder`/`segments`/`mismatched` check details.
- `serve.py`: `SAME_DATE_DISORDER` code; `frontend/lib/statementEngine.ts`: label.

Specs (registered, shadow-only where marked): `DBS_LAYOUT_3` (balance-less sandwich), `IDBI_LAYOUT_6`
(balance-less `Date|Description|Amount|Type`), `DHANLAXMI_LAYOUT_2` (fp-A: leading amounts + inline balance +
same-date reorder), DCB counts/turnover fields, `DBS_LAYOUT_1.segment_header_re` (multi-account),
`HSBC_LAYOUT_2` (UK variant, partial — see N2_RESULTS).
