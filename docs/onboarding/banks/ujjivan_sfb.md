# ujjivan_sfb — onboarding notes

Status: **SHADOW_ONLY** — detection 76.9%; all REVIEW (self-derived anchor) — spec frozen; FAILED x5 chain/side

Folders: Ujjivan Small Finance Bank
Files: 39 pdf | 39 text | 0 scanned | 0 locked

## Fingerprints

distinct fingerprints: 4 | top share: 74.4%
- `date/debit/credit/balance/amount` x29
- `date/narration/amount/dr_cr` x8
- `date/narration/debit/credit/balance` x1
- `date/narration/ref/srno/debit/credit/balance` x1

## Current behaviour (V2_MODE=shadow)

- probed: 39 | detected-correct: 76.9% (wrong: 1, none: 8)
- tier: {'fallback': 10, 'v2': 29} | rows read: 13323
- verdicts: {'REVIEW': 24, 'FAILED': 5}
- fallback reasons: {'no_layout': 10}
- cross-bank false accepts on pooled other-bank files: 1
  - f3105a96 from Human Verification via detector

## Independent audit (hold-out VERIFIED sample)

- sampled: 0 of 0 VERIFIED | ok: 0 | disagreements: 0
