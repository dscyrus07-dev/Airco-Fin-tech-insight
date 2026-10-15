# csb — onboarding notes

Status: **SHADOW_ONLY**

Folders: CSB Bank
Files: 17 pdf | 16 text | 0 scanned | 1 locked

## Fingerprints

distinct fingerprints: 4 | top share: 50.0%
- `date/date/narration/date/ref/narration/debit/credit/balance` x8
- `date/narration/debit/credit/balance` x5
- `date/debit/credit/balance` x2
- `balance/debit/amount/credit/amount/balance` x1

## Current behaviour (V2_MODE=shadow)

- probed: 16 | detected-correct: 18.8% (wrong: 8, none: 5)
- tier: {'v2': 8, 'fallback': 8} | rows read: 4125
- verdicts: {'REVIEW': 8}
- fallback reasons: {'other_bank:csb': 3, 'no_layout': 5}
- cross-bank false accepts on pooled other-bank files: 0

## Notes (post-onboarding measure)

- NEW spec `csb_date_value_transaction_debit_credit_balance` registered (fp: date/value/transaction/
  debit/credit/balance, dd-Mmm-yyyy, CR/DR balance suffix). Covers the dominant genuine-CSB fingerprint.
- Folder is MIXED: ~6 text files are mislabelled Federal Bank exports (print "Federal", Tran ID header);
  they correctly route to federal layouts � counted as csb-folder files but not CSB statements.
- Post-spec measure on folder (16 text): 2 v2/csb REVIEW, 6 v2/federal REVIEW, 7 no_layout
  (uncovered fingerprints: `date particulars withdrawal deposit balance` and the two-line-header
  `opening balance/total/closing` family), 1 locked.
- Genuine-CSB files are REVIEW-capped: opening-balance line folds into the chain (self-derived anchor).
- Detector now identifies csb (VERY_HIGH on routed files, LOW on some uncovered fps).

## [UB] re-measure (after CSB_LAYOUT_2/3)

- Folder measure (17 files): **1 VERIFIED** (`4c00cde7`, L3 netbanking export), 10 REVIEW,
  3 honest FAILED, 2 `bank_unconfirmed`, 1 locked/unsupported.
- NEW spec `csb_date_particulars_withdrawal_deposit_balance` (L2): ePassbook
  `Date|Particulars|Withdrawal|Deposit|Balance`; dated `OPENING BALANCE` row; `Closing Balance <amt> CR`
  tail (closing_row_marker); `dd-Mmm-`+`yyyy` split dates (date_tail_re); money cells may print on the
  undated continuation line (continuation_amounts); left-aligned amounts.
- NEW spec `csb_transdate_valuedate_details_refno_debits_credits_balance` (L3): wrapped
  TRANS/VALUE/DETAILS/REF NO./DEBITS/CREDITS/BALANCE header; split dates; dated `B/F` opening row;
  `0.00` unused side (zero_amount_is_empty); left-aligned amounts. `4c00cde7` -> VERIFIED;
  audit implied_open 18402.19 / implied_close 75.62 == printed band anchors (audit tool's
  `printed_close` misreads the label:value summary band; manual confirm exact).
- Honest FAILED: `5b6cd1cb`, `e315b619` (document omits printed balances on scattered rows — orphan
  `CR` suffix tokens; chain fails correctly), `89906828` (1 stray `08-Dec-` date fragment with no year,
  `bad date` schema error — document artifact).
- Still unrouted: `6a734355`, `8d175f67` — same ePassbook fingerprint but ZERO CSB tokens anywhere in
  the text layer -> honest `bank_unconfirmed` (no safe marker).
- The 8 Federal-routed files are confirmed mislabelled Federal Bank exports (FDRL/FEDERALBANK
  evidence, no CSB tokens) — correct routing, not CSB false accepts.
- Cross-bank: 0 false accepts on 360+ pooled files. Status remains SHADOW_ONLY (REVIEW ceiling /
  honest FAILED dominate); not a candidate.

## N5 re-check

- Re-measured at N5 tip: unchanged (1 VERIFIED, 10 REVIEW, 3 FAILED, 2 bank_unconfirmed,
  6 Federal misfiles still route correctly).
- Re-verified `89906828`: the bad-date row is `08-Dec-` + year `2023` separated by the
  interleaved `Closing Balance` line — a mid-cell marker interruption `date_tail_re` cannot
  span (class F ordering), honest FAILED.
- `e315b619`/`5b6cd1cb` re-confirmed: balance cells print on wrong visual lines in the
  interleaved family — beyond N2 continuation semantics (class F/D).
- No spec change this pass.
