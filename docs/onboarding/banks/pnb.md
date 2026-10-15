# pnb — onboarding notes

Status: **SHADOW_ONLY**

Folders: Punjab National Bank
Files: 109 pdf | 88 text | 1 scanned | 20 locked

## Fingerprints

distinct fingerprints: 7 | top share: 83.0%
- `date/ref/amount/dr_cr/balance/narration` x73
- `debit/credit/balance/narration` x8
- `ref/debit/credit/balance/narration` x2
- `date/debit/credit/balance/narration` x2
- `balance/ref` x1
- `narration/amount` x1
- `date/date/dr_cr` x1

## Current behaviour (V2_MODE=shadow)

- probed: 88 | detected-correct: 98.9% (wrong: 0, none: 1)
- tier: {'fallback': 31, 'v2': 57} | rows read: 27408
- verdicts: {'REVIEW': 57}
- fallback reasons: {'no_layout': 31}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 0 of 0 VERIFIED | ok: 0 | disagreements: 0

## N5 verification (layout-variant-only, restricted)

- Re-measured 82 files: 81 REVIEW / 1 `no_layout`.
- The sole `no_layout` (`4eb17de5`) is a WhatsApp Banking Terms & Conditions
  document misfiled in the PNB folder — correct refusal, not a gap.
- REVIEW ceiling is honest: layouts carry no printed-anchor verification for
  these variants; no spec or marker change made (restricted bank — any change
  needs zero-diff proof; none was warranted).
