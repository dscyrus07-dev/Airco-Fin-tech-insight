# idbi — onboarding notes

Status: **SHADOW_ONLY**

Folders: IDBI Bank
Files: 119 pdf | 109 text | 6 scanned | 4 locked

## Fingerprints

distinct fingerprints: 13 | top share: 31.2%
- `date/narration/srno/debit/credit/balance` x34
- `srno/date/date/narration/ref/srno` x31
- `date/date/narration/dr_cr/amount/balance` x20
- `date/narration/amount/dr_cr` x11
- `date/narration/ref/ref/date/debit/credit/balance` x2
- `<none>` x2
- `date/date/ref/narration/debit/amount/credit/amount/balance` x2
- `date/narration/ref/srno/debit/credit/balance` x2
- `date/narration/date/debit/credit/balance` x1
- `date/date/ref/srno/narration` x1
- `narration/ref/credit` x1
- `date/date/debit/amount/credit/amount` x1
- ... +1 more

## Current behaviour (V2_MODE=shadow)

- probed: 109 | detected-correct: 72.5% (wrong: 1, none: 29)
- tier: {'v2': 55, 'fallback': 54} | rows read: 27903
- verdicts: {'REVIEW': 31, 'VERIFIED': 15, 'FAILED': 9}
- fallback reasons: {'no_layout': 42, 'bank_unconfirmed': 11, 'foreign_bank': 1}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 15 of 15 VERIFIED | ok: 15 | disagreements: 0
