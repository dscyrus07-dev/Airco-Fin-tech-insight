# ippb â€” onboarding notes

Status: **SHADOW_ONLY**

Folders: India Post Payments Bank
Files: 6 pdf | 6 text | 0 scanned | 0 locked

## Fingerprints

distinct fingerprints: 2 | top share: 83.3%
- `date/date/narration/credit/balance` x5
- `srno/srno/srno/srno/srno/srno/srno` x1

## Current behaviour (V2_MODE=shadow)

- probed: 6 | detected-correct: 100.0% (wrong: 0, none: 0)
- tier: {'fallback': 6} | rows read: 0
- verdicts: {}
- fallback reasons: {'other_bank:ippb': 5, 'no_layout': 1}
- cross-bank false accepts on pooled other-bank files: 0

## Notes (post-onboarding measure)

- NEW spec `ippb_date_tranid_transaction_particulars_withdrwal_deposit_balance` + `ippb` detector
  entry (IPOS / "India Post Payments Bank"). Header title literally prints "WITHDRWAL".
- Post-spec folder measure (6 text): 5 v2 all REVIEW (self-derived chain — opening line folds into
  rows), 1 no_layout (second fingerprint uncovered).
- Detector identifies ippb VERY_HIGH on the routed files.
