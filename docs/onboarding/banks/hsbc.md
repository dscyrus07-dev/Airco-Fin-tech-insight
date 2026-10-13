# hsbc — onboarding notes

Status: **SHADOW_ONLY**

Folders: HSBC
Files: 103 pdf | 37 text | 66 scanned | 0 locked

## Fingerprints

distinct fingerprints: 4 | top share: 67.6%
- `date/narration/credit/debit/balance` x25
- `date/dr_cr/narration/balance` x9
- `branch/branch` x2
- `<none>` x1

## Current behaviour (V2_MODE=shadow)

- probed: 37 | detected-correct: 97.3% (wrong: 0, none: 1)
- tier: {'v2': 25, 'fallback': 12} | rows read: 5945
- verdicts: {'REVIEW': 25}
- fallback reasons: {'v2_failed:NO_ROWS': 2, 'no_layout': 10}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 0 of 0 VERIFIED | ok: 0 | disagreements: 0
