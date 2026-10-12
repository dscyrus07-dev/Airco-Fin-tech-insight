# PNB residual variants (wave1) — dominant layout ONBOARDED

Census: 107 files in `Punjab National Bank`. The overnight census had classified most of them
"headerless" because their dominant header `Date | Instrument Id | Amount | Type | Balance |
Remarks` was never fingerprinted — the `Instrument Id`/`Type` columns sat undeclared. Once those
columns are declared (header-only, not extracted), `find_header` matches and the layout verifies.

## Onboarded

| cluster | files | layout |
|---|---|---|
| `date instrumentid amount type balance remarks` | 56 | `pnb_date_instrumentid_amount_type_balance_remarks` — single `Amount` column, `Type` holds the Dr/Cr marker (new `side_marker_column` field; marker lands in the narration band). Dates `dd/mm/yyyy` or `dd-dd-yyyy`. Newest-first print order (`row_order="auto"`). Brand never appears in the text layer → `bank_markers=()`, routing via detector `pnb`. |

Result: build 33/33, hold-out 23/23 VERIFIED; G2 15/15 exact re-derivations; G6 all `detector` evidence.

## Still parked (residual)

| cluster | files | blocker |
|---|---|---|
| no detectable header (fixed-pitch text) | 29 | needs `headerless_inherit` (anchor borrowing) — see `HEADERLESS_VARIANTS_DESIGN.md` |
| `PdfminerException` on open | 20 | malformed PDFs, no text layer — honest unsupported |
| `date withdrawal deposit balance alpha chq.no narration` | 2 | <5 files = residual |

Note: many PNB narrations name counterparty banks (e.g. YESBANK UPI handles). These are narration
content, not bank evidence — the detector correctly identifies the statement bank; furniture/region
markers are unaffected.
