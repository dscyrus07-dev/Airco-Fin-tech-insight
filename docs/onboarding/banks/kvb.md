# kvb — onboarding notes

Status: **SHADOW_ONLY**

Folders: Karur Vysya Bank
Files: 89 pdf | 79 text | 7 scanned | 3 locked

## Fingerprints

distinct fingerprints: 3 | top share: 94.9%
- `balance/credit/amount/debit/amount/balance` x75
- `date/narration/debit/credit/balance` x3
- `narration/branch` x1

## Current behaviour (V2_MODE=shadow)

- probed: 79 | detected-correct: 5.1% (wrong: 3, none: 72)
- tier: {'fallback': 75, 'v2': 4} | rows read: 2286
- verdicts: {'VERIFIED': 3, 'FAILED': 1}
- fallback reasons: {'bank_unconfirmed': 71, 'no_layout': 4}
- cross-bank false accepts on pooled other-bank files: 0

## Unblock pass (prompt-29, current branch)

- The entire `bank_unconfirmed` tail (70 files) has a cid-garbage text layer: transaction rows extract as
  `(cid:NN)` tokens; `KVBL` IFSC prints only in the last-page branch address (beyond the detector's page-1
  scope, and the mangled layer could not be extracted anyway). Provably unreadable -> class D exclusion.
- Remaining no_layout are misfiled documents: `bc4fdbb2`,`6854f7b0` are Canara e-Pass sheets
  (`CANARA SB GENERAL`), `d86f615e` is a chit-fund agreement (Bilva Chits). Correctly unrouted.
- Gates unchanged: 4 valid routed files, 3 VERIFIED + 1 honest FAILED. No spec/detector change made.
