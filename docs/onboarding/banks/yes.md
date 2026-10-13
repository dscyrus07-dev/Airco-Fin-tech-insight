# yes — onboarding notes

Status: **SHADOW_ONLY**

Folders: Yes Bank
Files: 137 pdf | 106 text | 9 scanned | 22 locked

## Fingerprints

distinct fingerprints: 13 | top share: 36.8%
- `date/ref/srno/narration/debit/credit/balance` x39
- `date/date/ref/ref/srno/narration/debit/credit` x21
- `dr_cr/balance` x14
- `date/narration/ref/debit/credit/balance` x8
- `date/narration/credit/debit/balance` x6
- `date/narration/debit/credit/balance` x4
- `date/narration/amount/dr_cr` x4
- `date/date/ref/ref/srno/narration/debit/credit/balance` x3
- `balance/points/points/points/balance/points` x2
- `date/date/narration/debit/credit/balance` x2
- `narration/debit/credit` x1
- `balance/points/points/balance/points` x1
- ... +1 more

## Current behaviour (V2_MODE=shadow)

- probed: 106 | detected-correct: 85.8% (wrong: 5, none: 10)
- tier: {'v2': 82, 'fallback': 24} | rows read: 20128
- verdicts: {'REVIEW': 37, 'FAILED': 29, 'VERIFIED': 16}
- fallback reasons: {'detector_weak': 7, 'no_layout': 11, 'foreign_bank': 5, 'bank_unconfirmed': 1}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 16 of 16 VERIFIED | ok: 16 | disagreements: 0
