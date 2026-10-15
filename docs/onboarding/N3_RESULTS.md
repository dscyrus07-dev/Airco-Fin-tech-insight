# N3 — date-grouped app statements (Federal family)

Branch `devin/n3-engine-grouped`, base `devin/n2-engine-tables` tip `edd3e36` (engine `f8828a0`).
Scope: opt-in row-grouping engine model + two new Federal app-export layouts (shadow-only).
Capabilities doc: `docs/engine/N3_GROUPED_ROWS.md`.

## Family study (generic labels only)

Two Federal app-export families (Fi/Jupiter partnership) account for the `no_layout` bulk:

- **A — doubled glyphs** (`DDaatteeTTrraannssaaccttiioonn...` headers): section dates `23Nov` /
  `1Dec` (yearless, year comes from the printed period); rows carry `narration + amount + balance`,
  no Dr/Cr anywhere (side derivable only from balance movement); amount integer part and `.dd` tail
  can split across lines; page-1 summary prints truncated whole-rupee figures — `Opening`, `Money in`,
  `Spent`, `Saved`, `Closing` plus transaction counts (`186` in / `235`+`2` out).
- **B — single glyphs**: `Reference ID | Transaction details | Amount | Balance`; section dates
  `1 Dec '22` (apostrophe year); `₹`-prefixed money cells; page-1 summary prints `Money out /
  Money in / Closing balance` labels on one line and the bare `₹...₹...₹...` values on the next;
  no printed opening — the opening is implied by `closing + out − in`. Period prints `1 Dec to
  31 Dec '22` (year on the end date only).

Both families print `FDRL...` IFSC + `FEDERAL BANK` ownership evidence on page 1.

## Engine capabilities added (all opt-in, all refuse/downgrade rather than guess)

| Field | Behaviour |
|---|---|
| `section_date_re` | a bare line fully matching the section shape sets the pending date; undated rows inherit it; a row before any section date → `rows_without_section_date` warning → REVIEW |
| `derive_side_from_balance` | side = direction of balance move; row 0 derives off the printed opening, else the opening implied by printed `closing + debits − credits`; no base → `side_unproven` warning → REVIEW |
| `doubled_header_glyphs` | collapse doubled letters for header matching/scoring only |
| `wrapped_amount_tokens` (ext.) | `.dd` tails join integer cells same-line and cross-line |
| `summary_truncated` | reference/totals compare `floor(derived, printed_precision) == printed`; counts exact |
| `totals_sum_tail` | totals regex group 1 = first metric, remaining groups sum into the second (Spent+Saved) |
| `doc_counts_re` | document-region printed transaction counts feed `check_totals` |
| `period_from_borrows_end_year` | yearless period start borrows the end year (month wrap to `end−1`) |
| `ifsc_re` (wiring) | own IFSC family in the page-1 header region counts as own-bank evidence |

Anchor/summary scans prefer the **prepared** page text (pre-N3 semantics) and fall back to the
**raw** text only for regexes that found nothing — specs whose regexes key on `₹` delimiters work
while every pre-existing spec keeps its prepared-text matches.

## Federal re-measure (343 readable files; the 51 locked files stay uncounted)

| Route | before | after |
|---|---|---|
| v2 VERIFIED | 130 | **228** |
| v2 REVIEW | 36 | 36 |
| v2 FAILED | 13 | 13 |
| fallback | 113 | **15** |
| unsupported | 52 | 52 |

+98 VERIFIED conversions (50 on `FEDERAL_LAYOUT_4`, 48 on `FEDERAL_LAYOUT_5`), zero new REVIEW/FAILED.

### Residual fallback (15) — clusters

| Cluster | sha8s | Cause |
|---|---|---|
| No bank evidence | `045e78cc`, `0adeee02`, `25c793d8`, `2d0ef811`, `3204c326`, `5613f862`, `60109103`, `94afd26b`, `b0a00ada`, `c52e43b6`, `d488730a`, `dafdba24` | detector `UNKNOWN`:0 — unbranded/scanned exports; evidence-gated fallback is the correct outcome |
| Branch-printed variant | `a18ccc97` (142pp) | classic Federal layout whose header doesn't match L1–L5 — next-round candidate |
| Account-info cover | `b491d230` (1p) | Jupiter partnership account details page, no transaction table |
| Zero-transaction export | `a32f18d3` | "not made any transactions on Fi between 1 December 2023 to 1 December 2023" — empty statement |

