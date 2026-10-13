# yes — onboarding notes

Status: **SHADOW_ONLY**

Folders: Yes Bank
Files: 137 pdf | 106 text | 9 scanned | 22 locked

## Fingerprints

distinct fingerprints: 13 | top share: 36.8%
- `date/ref/srno/narration/debit/credit/balance` x39
- `date/date/ref/ref/srno/narration/debit/credit` x21
- `dr_cr/balance` x14
- `date/narration/ref/debit/credit/balance` x8
- `date/narration/credit/debit/balance` x6
- `date/narration/debit/credit/balance` x4
- `date/narration/amount/dr_cr` x4
- `date/date/ref/ref/srno/narration/debit/credit/balance` x3
- `balance/points/points/points/balance/points` x2
- `date/date/narration/debit/credit/balance` x2
- `narration/debit/credit` x1
- `balance/points/points/balance/points` x1
- ... +1 more

## Current behaviour (V2_MODE=shadow)

- probed: 106 | detected-correct: 85.8% (wrong: 5, none: 10)
- tier: {'v2': 82, 'fallback': 24} | rows read: 20128
- verdicts: {'REVIEW': 37, 'FAILED': 29, 'VERIFIED': 16}
- fallback reasons: {'detector_weak': 7, 'no_layout': 11, 'foreign_bank': 5, 'bank_unconfirmed': 1}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 16 of 16 VERIFIED | ok: 16 | disagreements: 0

## Unblock pass (prompt-29, current branch)

- spec fixes (yes-owned only): `YESBANK.IN` footer/RM-mail marker on all registered specs;
  `zero_amount_is_empty` (this family prints literal `0`/`0.00` in the unused side);
  `opening_row_balance_only` (dated `B/F ...` opening row — its words sit in the value-date band
  so narration never sees them); `end_markers=("^OPENINGBALANCE:",)` so a post-statement section
  (FD certificate page) cannot be swallowed into rows; L3 gained the printed
  `Opening Balance:/Closing Balance:` summary regexes + `anchor_full` that only L1 had.
- new `YES_LAYOUT_4`: 6-col variant `Transaction Date | Value Date | Description | Withdrawals |
  Deposits | Balance` (no ref column), integer debit/credit cells, left-aligned amounts,
  `band_left_pad` on narration, `opening_row_marker="B/F"`.
- after: 92 manifest files -> 86 v2 / 6 fallback | 33 VERIFIED / 34 REVIEW / 20 FAILED
  (before on same set: 16 VERIFIED). audit: 33/33 clean. cross-bank: 0 foreign accepts (364 files).
- remaining gaps (honest):
  - 34 REVIEW: documents genuinely print no opening/closing anchor -> self-derived chain (correct cap).
  - 20 FAILED: per-pair balance print (fee+GST debit pairs move the balance once while two debit
    lines carry the same running balance) -> printed data cannot reconcile row-wise; plus one
    trailing FD-certificate section flagged `additional_statement_after_summary` (REVIEW).
  - `008a966b`: 3-line interleaved header (`Transaction ... Running` / `Description Debit Credit` /
    `Date Date Transaction Number Balance`) - `header_wraps` merges only pairs -> engine gap.
  - misfiled (class D): `e99c7c1d` Union Bank letterhead, `2aed793f` AU (AUBL IFSC,
    detector au_sfb VERY_HIGH). `508a9258` foreign_bank: UTIB/AXIS IFSCs on page 1 (guard kept).
  - `382d5465`: zero-transaction statement -> honest NO_ROWS.
