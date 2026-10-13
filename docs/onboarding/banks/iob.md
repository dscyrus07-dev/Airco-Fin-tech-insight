# iob — onboarding notes

Status: **REVIEW_ONLY**

Folders: Indian Overseas Bank
Files: 71 pdf | 62 text | 3 scanned | 6 locked

## Fingerprints

distinct fingerprints: 5 | top share: 50.0%
- `date/narration/ref` x31
- `date/ref/debit/credit/balance` x21
- `date/ref/narration/debit/credit/balance` x6
- `date/date/ref/narration/debit/credit/balance` x3
- `<none>` x1

## Current behaviour (V2_MODE=shadow)

- probed: 62 | detected-correct: 100.0% (wrong: 0, none: 0)
- tier: {'v2': 58, 'fallback': 4} | rows read: 23117
- verdicts: {'REVIEW': 55, 'FAILED': 3}
- fallback reasons: {'no_layout': 4}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 0 of 0 VERIFIED | ok: 0 | disagreements: 0
