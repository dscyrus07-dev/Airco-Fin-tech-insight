# federal — onboarding notes

Status: **SHADOW_ONLY**

Folders: Federal Bank
Files: 360 pdf | 308 text | 1 scanned | 51 locked

## Fingerprints

distinct fingerprints: 13 | top share: 37.3%
- `date/date/narration/date/dr_cr/ref/narration/debit/credit/balance/dr_cr` x115
- `balance/debit/balance` x49
- `ref/narration/amount/balance` x48
- `date/date/narration/debit/credit/balance` x28
- `date/date/narration/date/ref/narration/debit/credit/balance` x27
- `date/date/narration/date/debit/credit/balance/dr_cr` x14
- `date/narration/amount/dr_cr` x11
- `date/date/narration/date/debit/credit/balance` x9
- `date/date/narration/debit/credit/balance/dr_cr` x2
- `srno/srno/srno` x2
- `<none>` x1
- `date/narration/dr_cr/amount` x1
- ... +1 more

## Current behaviour (V2_MODE=shadow)

- probed: 308 | detected-correct: 95.5% (wrong: 0, none: 14)
- tier: {'fallback': 114, 'v2': 194} | rows read: 106120
- verdicts: {'VERIFIED': 144, 'REVIEW': 37, 'FAILED': 13}
- fallback reasons: {'no_layout': 113, 'v2_failed:NO_ROWS': 1}
- cross-bank false accepts on pooled other-bank files: 5
  - 18f47088 from CSB Bank via layout
  - 105adbdd from CSB Bank via layout
  - 930efd6d from CSB Bank via layout
  - 528ee39a from CSB Bank via layout
  - 22f26126 from CSB Bank via layout

## Independent audit (hold-out VERIFIED sample)

- sampled: 15 of 144 VERIFIED | ok: 15 | disagreements: 0
