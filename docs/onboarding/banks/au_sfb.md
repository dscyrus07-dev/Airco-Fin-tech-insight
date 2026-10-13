# au_sfb — onboarding notes

Status: **READY_TO_SERVE_CANDIDATE** (promote-1) — 16/17 route to V2, all VERIFIED; audit 16/16 clean.
The 1 remaining `no_layout` file (`4e1287dd`) is a different export shape with zero own-bank
evidence (no AUBL/aubank.in/name in the text layer) — correctly refused, cannot be attributed.
Was: SHADOW_ONLY — detection 94.4% (<100% gate); audit 15/15 clean.

Folders: AU Small Finance Bank
Files: 18 pdf | 18 text | 0 scanned | 0 locked

## Fingerprints

distinct fingerprints: 3 | top share: 83.3%
- `date/date/ref/balance` x15
- `date/debit/credit/balance` x2
- `date/narration/amount/dr_cr` x1

## Current behaviour (V2_MODE=shadow)

- probed: 18 | detected-correct: 94.4% (wrong: 0, none: 1)
- tier: {'v2': 15, 'fallback': 3} | rows read: 4565
- verdicts: {'VERIFIED': 15}
- fallback reasons: {'no_layout': 3}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 15 of 15 VERIFIED | ok: 15 | disagreements: 0

## promote-1 changes (AU_LAYOUT_2 added)

New second layout for the newer export: two-line wrapped header (Transaction Date / Value Date /
Description/Narration / Cheque / Reference No. / Debit (Rs) / Credit (Rs) / Balance (Rs)), Value Date
column LEFT of narration, rupee-marked money titles, sign-gap negative balances ("- 39,457.19"),
`Opening Balance(₹)`/`Closing Balance(₹)` anchors, `Statement Period:` period line.
Marker: `AUBANK.IN` footer domain (compliant — not a bare IFSC prefix).

- `7b2023ab`, `f50a0f50` -> V2 VERIFIED (140 / 30 rows)
- cross-bank (419 files / 50 folders): see PROMOTE_RESULTS.md
