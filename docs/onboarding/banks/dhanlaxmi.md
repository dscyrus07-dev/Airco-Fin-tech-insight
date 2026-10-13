# dhanlaxmi â€” onboarding notes

Status: **SHADOW_ONLY**

Folders: Dhanlaxmi Bank
Files: 15 pdf | 15 text | 0 scanned | 0 locked

## Fingerprints

distinct fingerprints: 3 | top share: 53.3%
- `date/date` x8
- `date/date/narration/ref/srno/debit/credit/balance` x5
- `date/srno/narration/debit/amount/credit/amount/balance` x2

## Current behaviour (V2_MODE=shadow)

- probed: 15 | detected-correct: 0.0% (wrong: 0, none: 15)
- tier: {'fallback': 15} | rows read: 0
- verdicts: {}
- fallback reasons: {'no_layout': 15}
- cross-bank false accepts on pooled other-bank files: 0

## Notes (post-onboarding measure)

- NEW spec `dhanlaxmi_date_valuedate_description_chequeno_debits_credits_balance` (fp-B, 5 files) +
  `dhanlaxmi` detector entry (DLXB / dhanbank domains). Detector: VERY_HIGH on all 15 files.
- Real rows print literal `0.00` in the unused debit/credit cell -> `zero_amount_is_empty` set.
- Post-spec measure (15 text): 5 v2 REVIEW, 10 no_layout.
  Uncovered: fp-A x8 (interleaved layout printing the running balance on its OWN line after the row —
  needs a balance-as-continuation capability the engine does not have today -> stayed fallback, not built);
  fp-C x2 (`debit amount | credit amount` titles, `srno` column).
- VERIFIED not reachable yet: routed files are REVIEW (self-derived chain).