## Cross-check on other folders' no_layout (yes, equitas_sfb, csb, kotak)

Section-date signature (`bare date line` ≥3 on first pages): **0 hits** in any other folder's
fallback set. Doubled-letter noise without section dates is not the family and lacks bank evidence.
No other bank's file was claimed — the two new layouts require Federal detection + `FDRL` evidence.

## Safety

- **Regression**: 734/734 files vs N2 tip — **1 diff**: `ed04dc45` (hdfc) `fallback:foreign_bank` →
  `v2 VERIFIED`. Verified legitimate: own `RTGS/NEFT IFSC: HDFC0009086` prints in the header region
  and `HDFC BANK LIMITED` in the furniture; the "foreign" marker was an `AXIS BANK ATM` counterparty
  descriptor. The `ifsc_re` own-evidence rule rescued a genuine own-bank document.
- **CSB misfiles**: all 8 Federal documents misfiled under `CSB Bank/` still route to a Federal
  layout (REVIEW) — unchanged.
- **Audit** (`audit2.py`, spec-independent): 98 VERIFIED files — chain breaks 0 in every file.
  Auditor flags are structural to the family, not defects: `rows>dated_lines` (dates print once per
  section), `close/open_anchor_mismatch` (generic label scan can't read the app summary's bare-value
  lines / truncated display; L5 prints no opening at all), `no_printed_anchors_found` (same cause).
  Engine VERIFIED rests on spec-matched printed anchors + totals + counts + chain — all independent
  of extraction.
- **Tests**: `tests/statement_engine` 493 pass; `test_n3_grouped_rows.py` 21 tests (section
  inheritance, page-break loss, duplicate sections, date-like rows, doubled headers, wrapped tails,
  truncated summary, boundary-year resolution, period year-borrow, implied opening, mutations).
- Registry codec round-trips every new field.

## Risks / parked

- Federal residual `a18ccc97` branch-printed variant — likely a further L1-family layout tweak.
- Empty-export statements (`a32f18d3`) have no table to verify — decide later whether an explicit
  "empty statement" outcome is wanted; they currently fall back.
- `derive_side_from_balance` remains unsafe for VERIFIED without an anchor or totals+closing;
  `side_unproven` keeps those at REVIEW by design.
- Truncated summaries compare at printed precision — a file whose summary precision exceeds the
  family's (forged extra decimals) would fail honestly.

## Files / functions touched

- `extraction/rows.py`: section-date state, `marked=False` fallback scan, `_is_section_date`,
  same-line `.dd` fragment merge.
- `extraction/checks.py`: `check_period` (`from_borrows_end_year` + wrap), `_matches_printed`
  truncated compare, `check_totals` truncated path, `run_checks` kwargs.
- `extraction/engine.py`: `raw_pages` retention, `_document_anchors(_scan)` prepared-then-raw,
  doc totals/counts, implied-opening feed to `normalize_rows`, `run_checks` args.
- `extraction/normalize.py`: `derive_side_from_balance` opening-base, `side_unproven`.
- `extraction/anchors.py`: doubled-glyph token collapse (`_tokens`).
- `extraction/registry.py`: `ifsc_re` own-evidence, `_tokens` spec arg.
- `extraction/layout_spec.py`, `spec_codec.py`: `section_date_re`, `derive_side_from_balance`,
  `doubled_header_glyphs`, `summary_truncated`, `totals_sum_tail`, `period_from_borrows_end_year`,
  `doc_counts_re` — all serialized round-trip.
- `serve.py` + `frontend/lib/statementEngine.ts`: `SECTION_DATE_MISSING` review code + label.
- `extractors/federal/layout_spec.py`: `FEDERAL_LAYOUT_4`, `FEDERAL_LAYOUT_5` (shadow-only);
  `extractors/registry.py` registration.
- `tools/onboarding/synth/table_shapes.py`: `grouped_statement` generator.
- `tests/statement_engine/extraction/test_n3_grouped_rows.py`: 21 tests.
