# csb â€” onboarding notes

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
  they correctly route to federal layouts — counted as csb-folder files but not CSB statements.
- Post-spec measure on folder (16 text): 2 v2/csb REVIEW, 6 v2/federal REVIEW, 7 no_layout
  (uncovered fingerprints: `date particulars withdrawal deposit balance` and the two-line-header
  `opening balance/total/closing` family), 1 locked.
- Genuine-CSB files are REVIEW-capped: opening-balance line folds into the chain (self-derived anchor).
- Detector now identifies csb (VERY_HIGH on routed files, LOW on some uncovered fps).
