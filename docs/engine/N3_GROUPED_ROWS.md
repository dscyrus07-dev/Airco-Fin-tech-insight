# N3 — Date-grouped (sectioned) app statements

Opt-in `LayoutSpec` capabilities added in N3 (`devin/n3-engine-grouped`, base `devin/n2-engine-tables` tip).
All are configuration-driven; none is bank-specific in the engine. Every capability refuses or downgrades
rather than silently accept. Target family: mobile-app exports (Federal/Fi/Jupiter style) where the date
prints once as a section header and the rows beneath carry no date.

## `section_date_re` — date-grouped rows

The statement prints `23Nov` / `1 Dec '22` section headers; transaction rows below inherit the last seen
section date.

- A line qualifies as a section date only when **every word** on it matches `section_date_re` (a date-like
  row with extra words is never eaten as a header).
- Rows created without a repeated date take the pending section date; a row before any section date is a
  defect → `rows_without_section_date` warning → REVIEW (never silently dropped, never dated by guess).
- Page breaks preserve the pending section (continuation pages need no re-printed date).
- `year_from_period` assigns the year that places a yearless section date inside the printed period; when
  the date is boundary-ambiguous (fits either end year), the chronological order of the sections resolves it
  (sections print monotonic). Unresolvable → the raw text stays and normalisation reports it.

## `derive_side_from_balance` — sign-free exports

The export prints one `Amount` column with no `Dr`/`Cr` marker, colour, or sign.

- Each row's side is the direction of the balance move (`bal[i] > base` → credit, else debit).
- The first row derives against the opening anchor — printed opening, else the opening implied by the
  printed identity `closing + debits − credits` when a document summary carries all three. The implied
  value is evidence for side derivation only; `check_reference` still requires a printed anchor, and
  `check_totals` re-verifies the identity against print.
- No derivable base (and no printed-implied opening) → `side_unproven` row warning → REVIEW ceiling.
- A zero-move balance row is also `side_unproven`.

## `doubled_header_glyphs` — app-export header matching

The Fi export prints every header letter twice (`DDaatteeTTrraannssaaccttiioonn...`). When set, doubled
letters are collapsed for header title matching and header spelling-penalty scoring only — row values are
untouched.

## `wrapped_amount_tokens` extensions

- A bare `.dd` decimal-tail fragment is merged onto a previous same-cell amount **even when** that amount
  already matches `amount_re` (integer `1,111` + `.40` → `1,111.40`). Integer amounts are only produced by
  widths — the tail fragment can only be a decimal.
- Same-line fragments: a `.dd` cell adjacent in the same column joins the integer cell on the same row line.

## `summary_truncated` — floored display precision

App summaries display whole-unit (or reduced-precision) figures: `₹693` for a derived 693.67,
`₹124,680.8` for 124,680.80. When set, `check_reference` and `check_totals` compare
`floor(derived, printed_precision) == printed` — the printed precision is read from the printed value's own
scale (trailing-zero-stripped). Counts still compare exactly. A truncated print can never be *more* precise
than the truth, so a fabricated summary still fails.

## `totals_sum_tail` + `doc_counts_re` — multi-bucket totals and printed counts

- `totals_sum_tail`: the summary prints the second metric in several buckets (Fi: `Spent` + `Saved` are both
  outflows). Group 1 of the totals regex is the first metric; every further group is summed into the second.
  `totals_credit_first` still decides which metric is credits.
- `doc_counts_re`: a document-region line carrying printed transaction counts (Fi page-1: `186` incoming /
  `235`+`2` spent+saved). Captured groups feed `check_totals` dr/cr counts; a count-line that sits adjacent
  to a period year is insulated by non-capturing context.

## `period_from_borrows_end_year` — yearless period start

`1 Dec to 31 Dec '22` prints the year only on the end date. When set, `check_period` parses the start by
borrowing the end year; a start month later than the end month wraps to `end_year − 1`
(`1 Dec to 31 Jan '23` → `1 Dec '22`). Unparseable end dates still WARN.

## `ifsc_re` as own-bank evidence

A layout's own IFSC family (`FDRL0[0-9A-Z]{6}`) printed in the page-1 header region counts as own-bank
evidence in `resolve()`. Counterparty IFSCs in the transaction body never reach the header-region text, so
the evidence cannot be faked by a transaction mentioning the bank.

## Anchor scans run on raw pages

`_document_anchors`, page-1 summary scan, and header-region evidence all read the **raw** page text, not the
spec-preprocessed text — so `amount_prefix`/word-level transforms (e.g. stripping `₹` for cell parsing)
cannot destroy `₹`-delimited summary and anchor evidence.

## Files / functions touched

- `extraction/rows.py`: section-date state + `marked=False` fallback scan; `_is_section_date` boundary rule;
  same-line `.dd` fragment merge in cell assignment.
- `extraction/checks.py`: `check_period` (`from_borrows_end_year`), `_matches_printed` truncated compare,
  `check_totals` truncated path, `run_checks` new kwargs.
- `extraction/engine.py`: `_document_anchors` doc totals/counts; raw-pages evidence; implied-opening feed to
  `normalize_rows`; `run_checks` args.
- `extraction/normalize.py`: `derive_side_from_balance` opening-base + `side_unproven` warning.
- `extraction/anchors.py`: `doubled_header_glyphs` token collapse.
- `extraction/registry.py`: `ifsc_re` own-evidence; `_tokens` takes spec.
- `extraction/layout_spec.py` + `spec_codec.py`: 7 new fields, all round-trip.
- `serve.py` + `frontend/lib/statementEngine.ts`: `ROWS_WITHOUT_SECTION_DATE`/`SIDE_UNPROVEN_ROWS` codes.

Specs (shadow-only): `FEDERAL_LAYOUT_4` (doubled-glyph Fi export), `FEDERAL_LAYOUT_5` (single-glyph
`Reference ID` variant, apostrophe-year sections, `₹`-marked cells).
