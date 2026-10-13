# airtel_pb â€” onboarding notes

Status: **SHADOW_ONLY**

Folders: Airtel Payments Bank
Files: 7 pdf | 7 text | 0 scanned | 0 locked

## Fingerprints

distinct fingerprints: 3 | top share: 57.1%
- `date/narration/debit/credit/balance` x4
- `charges/amount` x2
- `credit/charges/amount` x1

## Current behaviour (V2_MODE=shadow)

- probed: 7 | detected-correct: 57.1% (wrong: 0, none: 3)
- tier: {'fallback': 7} | rows read: 0
- verdicts: {}
- fallback reasons: {'other_bank:airtel_pb': 4, 'no_layout': 3}
- cross-bank false accepts on pooled other-bank files: 0

## Notes (post-onboarding measure)

- NEW spec `airtelpb_date_transactiontype_particulars_withdrawal_deposit_balance` + `airtel_pb`
  detector entry (AIRP). Detector identifies airtel_pb VERY_HIGH on 4/7 files (LOW x2).
- Post-spec folder measure (7 text): 4 v2 (all FAILED on 1-2 schema-error rows each — real edge rows,
  rows otherwise parse), 3 no_layout (other fingerprints uncovered).
