# bank_of_maharashtra — onboarding notes

Status: **SHADOW_ONLY**

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
