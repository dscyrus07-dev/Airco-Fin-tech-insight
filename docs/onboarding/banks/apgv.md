# apgv — onboarding notes

Status: **REVIEW_ONLY_SERVABLE** (wiring unblocked on the APGB collision evidence below)

Folders: APGV Bank
Files: 19 pdf | 19 text | 0 scanned | 0 locked

## Fingerprints

distinct fingerprints: 3 | top share: 84.2%
- `date/date/narration/ref/debit/credit/balance` x16
- `date/narration/debit/credit/balance` x2
- `date/narration/credit/debit/balance` x1

## Current behaviour (V2_MODE=shadow)

- probed: 19 | detected-correct: 84.2% (wrong: 2, none: 1)
- tier: {'v2': 16, 'fallback': 3} | rows read: 7666
- verdicts: {'REVIEW': 16}
- fallback reasons: {'no_layout': 2, 'foreign_bank': 1}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 0 of 0 VERIFIED | ok: 0 | disagreements: 0

## Prompt-29 update: APGB collision check + detector wiring

The only blocker was the missing `banks/apgv.json` detector config, held pending
evidence that APGV and APGB do not collide (same core table shape).

Evidence scan (both folders, all text files):

- APGV files carry `APGV` / `AP GRAMEENA VIKAS BANK` / `VIKAS` evidence; none carry
  `APGB` or `PRAGATHI`.
- APGB files carry `ANDHRA PRAGATHI GRAMEENA BANK` / `APGB`; none carry APGV evidence.
- `ANDHRAPRAGATHIGRAMEENABANK` is already in `OTHER_BANK_MARKERS`, so APGB-branded
  pages refuse the APGV spec at the layout layer; the detector resolves APGB docs to
  UNKNOWN (no name/IFSC overlap with `ap grameena vikas bank` / `APGV` prefix).

Wiring added:

- `banks/apgv.json` (name + `APGV` IFSC prefix; `corpus_folder: APGV Bank`)
- `DETECTOR_TO_SPEC_BANK["apgv"]`, orchestrator aliases (`apgv`, `apgv bank`,
  `ap grameena vikas bank`), `ONBOARDED` wiring test + analyze-detection case
  (APGB evidence resolves to no onboarded bank).

Post-wiring corpus run (15 text files in the manifest view):

- detector: 13 x apgv VERY_HIGH (score 95, no runner-up); `e6a586ec` UNKNOWN
  (brandless e-pass sheet, no bank evidence at all); `248fc20d` misfiled Canara
  e-Pass Sheet (detected canara LOW).
- routing: 13 x v2 `apgv_postdate_..._balance` all REVIEW (no printed anchors ->
  honest REVIEW cap via NO_INDEPENDENT_ANCHOR); `e6a586ec` fallback foreign_bank;
  `248fc20d` fallback no_layout.
- APGB corpus files: detector UNKNOWN, route fallback - never apgv.
- cross-bank sample (393 files, all other folders): 0 false `apgv` detections.

APGV has no legacy processor and no printed opening/closing anchors in this layout
family, so its ceiling is REVIEW -> servable only under explicit allowlisting with
`needs_review=True` (same class as iob/south_indian). APGB remains NOT_POSSIBLE.
