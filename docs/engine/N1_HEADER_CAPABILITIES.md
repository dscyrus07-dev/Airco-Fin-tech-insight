# N1 — Header & marker capabilities (engine, branch `devin/n1-engine-headers`)

Base: `5be615d` (tip of `integration/v2-waves`, contains `411f6ca`). All fields
opt-in; defaults reproduce prior behaviour exactly (regression: 734 files, 0 diffs).

## Capabilities

### 1. Period-suffixed side markers
`SIDE_MARKER_RE` in `extraction/normalize.py` now accepts an optional trailing
period: `Dr.` `Cr.` `DR.` `CR.` (and the bare/parenthesised forms as before).
Same constant reused at the two normalize call sites; `rows.py` marker pickup and
`engine.py::_merge_drcr_suffix` updated identically.

- Rule: the marker must terminate the cell (`\(?(cr|dr)\)?\.?$`), case-insensitive.
- Derived from: `idbi` folder sha8s incl. `1f8ffc2f` (19-file `Dr.`/`Cr.` family,
  `IDBI_LAYOUT_3`).

### 2. Multi-line header assembly — `header_lines: int`, `header_merge_tol: float`
`find_header` merges up to `header_lines` adjacent visual lines into one stream
(`_merge_header_lines`): words cluster by horizontal overlap (a word joins the
cluster when its `x0` ≤ cluster right edge + `header_merge_tol`); each cluster
emits fragments top-to-bottom. `n=2..header_lines` windows are tried per line.

- Tolerance default `4.0`pt — mid-word split fragments sit ~2–4pt apart; real
  column gaps observed ≥6pt. A spec may widen it.
- Refusal unchanged: the merged view must complete the column set and contain no
  unknown token inside the span (`_complete`, centre-test).
- The old `header_wraps` restriction (date title must be on the first line) does
  not apply to this path — the date fragment may sit on any merged line.
- `_find_sequence` hit span is now `min(x0)..max(x1)` over the matched tokens:
  wrapped fragments can print left of the last token (mid-word splits).
- `date_join_words` (opt-in): date cells printed as several same-line words
  ("08 Aug 2021") join before parsing — same convention as secondary dates.
- Derived from: `yes` `008a966b` (3-line interleaved), `central_bank` `459f15b8`
  (15 columns, mid-word splits), `pnb` landscape `f2be0893`/`e30390d8`/`8b2cd533`
  (3-line) and `e392125a`/`42840c0c` (2-line), `idbi` L3 (fragments above+below).

### 3. Untitled leading date column — `untitled_date_column: bool`
When a line completes every declared column except `date` with nothing left of
the first title (`_complete_without_date`), the date span is read from data rows
(`_find_untitled_date`): the left-of-title zone is clustered by x; exactly one
cluster may qualify — every member cell must match `spec.date_re`, on ≥2 lines.
The probe stops at the first zone-line with no date-shaped cell, so footers /
summary blocks cannot poison or fake membership.

- Refuses when 0 or ≥2 candidate clusters exist (ambiguous).
- Mutually exclusive with `implicit_header` (validated in `LayoutSpec.validate`).

### 4. `period_date_format` `|`-alternates fix
`checks.parse_period_date` iterates `period_format.split("|")` (same convention
as `normalize.parse_date`); `engine._add_years` uses it too. Previously a `|`
format reached `datetime.strptime` verbatim and crashed.

## Parked

- **`implicit_header` absent-column robustness** — `_implicit_row_match` already
  tolerates a missing *narration* token on the anchor line. Extending to arbitrary
  absent columns requires deciding which role each remaining token binds to; with
  two absent columns the alignment is ambiguous without anchors, and a wrong guess
  would silently mis-bin money cells. No cheap safe version inside the time box.

## Failure-injection battery (tests: `test_n1_header_caps.py`, 27 tests)

Per capability spec (synthetic) plus every new registered family:
dropped row · swapped debit/credit · changed amount · missing page · truncated
final page · extra unknown column mid-header — none may end `VERIFIED`.
Refusal tests: unknown token inside merged span, two-candidate untitled date,
`header_lines=2` cannot bridge a 3-line header, `header_lines=1` unchanged.

Synthetic generators: `tools/onboarding/synth/split_headers.py`
(`two_line_wrap`, `three_line_interleave`, `centred_titles`).

## Limits / risks

- `header_merge_tol` is a per-spec tuning knob; too large merges neighbour
  columns' fragments into one cluster (refusal via unknown-token, but also false
  negatives). Keep ≤ half the smallest real inter-column gap.
- The x-overlap cluster rule is greedy left-to-right; a fragment protruding far
  right of its own title can pull in a neighbour's fragment. `center_test`
  coverage + completeness are the guards.
- `untitled_date_column` trusts date-shape geometry left of the first title;
  a bank whose rows print another date-shaped column there gets refused, not
  mis-parsed.
- FAILED verdicts on real corpus files (redacted `0.00` balance fixtures in the
  idbi L3 set; long pnb files) are honest unreconcilable prints, not extraction
  failures — the chain check is doing its job.

## Touched files & functions

- `extraction/normalize.py`: `SIDE_MARKER_RE` (new const), `_strip_drcr`,
  `parse_amount` (suffix path), `normalize_rows` (single-amount marker path)
- `extraction/rows.py`: side-marker pickup regexes (~lines 244, 266-269),
  `date_join_words` join (~line 226)
- `extraction/engine.py`: `_merge_drcr_suffix` regex, `_add_years` (via
  `parse_period_date`), import
- `extraction/checks.py`: `parse_period_date` (new), `check_period`
- `extraction/anchors.py`: `_find_sequence` (span = min..max), `_merge_header_lines`
  (new), `_find_untitled_date` (new), `_complete_without_date` (new), `find_header`
- `extraction/layout_spec.py`: fields `header_lines`, `header_merge_tol`,
  `date_join_words`, `untitled_date_column` + `validate` rules
- `extraction/spec_codec.py`: serialize/deserialize the four new fields
- `extractors/registry.py`: register 5 candidate layouts
- `extractors/idbi/layout_spec.py`: `IDBI_LAYOUT_3` (registered; comment updated)
- `extractors/yes/layout_spec.py`: `YES_LAYOUT_5` + fused ref-token alternatives
- `extractors/central_bank/layout_spec.py`: `CBI_LAYOUT_4` (15-col)
- `extractors/pnb/layout_spec.py`: `PNB_LAYOUT_2`, `PNB_LAYOUT_3` (+`band_left_pad`)
- `tests/statement_engine/extraction/test_n1_header_caps.py` (new)
- `tests/statement_engine/extraction/test_registry_store_and_router.py`: priority
  constant fix (brittle max assumption)
- `tools/onboarding/synth/{__init__.py,split_headers.py}` (new)
- `tools/onboarding/{geo.py,geo_raw.py}` (sanitized geometry probes)
