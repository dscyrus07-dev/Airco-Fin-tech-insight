# bank_of_maharashtra — onboarding notes

Status: **READY_TO_SERVE_CANDIDATE** (promote-1) — was SHADOW_ONLY; see promote-1 below.

Folders: Bank of Maharashtra
Files: 36 pdf | 33 text | 0 scanned | 3 locked

## Fingerprints

distinct fingerprints: 6 | top share: 39.4%
- `srno/date/narration/ref/srno/debit/credit/balance` x13
- `srno/date/narration/debit/credit/balance` x9
- `date/dr_cr/narration/ref/srno/debit/credit/balance` x7
- `date/dr_cr/narration/debit/credit/balance` x2
- `ref/credit/balance` x1
- `date/narration/ref/srno/debit/credit/balance` x1

## Current behaviour (V2_MODE=shadow)

- probed: 33 | detected-correct: 100.0% (wrong: 0, none: 0)
- tier: {'v2': 20, 'fallback': 13} | rows read: 5060
- verdicts: {'REVIEW': 11, 'VERIFIED': 9}
- fallback reasons: {'no_layout': 13}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 9 of 9 VERIFIED | ok: 9 | disagreements: 0

## promote-1 changes

- `BOM_LAYOUT_1` ref alternatives widened (`cheque`, `chequereference`, `chequeno`)
  -> routed `b84caf1b`, `c499d608`, `edaba8de`, `c5b35379`.
- `BOM_LAYOUT_2` ref alternatives widened (`chequerefer`, `chequereference`)
  + added missing `opening/closing_balance_re` + `anchor_full`
  -> routed `e775dd3a` (VERIFIED), `ff707aad` (VERIFIED).
- `BOM_LAYOUT_3` new: `Sr No | Date | Particulars | Debit | Credit | Balance | Channel`
  (no cheque column) -> `6f062db1` REVIEW, `ae282376` VERIFIED.
- `BOM_LAYOUT_4` new: `Date | Particulars | Cheque No | Withdrawals | Deposits | Balance`
  (dd/mm/yy, `0.00` empty cells, `Cr`-suffixed balance, `B/F` opening row, `Total` 3-figure
  line) -> `0b9c23b9` VERIFIED / 339 rows.

After: 26/27 text files routed — 21 VERIFIED / 5 REVIEW / 0 FAILED.
Yield 96.3%, VERIFIED share 80.8%. Multi-segment docs whose summary sits mid-document
keep honest REVIEW (opening anchor out of page1/last scan — engine gap).
`904ca49e` parked: pathological extract (dates split over 3 lines, fused amounts) — engine gap.
Audit: 21 VERIFIED audited, 19 clean, 2 false-positive sign-regex artifacts
(anchors verified to match exactly, e.g. -3,91,483.45 opening).

## N5 verification (layout-variant-only, zero-diff proof)

- `BOM_LAYOUT_3` += `dates_monotonic_expected=False`: the bank prints value-dated
  rows out of order in posting order (03-29 rows between 03-30/03-31; balances
  chain perfectly in print order).
- Zero-diff proof on current folder: 25 files, **1 named diff** —
  `6f062db1` REVIEW -> VERIFIED; all 24 other outcomes byte-identical.
- Independent audit of the changed file: 281/281 dated lines read, 0 chain
  breaks, implied opening 373.42 / closing 15.04 match printed anchors exactly.
- After: 25/25 routed VERIFIED on the measured corpus.
