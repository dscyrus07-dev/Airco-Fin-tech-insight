# south_indian — onboarding notes

Status: **REVIEW_ONLY**

Folders: South Indian Bank
Files: 33 pdf | 29 text | 1 scanned | 3 locked

## Fingerprints

distinct fingerprints: 1 | top share: 100.0%
- `date/narration/debit/credit/balance` x29

## Current behaviour (V2_MODE=shadow)

- probed: 29 | detected-correct: 100.0% (wrong: 0, none: 0)
- tier: {'v2': 28, 'fallback': 1} | rows read: 18653
- verdicts: {'REVIEW': 28}
- fallback reasons: {'no_layout': 1}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 0 of 0 VERIFIED | ok: 0 | disagreements: 0

## [UB] §3 REVIEW_ONLY serve test

- Same `decide_serve` path as iob (no legacy processor): REVIEW -> serve_v2 + needs_review.
- Synthetic e2e (onb stack, `ONB_EXTRA_SERVE_BANKS=south_indian`): confirm-override bank,
  process -> completed. Workbook `Statement Check`: `Engine: v2 | Verdict: REVIEW |
  Independently verified: no | Needs review: yes | NO_INDEPENDENT_ANCHOR, EXTRACTION_WARNINGS`.
  Rows reconcile exactly.
- CAVEAT (latent marker collision): a synthetic doc that prints the brand "South Indian Bank"
  in the header region trips the `INDIANBANK` substring marker and is refused `foreign_bank` ->
  UNSUPPORTED (no legacy fallback). Real corpus docs never print the brand (spec relies on
  detector), so this is not hit in practice; noted for the marker-set owners.
- Honest: never looks verified. Status: **REVIEW_ONLY_SERVABLE** (requires `south_indian`
  in the serve allowlist; corpus: 28 REVIEW, 1 no_layout).
