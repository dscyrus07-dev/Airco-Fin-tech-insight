# central_bank — onboarding notes

Status: **SHADOW_ONLY**

Folders: Central Bank of India
Files: 56 pdf | 49 text | 2 scanned | 5 locked

## Fingerprints

distinct fingerprints: 5 | top share: 75.5%
- `date/branch/ref/narration/debit/credit/balance` x37
- `narration/debit/credit/balance` x6
- `date/date/branch/ref/narration/debit/credit/balance` x4
- `branch/narration/debit/credit/balance` x1
- `credit/balance` x1

## Current behaviour (V2_MODE=shadow)

- probed: 49 | detected-correct: 89.8% (wrong: 0, none: 5)
- tier: {'v2': 37, 'fallback': 12} | rows read: 13321
- verdicts: {'REVIEW': 28, 'FAILED': 9}
- fallback reasons: {'no_layout': 11, 'foreign_bank': 1}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 0 of 0 VERIFIED | ok: 0 | disagreements: 0

## Unblock pass (devin/unblock-1)

Added `CBI_LAYOUT_3` ("Value | Post | Details | Chq.No. | Debit | Credit | Balance"
branch-portal variant: `Value/Post` title line + `Date/Date` wrap, dd/mm/yy, `-` empty
cheque cell, `Cr`-suffixed balances, `BROUGHT FORWARD :` opening anchor, single-ended;
`monospace_text` splits the space-glued line tokens). `23d24bef`,`fe181a19` -> VERIFIED.
Still **SHADOW_ONLY**: 26 L1/L2 files reach REVIEW with no printed opening/closing
summary (self-derived chain - by design); Vshare stays far under 80%.
Remaining no_layout files:
- `2e2f4e20`,`735d18a4` - same family but every line is one glued word AND balances
  print as lone tokens; rows split but balances cannot classify positionally (F).
- `435bb0ee`,`173e4a36`,`e2a135b2`,`73679c2c` - `POST Date|TXN Date|Branch Code|Cheque|
  DESCRIPTION` variant with NO own-bank header/footer text (only body `CBINM..` UPI
  refs - not usable as marker evidence); correctly unroutable (C/D).
- `459f15b8` - 15-column header wrapped across 5 lines with mid-word splits (F).
- `0241c956` - foreign_bank refusal (correct).
Honest FAILED kept: `deb76171` (document prints duplicated rows mid-table),
`26f22d59`,`98f557cb` (chain broken in the print), `fef47c0b` (no period marker,
0 rows), `b4a408e2` handled under dbs. Regression: 650-file compare vs 54f51ab = 0 diffs.

## N5 pass (branch devin/n5-bank-wave)

- Re-measure on N3 tip (33 readable): VERIFIED 2, REVIEW 25, FAILED 5, fallback 2.
- `459f15b8` (15-column 3-line header, mid-word splits) now reads via `CBI_LAYOUT_4` ->
  REVIEW/13 (no printed anchors; honest cap).
- Still unresolved, all documented classes: `2e2f4e20`,`735d18a4` glued single-token lines
  (class D — no space glyphs; balances can't classify positionally), `435bb0ee` family has no
  own-bank header/footer text (class C), FAILEDs `26f22d59`/`98f557cb` (print-level chain
  gaps, class D), `deb76171` (duplicated printed rows, class D), `fef47c0b` (no period
  marker, class E), `0241c956` (foreign_bank on own page-1 evidence — correct).
- No spec/detector change this pass — every residual is class C/D/E/F. **SHADOW_ONLY**
  (VERIFIED share far under 80%; most files print no anchors at all).
