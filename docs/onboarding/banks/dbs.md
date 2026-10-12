# dbs — onboarding notes

Status: **SHADOW_ONLY** — detection 99.2% (<100%); VERIFIED unreachable under current spec (opening row consumed -> self-derived chain caps at REVIEW); spec frozen by rules

Folders: DBS Bank
Files: 137 pdf | 131 text | 4 scanned | 2 locked

## Fingerprints

distinct fingerprints: 3 | top share: 91.6%
- `dr_cr/balance` x120
- `date/narration/debit/credit` x9
- `date/date/branch/narration/debit/credit/balance` x2

## Current behaviour (V2_MODE=shadow)

- probed: 131 | detected-correct: 99.2% (wrong: 0, none: 1)
- tier: {'v2': 118, 'fallback': 13} | rows read: 19972
- verdicts: {'REVIEW': 112, 'FAILED': 6}
- fallback reasons: {'no_layout': 12, 'v2_failed:NO_ROWS': 1}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 0 of 0 VERIFIED | ok: 0 | disagreements: 0
