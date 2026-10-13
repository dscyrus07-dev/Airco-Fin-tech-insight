# au_sfb — onboarding notes

Status: **SHADOW_ONLY** — detection 94.4% (<100% gate); audit 15/15 clean; 1 file no_layout

Folders: AU Small Finance Bank
Files: 18 pdf | 18 text | 0 scanned | 0 locked

## Fingerprints

distinct fingerprints: 3 | top share: 83.3%
- `date/date/ref/balance` x15
- `date/debit/credit/balance` x2
- `date/narration/amount/dr_cr` x1

## Current behaviour (V2_MODE=shadow)

- probed: 18 | detected-correct: 94.4% (wrong: 0, none: 1)
- tier: {'v2': 15, 'fallback': 3} | rows read: 4565
- verdicts: {'VERIFIED': 15}
- fallback reasons: {'no_layout': 3}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 15 of 15 VERIFIED | ok: 15 | disagreements: 0
