# equitas_sfb — onboarding notes

Status: **SHADOW_ONLY**

Folders: Equitas Small Finance Bank
Files: 42 pdf | 38 text | 1 scanned | 3 locked

## Fingerprints

distinct fingerprints: 6 | top share: 44.7%
- `debit/credit/balance` x17
- `date/ref/ref/narration/debit/credit` x12
- `date/ref/ref/narration` x3
- `srno/srno/balance` x3
- `date/date/date/ref/narration/debit/credit/balance` x2
- `ref/ref` x1

## Current behaviour (V2_MODE=shadow)

- probed: 38 | detected-correct: 89.5% (wrong: 0, none: 4)
- tier: {'v2': 29, 'fallback': 9} | rows read: 10661
- verdicts: {'REVIEW': 23, 'FAILED': 6}
- fallback reasons: {'no_layout': 9}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 0 of 0 VERIFIED | ok: 0 | disagreements: 0
