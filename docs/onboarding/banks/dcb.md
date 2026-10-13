# dcb — onboarding notes

Status: **SHADOW_ONLY**

Folders: DCB Bank
Files: 16 pdf | 15 text | 1 scanned | 0 locked

## Fingerprints

distinct fingerprints: 1 | top share: 100.0%
- `narration/ref/debit/credit/balance` x15

## Current behaviour (V2_MODE=shadow)

- probed: 15 | detected-correct: 100.0% (wrong: 0, none: 0)
- tier: {'v2': 15} | rows read: 4310
- verdicts: {'VERIFIED': 7, 'FAILED': 8}
- fallback reasons: {}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 7 of 7 VERIFIED | ok: 7 | disagreements: 0

## Notes

- 8/15 corpus files FAILED: dominant reason `reference failed`; also `schema errors: 1`,
  `chain failed`, `side failed`. Failing files carry a second account/summary block
  (multi-account fingerprint variant): the printed summary's opening/closing does not
  match the parsed section's derived values. The frozen spec cannot handle that variant;
  files stay FAILED rather than passing silently.
- VERIFIED subset audited clean (7/7): rows match dated amount lines, chain intact,
  anchors verified independently.
- Gate misses: VERIFIED 7/15 = 47% (<80%) despite 100% detection and zero false accepts.
