# uco â€” onboarding notes

Status: **SHADOW_ONLY**

Folders: UCO Bank
Files: 11 pdf | 11 text | 0 scanned | 0 locked

## Fingerprints

distinct fingerprints: 3 | top share: 72.7%
- `date/narration/ref/srno/debit/credit/balance` x8
- `date/narration/credit/balance` x2
- `date/narration/debit/credit/balance` x1

## Current behaviour (V2_MODE=shadow)

- probed: 11 | detected-correct: 100.0% (wrong: 0, none: 0)
- tier: {'fallback': 11} | rows read: 0
- verdicts: {}
- fallback reasons: {'other_bank:uco': 11}
- cross-bank false accepts on pooled other-bank files: 0

## Notes (post-onboarding measure)

- NEW specs `UCO_LAYOUT_1` (with instrument-no column) + `UCO_LAYOUT_2` (without) registered;
  `uco` detector entry added (UCBA / uco bank names).
- Post-spec folder measure (11 text): 8 v2 (4 REVIEW self-derived chain, 4 FAILED chain+side —
  real reconciliation mismatches, not spec crashes), 2 no_layout (landscape fingerprint uncovered),
  1 other fallback.
- Detector identifies uco VERY_HIGH on all measured files.
