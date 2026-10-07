# Headerless and unknown-header files: what they are and what the engine should do

Evidence: the layout census lists 88 text-layer files with no recognised header fingerprint (Union 37, Federal 22,
BoB 17, SBI 12). A structural scan of their first four pages (counting dated lines with two or more amounts, and
header-like lines naming a balance plus a debit/credit word; no content kept) splits them as follows.

| Bank | no table at all | table rows + header-like line | table rows, no header line | header, no rows |
|---|---|---|---|---|
| Union (37) | 34 | 3 | 0 | 0 |
| Federal (22) | 22 | 0 | 0 | 0 |
| BoB (17) | 5 | 10 | 1 | 1 |
| SBI (12) | 2 | 2 | 8 | 0 |

(The scan is a heuristic over four pages, not a verdict; counts are indicative.)

## Reading
1. **No table (Union 34, Federal 22, BoB 5, SBI 2 = 63 of 88).** These are not transaction statements the layouts
   target (account-detail letters, notices, other products). Correct behaviour is what exists today: refuse with
   NO_TABLE_HEADER and let the legacy/generic path decide. Do not add a spec.
2. **Header-like line present, fingerprint unknown (Union 3, BoB 10, SBI 2 = 15).** These are ordinary
   header variants the census failed to fingerprint (wrapped or merged title cells). Onboard like any layout:
   one `LayoutSpec` each, once the real header token sequence is dumped. No engine change expected.
3. **Rows but no header (SBI 8, BoB 1 = 9).** The only genuinely new case: a continuation file or export that begins
   mid-table.

## Policy for case 3 (proposal, not built)
- Never guess columns from nothing. A headerless file may borrow anchors only from a registered layout whose
  column x-positions match the file's own dated-row geometry within a tolerance, chosen by the data, not by bank name.
- The borrowed-anchor result is capped at REVIEW unless the balance chain passes end to end AND sides agree with the
  chain; with no opening/closing reference it can never be VERIFIED ("chain-only, anchors inherited" is its own note).
- Opt-in per spec (`headerless_inherit=True`); default off, so no existing layout changes behaviour.
- The result carries a `layout_inferred` note so downstream consumers and Devin can tell it from a header-detected one.

## Recommendation
Do case 2 first (15 files, config only). Defer case 3: 9 files, needs a new geometry-matching routine, and the
ceiling is REVIEW. Case 1 stays refused. Revisit case 3 only if the MyPaisaa traffic shows such uploads.

## Open
- Need to dump header token sequences for the 15 case-2 files to write their specs.
- The scan covers four pages; a header only on later pages would be misfiled under case 3.
