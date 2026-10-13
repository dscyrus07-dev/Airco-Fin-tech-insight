# dbs — onboarding notes

Status: **SHADOW_ONLY** (promote-1, improved) — yield 87.0% (114/131 V|R) < 90% gate because
9 files print a balance-less layout the engine cannot verify (engine gap, parked for Claude).
VERIFIED share of routed files is 91.7% (110/120). The original diagnosis was wrong:
the 'Opening Balance' line is undated (dropped as a pre-row narration line), not a dated opening
row — adding `opening_balance_re` (searched on the table's first page) restored both anchors.
Was: SHADOW_ONLY — detection 99.2%, 0 VERIFIED.

Folders: DBS Bank
Files: 137 pdf | 131 text | 4 scanned | 2 locked

## Fingerprints

distinct fingerprints: 3 | top share: 91.6%
- `dr_cr/balance` x120
- `date/narration/debit/credit` x9
- `date/date/branch/narration/debit/credit/balance` x2

## Current behaviour (V2_MODE=shadow)

- probed: 131 | detected-correct: 99.2% (wrong: 0, none: 1)
- tier: {'v2': 118, 'fallback': 13} | rows read: 19972
- verdicts: {'REVIEW': 112, 'FAILED': 6}
- fallback reasons: {'no_layout': 12, 'v2_failed:NO_ROWS': 1}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 0 of 0 VERIFIED | ok: 0 | disagreements: 0

## promote-1 changes

1. `opening_balance_re` added to DBS_LAYOUT_1 -> 109/112 former REVIEWs now VERIFIED.
   The 6 `chain+side` FAILEDs are multi-account docs where merged statement segments share
   one row stream — the boundary break is engine behaviour, not a spec defect (unchanged).
2. `DBS_LAYOUT_2` added for the `Transaction date | Value date | Branch code | Description |
   Cheque/Reference number | Debit | Credit | Balance` variant (wrapped 'number' title,
   dd/mm/yyyy dates, label/value summary block anchored via INR-prefixed last-page text).
   `d8e38ff6` -> VERIFIED/593 rows; `fe125181` -> REVIEW (summary block sits on the
   second-to-last page — out of reach of the last-page anchor scan; honest cap).

Remaining gaps (engine/corpus, not spec-fixable):
- 9 files `Date | Details of Transaction | Debit | Credit` with NO balance column —
  the engine cannot verify a chain without balances -> park (engine capability needed).
- `b4a408e2` (CID-encoded fonts, v2_failed:NO_ROWS), `2afd8fc8` (scanned),
  `0e3bc943` (consolidated-accounts certificate, not a transaction statement),
  4 scanned + 2 locked -> corpus problems.
- `fe125181` REVIEW as described above.
