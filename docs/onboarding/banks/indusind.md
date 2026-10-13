# indusind — onboarding notes

Status: **SHADOW_ONLY**

Folders: IndusInd Bank
Files: 154 pdf | 148 text | 3 scanned | 3 locked

## Fingerprints

distinct fingerprints: 9 | top share: 37.8%
- `date/narration/credit/balance` x56
- `date/narration/ref/srno/debit/credit/balance` x43
- `date/dr_cr/narration/debit/credit` x21
- `srno/dr_cr/amount/balance` x11
- `date/narration/debit/credit/balance` x8
- `date/narration/ref/debit/credit/balance` x3
- `date/dr_cr/narration/debit/credit/balance` x2
- `date/narration/ref/srno/ref/debit/credit/balance` x2
- `<none>` x2

## Current behaviour (V2_MODE=shadow)

- probed: 148 | detected-correct: 93.2% (wrong: 0, none: 10)
- tier: {'fallback': 48, 'v2': 100} | rows read: 61410
- verdicts: {'VERIFIED': 95, 'FAILED': 2, 'REVIEW': 3}
- fallback reasons: {'no_layout': 48}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 20 of 95 VERIFIED | ok: 20 | disagreements: 0
