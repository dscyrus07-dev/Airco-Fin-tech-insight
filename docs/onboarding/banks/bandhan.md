# bandhan — onboarding notes

Status: **SHADOW_ONLY** (VERIFIED share 47% < 80% gate)

Folders: Bandhan Bank
Files: 19 pdf | 18 text | 0 scanned | 1 locked

## Fingerprints

distinct fingerprints: 5 | top share: 44.4%
- `date/branch/narration/debit/credit/balance` x8
- `date/narration/amount/balance` x5
- `date/date/narration/amount` x3 (N5: BANDHAN_LAYOUT_3, balance-less app export)
- `date/date/narration/amount/balance` x1 (N5: BANDHAN_LAYOUT_4 + Statement Summary)
- `date/narration/credit/debit` x1

## N5 changes

- `ifsc_re=BDBL0[0-9A-Z]{6}` on L1/L2/L3/L4: the account-block `IFSC: BDBL000XXXX` line is
  own-bank evidence. Rescued 3 `foreign_bank` files whose customer address prints
  `BEHIND AXIS BANK A SECTOR` (a landmark, not the issuer).
- `BANDHAN_LAYOUT_3`: `TransactionDate|ValueDate|Description|Amount|Dr/Cr`, dates
  `01 Jan 2024` (date_join_words), `INR` amount prefix, side-marker column,
  `no_running_balance` -> structural REVIEW ceiling (no anchors print).
- `BANDHAN_LAYOUT_4`: same table + `Balance` column, dates `July 10, 2024`,
  `Statement Summary` label line then bare `INR` values (summary_fields
  opening/credits/debits/closing). Independent anchors -> VERIFIED.
- date_re token alternatives restricted to month names (`Jan`/`January`...): a loose
  `^[A-Za-z]+$` alternative let `Balance`/`Thanking` classify as date words, which
  tripped `additional_statement_after_summary` and could mark furniture "dated".
- 4 synthetic tests (L3 rows/REVIEW, ifsc evidence, foreign-marker refusal, L4 summary VERIFIED).

## Current behaviour (V2_MODE=shadow, after N5)

- probed: 18 | detected-correct: 100% (wrong: 0)
- tier: {'v2': 17, 'fallback': 0} | rows read: ~7500
- verdicts: {'VERIFIED': 8, 'REVIEW': 8, 'FAILED': 1}
- `de9d5233` FAILED honestly: bank-printed balance decreases on a credit row
  (chain + side disagree at the same index; printed data defect, class D).
- cross-bank false accepts on pooled other-bank files: 0 / 416 routes

## Independent audit (hold-out VERIFIED sample)

- sampled: 3 of 3 new VERIFIED | ok: 3 | disagreements: 0
  (generic-scan `close_anchor_mismatch` flags = bare-value summary the auditor
  cannot see; engine reference passed exactly: 29,651.85 -> 198.81)

## Remaining gaps

- L3 family's REVIEW ceiling is structural (class E: no printed anchors).
- VERIFIED share 8/17 = 47% < 80% -> SHADOW_ONLY.
