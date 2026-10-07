# Slice 3C - bank onboarding results (author's own probe, NOT yet independently validated)

Same engine, one `LayoutSpec` per layout. Numbers come from running each layout over the files of its header
fingerprint in the layout census (150 files per bank folder). "VERIFIED" = every independent check passed. Chain-only
means the layout prints no summary or opening/closing reference, so the verdict rests on the balance chain, side,
schema and date checks. Independent validation (Devin) is the next step; treat everything here as a claim to falsify.

| Bank | Layouts | Probe result (dominant fingerprint) | Notes |
|---|---|---|---|
| HDFC | A (existing) | unchanged vs 3A on a 42-file sample (verdict, row count, comparator class) | regression gate for every engine change |
| SBI | 1 | 83 VERIFIED, 3 REVIEW of 86 (multi-statement PDFs merged where tails overlap; true gaps stay REVIEW) | no printed summary |
| Canara | 1, 2 (mode column) | L1 76 VERIFIED, 5 REVIEW, 2 FAILED of the 83 files that carry its header; L2 23 of 29 | L2 failures are tail rows after the statement |
| Axis | 1 | 96 of 97 VERIFIED, 1 FAILED (printed 1.73 chain gap) | also verifies Paytm-folder files of the same layout |
| IDFC | 1 (3 header variants) | 110 VERIFIED, 1 REVIEW, 1 FAILED of 140 | FAILED: printed totals differ by 594,476.00 on both sides |
| Kotak | 1, 2, 3 | L1: 50 VERIFIED, 17 REVIEW (multi-statement PDFs), 2 empty of 69. L3 (dd-Mon-yy): 3 of 7 VERIFIED, 2 REVIEW. L2 (dd-mm-yyyy): 1 file, FAILED (split date cell) | L2/L3 need more files before any claim |
| Federal | 1 | 48 of 50 VERIFIED | other Federal fingerprints refused, not onboarded |
| Bank of Baroda | 1, 2 | L1: 64 VERIFIED, 1 REVIEW, 1 FAILED of 66. L2: 14 of 21 | L2 failures: dated rows above the table |
| ICICI | 1 | 21 of 23 VERIFIED (chain-only), 2 empty statements | |
| Union | 1 | 57 of 57 VERIFIED | single Dr/Cr amount column, newest row first |
| Paytm | 1 | 43 of 43 VERIFIED | single signed amount column |

11 banks, 17 layouts. Not onboarded (header fingerprints are refused rather than guessed): headerless variants, other
Federal / ICICI / Paytm / Union fingerprints, banks outside the census.

## What the engine needed (cumulative; all optional spec fields, defaults keep the old behaviour)
`totals_line_re`, `continuation_start`, trailing-column drop, `summary_position`, bracketed negatives,
`opening_row_marker`, `closing_row_marker`, `sign_is_decoration`, `^`/`=` anchored end markers, Cr/Dr balance suffix,
fused-date splitting, leading cover pages, `band_left_pad`, `page_footer_markers`, `merge_drcr_suffix`,
`single_amount_column`, `row_order`, `zero_amount_is_empty`, `amount_prefix`, `merge_sign_prefix`,
`dated_rows_after_end_ok`, `merge_statements`. Engine diff since SBI/Canara: about 200 added lines for eight further banks; each new spec
is 38-85 lines of configuration.

## Known limits
- A PDF holding several statements returns the first and is REVIEW (Kotak).
- Chain-only layouts (ICICI, SBI, Paytm) cannot detect a wrong opening balance.
- Reverse-order (Union) rows are returned oldest-first.
- A date cell wrapped across a page boundary, or split above the header line, is not recovered (FAILED, not guessed).
- A regression was found and fixed by re-running HDFC: the date-prefix split cut inside a four-digit year. A test now
  guards it.
