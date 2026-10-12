# bandhan — onboarding notes

Status: **SHADOW_ONLY**

Folders: Bandhan Bank
Files: 19 pdf | 18 text | 0 scanned | 1 locked

## Fingerprints

distinct fingerprints: 5 | top share: 44.4%
- `date/branch/narration/debit/credit/balance` x8
- `date/narration/amount/balance` x5
- `date/date/narration/amount` x3
- `date/date/narration/amount/balance` x1
- `date/narration/credit/debit` x1

## Current behaviour (V2_MODE=shadow)

- probed: 18 | detected-correct: 94.4% (wrong: 0, none: 1)
- tier: {'v2': 10, 'fallback': 8} | rows read: 5032
- verdicts: {'REVIEW': 5, 'VERIFIED': 5}
- fallback reasons: {'foreign_bank': 3, 'no_layout': 5}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 5 of 5 VERIFIED | ok: 5 | disagreements: 0
