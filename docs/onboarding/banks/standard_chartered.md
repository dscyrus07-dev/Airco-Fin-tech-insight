# standard_chartered — onboarding notes

Status: **SHADOW_ONLY** — detection 91.9% (<100% gate); 24/182 v2 FAILED on chain/side/totals; audit 30/30 clean

Folders: Standard Chartered Bank
Files: 245 pdf | 210 text | 1 scanned | 34 locked

## Fingerprints

distinct fingerprints: 3 | top share: 99.0%
- `date/narration/ref/credit/debit/balance` x208
- `narration/narration` x1
- `date/date/date/narration/debit/credit/balance` x1

## Current behaviour (V2_MODE=shadow)

- probed: 210 | detected-correct: 91.9% (wrong: 5, none: 12)
- tier: {'v2': 182, 'fallback': 28} | rows read: 28030
- verdicts: {'VERIFIED': 158, 'FAILED': 24}
- fallback reasons: {'foreign_bank': 22, 'no_layout': 6}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 30 of 158 VERIFIED | ok: 30 | disagreements: 0
