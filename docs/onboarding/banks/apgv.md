# apgv — onboarding notes

Status: **SHADOW_ONLY**

Folders: APGV Bank
Files: 19 pdf | 19 text | 0 scanned | 0 locked

## Fingerprints

distinct fingerprints: 3 | top share: 84.2%
- `date/date/narration/ref/debit/credit/balance` x16
- `date/narration/debit/credit/balance` x2
- `date/narration/credit/debit/balance` x1

## Current behaviour (V2_MODE=shadow)

- probed: 19 | detected-correct: 84.2% (wrong: 2, none: 1)
- tier: {'v2': 16, 'fallback': 3} | rows read: 7666
- verdicts: {'REVIEW': 16}
- fallback reasons: {'no_layout': 2, 'foreign_bank': 1}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 0 of 0 VERIFIED | ok: 0 | disagreements: 0
