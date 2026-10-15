# equitas_sfb — onboarding notes

Status: **SHADOW_ONLY**

Folders: Equitas Small Finance Bank
Files: 42 pdf | 38 text | 1 scanned | 3 locked

## Fingerprints

distinct fingerprints: 6 | top share: 44.7%
- `debit/credit/balance` x17
- `date/ref/ref/narration/debit/credit` x12
- `date/ref/ref/narration` x3
- `srno/srno/balance` x3
- `date/date/date/ref/narration/debit/credit/balance` x2
- `ref/ref` x1

## Current behaviour (V2_MODE=shadow)

- probed: 38 | detected-correct: 89.5% (wrong: 0, none: 4)
- tier: {'v2': 29, 'fallback': 9} | rows read: 10661
- verdicts: {'REVIEW': 23, 'FAILED': 6}
- fallback reasons: {'no_layout': 9}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 0 of 0 VERIFIED | ok: 0 | disagreements: 0

## Unblock pass (devin/unblock-1)

Added `EQUITAS_LAYOUT_2` (Tran Date/Value Date/Ref/Description/Debits/Credits/Balance,
`B/F` opening row, `0.00` empty cells, squashed `Statement Summary` value row is
ambiguous -> single-ended opening anchor) and `EQUITAS_LAYOUT_3` (wrapped
`Date of TXN`/`Value date of`/`Reference or`/`Narration`/`Debit`/`Credit`/`Balance`
header + `OPENING BALANCE` line). Re-measure (36 files):
VERIFIED 4 (`1df4ec20`, `3dc3981d`, `4be4013a`, `d3e5bb98`), REVIEW 23, FAILED 5,
no_layout 4. Cross-bank on 383 other-folder files: 0 equitas accepts/detects.

Still **SHADOW_ONLY**: VERIFIED share 4/27 = 15% (gate >=80%).
- L1 files print no opening/closing summary -> self-derived chain -> honest REVIEW.
- Excluded as proven unreadable (money cells absent from text layer):
  FAILED `608ebbdd`,`a3a7a374`,`a69ef389`,`db2e6852`,`fe78429e`;
  no_layout `d13fe8d1`,`ea54c3b1`,`f98de911`.
- Engine gap: `baf15ad9` single `Withdrawal(INR)` column, no balance column.

## N5 pass (branch devin/n5-bank-wave)

- Re-measure (36 files): VERIFIED 4, REVIEW 23, FAILED 5, fallback 4 — unchanged vs unblock-1.
- Residuals all previously-documented classes: FAILED `608ebbdd`/`a69ef389`/`db2e6852` (money cells absent
  from text layer — class D), `a3a7a374`/`fe78429e` (`schema errors: 2` — same missing-cell family);
  no_layout `d13fe8d1`/`ea54c3b1`/`f98de911` (class D); `baf15ad9` single `Withdrawal(INR)` column with
  no side markers and no balance — dr/cr unprintable, class F/D, NOT_POSSIBLE.
- No spec/detector change. Stays **SHADOW_ONLY** (Vshare 4/27 = 15%).
