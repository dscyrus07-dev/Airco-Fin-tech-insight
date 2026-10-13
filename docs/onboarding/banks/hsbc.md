# hsbc — onboarding notes

Status: **SHADOW_ONLY**

Folders: HSBC
Files: 103 pdf | 37 text | 66 scanned | 0 locked

## Fingerprints

distinct fingerprints: 4 | top share: 67.6%
- `date/narration/credit/debit/balance` x25
- `date/dr_cr/narration/balance` x9
- `branch/branch` x2
- `<none>` x1

## Current behaviour (V2_MODE=shadow)

- probed: 37 | detected-correct: 97.3% (wrong: 0, none: 1)
- tier: {'v2': 25, 'fallback': 12} | rows read: 5945
- verdicts: {'REVIEW': 25}
- fallback reasons: {'v2_failed:NO_ROWS': 2, 'no_layout': 10}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 0 of 0 VERIFIED | ok: 0 | disagreements: 0

## Unblock pass (devin/unblock-1)

Re-measure: 91 files -> 57 scanned_no_text (image-only corpus, class D),
22 REVIEW (all self-derived chain - HSBC statement pages print no
opening/closing anchors, honest), 10 no_layout, 2 NO_ROWS.
no_layout breakdown: 9 are HSBC UK exports
(`Date | Payment type and details | Paid out | Paid in | Balance` with
`BALANCE BROUGHT FORWARD`/`BALANCE CARRIED FORWARD` page-boundary rows) -
data rows print NO running balance, so the chain model cannot verify them;
sparse-balance layout is an engine gap (F): `6792a91d`,`dec6e727`,`33b3a7cd`,
`5fa624e1`,`a1ffcd60`,`1577e8f4`,`7a81679e`,`ee896cdc`,`f3a109c5`.
NO_ROWS `f06eb015`,`84f8564e` are app-screenshot-style docs (Available balance /
Date range, no transaction table) - not statement layouts.
Still **SHADOW_ONLY**: no printed anchors (E) + sparse-balance variant (F).
