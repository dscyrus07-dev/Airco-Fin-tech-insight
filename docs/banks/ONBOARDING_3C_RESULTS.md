# Slice 3C - bank onboarding results (author's own probe, NOT yet independently validated)

Same engine, one `LayoutSpec` per layout. Numbers come from running each layout over the files of its header
fingerprint in the layout census (150 files per bank folder). "VERIFIED" = every independent check passed. Chain-only
means the layout prints no summary or opening/closing reference, so the verdict rests on the balance chain, side,
schema and date checks. Independent validation (Devin) is the next step; treat everything here as a claim to falsify.

| Bank | Layouts | Probe result (dominant fingerprint) | Notes |
|---|---|---|---|
| HDFC | A (existing) | unchanged vs 3A on a 42-file sample (verdict, row count, comparator class) | regression gate for every engine change |
| SBI | 1 | 83 VERIFIED, 3 REVIEW of 86 (multi-statement PDFs merged where tails overlap; true gaps stay REVIEW) | no printed summary |
| Canara | 1 | L1 75/98 VERIFIED, 5 REVIEW, rest FAILED/refused | the former "layout 2" (date, mode, particulars, deposits, withdrawals, balance) is ICICI's older layout and now lives under ICICI |
| Axis | 1 | 96 of 97 VERIFIED, 1 FAILED (printed 1.73 chain gap) | also verifies Paytm-folder files of the same layout |
| IDFC | 1 (3 header variants) | 110 VERIFIED, 1 REVIEW, 1 FAILED of 140 | FAILED: printed totals differ by 594,476.00 on both sides |
| Kotak | 1, 2, 3 | L1: 50 VERIFIED, 17 REVIEW (multi-statement PDFs), 2 empty of 69. L3 (dd-Mon-yy): 3 of 7 VERIFIED, 2 REVIEW. L2 (dd-mm-yyyy): 1 file, FAILED (split date cell) | L2/L3 need more files before any claim |
| Federal | 1 | 48 of 50 VERIFIED | other Federal fingerprints refused, not onboarded |
| Bank of Baroda | 1, 2 | L1: 64 VERIFIED, 1 REVIEW, 1 FAILED of 66. L2: 14 of 21 | L2 failures: dated rows above the table |
| ICICI | 1, 2 | L1 21 of 23 VERIFIED (chain-only), 2 empty statements; L2 (older layout, moved from Canara) 23/29 own-probe | date column is the Transaction Date (a value-date column sits left of it) |
| Union | 1 | 57 of 57 VERIFIED | single Dr/Cr amount column, newest row first |
| Paytm | 1 | 43 of 43 VERIFIED | single signed amount column |

11 banks, 18 layouts. Registry: `LayoutRegistry.resolve` anchors a header to its bank and refuses ambiguity (see below). Not onboarded (header fingerprints are refused rather than guessed): headerless variants, other
Federal / ICICI / Paytm / Union fingerprints, banks outside the census.

## What the engine needed (cumulative; all optional spec fields, defaults keep the old behaviour)
`totals_line_re`, `continuation_start`, trailing-column drop, `summary_position`, bracketed negatives,
`opening_row_marker`, `closing_row_marker`, `sign_is_decoration`, `^`/`=` anchored end markers, Cr/Dr balance suffix,
fused-date splitting, leading cover pages, `band_left_pad`, `page_footer_markers`, `merge_drcr_suffix`,
`single_amount_column`, `row_order`, `zero_amount_is_empty`, `amount_prefix`, `merge_sign_prefix`,
`dated_rows_after_end_ok`, `merge_statements`, `monospace_text`, `page_break_re`, `opening_row_balance_only`. Engine diff since SBI/Canara: about 200 added lines for eight further banks; each new spec
is 38-85 lines of configuration.

## Known limits
- A PDF holding several statements returns the first and is REVIEW (Kotak).
- Chain-only layouts (ICICI, SBI, Paytm) cannot detect a wrong opening balance.
- Reverse-order (Union) rows are returned oldest-first.
- A date cell wrapped across a page boundary, or split above the header line, is not recovered (FAILED, not guessed).
- A regression was found and fixed by re-running HDFC: the date-prefix split cut inside a four-digit year. A test now
  guards it.

## Registry resolution (after Devin 3C)
Devin's 3C run proved that header-only detection is not safe: a header shared by two banks was accepted under whichever
was registered first (467 ICICI statements verified as Canara; Kotak L2 shadowing Kotak L3 and BoB L2). `resolve` now:
1. header match; 2. refuses a candidate when the text above the table names another registered bank and not its own
(a page naming no bank is not refused); 3. ranks by own bank named, header titles closest to the primary spellings, date
cells in the layout's own date shape, column count; 4. returns no layout (`ambiguous`) when different banks tie.
Sample resolution (random 60-70 files per folder, first 3 pages): Canara folder 36 own + 2 ICICI-older (correctly
re-attributed); ICICI folder 30 own, 3 HDFC; BoB folder 47 own (11 on layout 2, previously shadowed); Axis folder 7 ICICI
statements re-attributed. Still open: statements whose header is shared and whose page names no bank stay ambiguous.
