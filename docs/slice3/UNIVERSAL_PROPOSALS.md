# Proposals for NOT-ALLOWED areas (Universal wave)

Changes I believe are needed in code I may not touch. Nothing here is
implemented in the registered tiers.

## 1. `_region_start` period-marker truncation (extraction/rows.py)

Observed defect (wave-11 audit BLOCKER + ~70 corpus files): a page that
prints dated transaction rows *above* a later period-like line (charge
breakup, repeated statement footer) has `marker_idx` hit first, so
`_region_start` returns `marker_idx + 1` and the rows are silently
dropped. The registered `axis` spec serves 1,141 rows on `000df35f` +
VERIFIED while the true statement has 1,147 (final 11-Jan day missing,
closing balance wrong by ~4,940).

T3 works around it inside its own runtime spec (never-matching
`page_break_re` sentinel + `period_re` in `ignore_line_res`), which
enables the existing "dated rows above the marker → start 0" branch
without touching shared code. The registered axis spec (and any other
spec whose footers re-print a `From To` line below the last rows) needs
the same treatment or a shared fix:

- Either apply the equivalent spec fields to affected registered specs,
- or change `_region_start` so a `marker_idx` with dated rows *above* it
  does not discard them (return 0, or return the first dated index).

Owner: extraction engine / registered specs (Claude). Evidence: u3a
records — ~50 axis + ~19 kotak files where T3 reads strictly-more rows
with intact balance chains; axis `13c2b5f5` base 24 vs true 46.

## 2. `opening_row_balance_only` under single-amount columns

`balance_only_first` (engine.py) checks `amounts.get(spec.debit_column)`
/`credit_column` — under `single_amount_column` those names are virtual
and never present, so row 0 always qualifies as an opening row and is
popped silently. Any future registered spec using single-amount columns
hits the same first-row loss. Suggest the check consult
`spec.single_amount_column` too. (T3's infer now leaves the flag off for
single-amount layouts — same fix pattern.)

## 3. Corpus relabel

`Non_Bank_Documents` contains ≥20 real bank statements (Andhra/"DETAILS
OF STATEMENT" family, BoB-format, IndusInd, Indian-Bank-style); the BoB
spec VERIFIEDs at least one (`c04ec323`). `Bank of Baroda` folder holds a
Union statement (`011c584c` per wave-11 audit). Relabel before the next
negative-set measurement.
