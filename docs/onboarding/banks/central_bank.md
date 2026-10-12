# central_bank — onboarding notes

Status: **SHADOW_ONLY**

Folders: Central Bank of India
Files: 56 pdf | 49 text | 2 scanned | 5 locked

## Fingerprints

distinct fingerprints: 5 | top share: 75.5%
- `date/branch/ref/narration/debit/credit/balance` x37
- `narration/debit/credit/balance` x6
- `date/date/branch/ref/narration/debit/credit/balance` x4
- `branch/narration/debit/credit/balance` x1
- `credit/balance` x1

## Current behaviour (V2_MODE=shadow)

- probed: 49 | detected-correct: 89.8% (wrong: 0, none: 5)
- tier: {'v2': 37, 'fallback': 12} | rows read: 13321
- verdicts: {'REVIEW': 28, 'FAILED': 9}
- fallback reasons: {'no_layout': 11, 'foreign_bank': 1}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 0 of 0 VERIFIED | ok: 0 | disagreements: 0
