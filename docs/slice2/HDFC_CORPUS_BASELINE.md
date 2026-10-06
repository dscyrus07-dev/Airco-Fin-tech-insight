# HDFC corpus baseline and layout-diversity report (old-parser capture, Docker)

Source: full capture of `New Dataset/Ready to Use PDF/HDFC Bank` inside the backend Docker image
(Python 3.11.17, pdfplumber 0.11.9, pikepdf 10.5.1), commit `0b1517f`, tool v5, one producer fingerprint on all results.
Identity = SHA-256. Raw rows are pre-repair. Captures live in `comparison/hdfc_docker/` (gitignored, customer data).
Status: DOCUMENTATION ONLY. HDFC V2 extraction has not been started.

## 1. Baseline table
| Item | Files (2,349) | Unique SHA-256 (2,278) |
|---|---|---|
| Duplicates | 71 extra copies in 54 groups | |
| CAPTURED (old parser produced rows) | 1,716 | 1,694 |
| LOCKED (needs password; no password used) | 61 | 61 |
| SCANNED_UNSUPPORTED | 24 | 20 |
| NON_HDFC (detector names another bank AND HDFC structure check failed) | 419 | 389 |
| PARSER_ERROR (see section 4, mostly not bank statements) | 129 | 114 |
| Rows captured | | 662,011 |

Notes
- "Locked PDFs" folder: 1,337 of its files captured normally, so most were already opened/decrypted (or owner-password only). Only 61 truly need a password. The earlier "1,423 locked" estimate was folder-based, not real.
- Folder membership is not truth: 389 unique files (17%) belong to other banks (ICICI 201, IndusInd 50, ...).

## 2. What is actually HDFC-native
Of 1,694 CAPTURED, only the `coordinate` parse path is the real HDFC layout:

| Group | Unique files | Notes |
|---|---|---|
| coordinate, detector = hdfc | **1,659** | The HDFC-native population. All detector-agree. |
| text / dynamic fallback | 35 | 15 detector=hdfc, 12 sbi, 5 unknown, 2 union, 1 axis. Mostly other-bank statements the lenient fallback accepted (e.g. an SBI file with the date inside the description). **Quarantine: do not use as oracle.** |

Oracle-grade candidates = coordinate AND zero balance-chain breaks AND not ROWS_SUSPECT: **1,556 files / 594,516 rows**.
Needs review: 25 coordinate files with chain breaks (122 breaks), 103 coordinate ROWS_SUSPECT (mostly heuristic: duplicate_check 81, header_period_check 372 incl. rows after the printed period).
Old-parser faults on the text/dynamic set are heavy: 21 of 35 have chain breaks, one has 248 breaks in 293 rows.

## 3. Layout diversity (HDFC-native, coordinate)
| Layout | Table header (compacted words) | Date | Value date | Files |
|---|---|---|---|---|
| A (dominant, 99%) | `Date Narration Chq./Ref.No. ValueDt WithdrawalAmt. DepositAmt. ClosingBalance` | dd/mm/yy | yes | 1,646 |
| B | `Date Narration Chq./Ref.No. Value Dt Withdrawal Amt. Deposit Amt. Closing Balance` (spaced words) | dd/mm/yy | yes | 12 |
| C | header not found, still parsed by coordinate | dd/mm/yy | yes | 1 |

Not HDFC-native but captured by fallback: header `... Value Date Withdrawal Amount Deposit Amount Closing Balance*` (dd/mm/yyyy, no value date column; 10 files, text/dynamic) and header-less statements (21 files, text). Treat as separate layouts/other banks until proven HDFC.
Pages: 1 to 277 (62 coordinate files have >= 100 pages). Rows per file: 3 to 3,838 (median 286). First-transaction years: 2020-2026 (one 2014 outlier).
Slice 2C registry: UNKNOWN on 1,657 of 1,694 (97.8%), because layout A/B headers are not in the registry.

## 4. PARSER_ERROR triage (114 unique) - not the same as "old parser failed on HDFC"
By detector: none 79, hdfc 33, axis 1, union 1. Reading the first page:
- Not bank statements: payslips, GST receipts, a loan statement, a credit-card statement, company letterheads (detector=hdfc fires on HDFC IFSC/name in the text). about 21 of the 33 detector=hdfc (the rest are the candidates below plus one IDFC-style statement).
- Other-bank statements (e.g. IDFC "Account Number ... Transaction date : From ..."): the bulk of the detector=none group.
- **Real HDFC candidates the old parser missed: 9 confirmed layout-A files** (1-page, 1-2 transactions, hard-coded y-bounds likely cause) plus 2 files in a different HDFC format (relationship-summary front page, header `Txn Date Narration Withdrawals Deposits Closing Balance`), all NO_TRANSACTIONS. Needs manual confirmation (list by SHA in `manifest.csv`: filter `error_code=NO_TRANSACTIONS` and `detector_bank=hdfc`).
Conclusion: the old structure validator is weak both ways: it lets non-HDFC docs reach the parser (and the text fallback even succeeds on some), and it rejects some real HDFC variants.
Detector-says-HDFC but excluded as NON_HDFC: 6 files (to inspect).

## 5. Verification and the closing-balance defect
- Verification v1 (raw rows): FAILED 1,613 / VERIFIED 58 / REVIEW 23. 1,493 are REFERENCE_MISMATCH_ONLY, i.e. rows consistent, only the metadata reference is wrong.
- Metadata `closing_balance` vs rows: equals the pre-first-transaction balance in **1,587** files (93.7%), None in 85, other in 18, correct in only **4**. `opening_balance` None in 99.8%. See `ISSUE_hdfc_legacy_closing_balance.md` (P1, separate).
- CORRECTION (after commit 5): the old parser extracted printed Dr/Cr counts and totals in 0 files, but HDFC layout A DOES print a `STATEMENT SUMMARY` block (opening balance, Dr count, Cr count, debits, credits, closing balance). A probe of 332 coordinate files found it in 311 (94%); printed opening matched the rows in 310, closing in 309, and counts/sums in 278 (the rest differ by a reversal-pair pattern or by row loss, under study). V2 can therefore use an independent printed reference.
- Old side/amount logic: the old coordinate parser decides debit vs credit from the balance change (not the column), with hard-coded x/y bounds (y 230-790). Its 'zero chain breaks' is therefore partly circular; the oracle must be adjudicated, not trusted blindly (see HDFC_V2_DESIGN.md).

## 6. Golden cross-check
2 of 5 snapshots had a capture, both 100% row-identical (366/366, 577/577 on date, amount, balance). Two source PDFs are not in this corpus; the 61XXXXX357 golden is a Kotak misfile.

## 7. Implications for the V2 extractor (design inputs, not implementation)
1. Design for Layout A (99%) and B (spaced header) first; both are fixed-column coordinate tables with value date and ref no.
2. Do not copy the old text/dynamic fallbacks; they are the main source of wrong rows.
3. Bank identification must precede extraction; the old structure validator should not be reused for it.
4. Compare V2 against the 1,556 oracle-grade files first; review the 25+103 flagged files by hand before treating old output as truth there.
5. Compare balance-chain and sums, not metadata; metadata closing is a known defect. Use the printed STATEMENT SUMMARY as an independent reference.
6. Add Layout A/B headers to the Slice 2C registry (small, separate change) so analyze-first stops reporting UNKNOWN for HDFC.

## 8. Tool notes
- Resume re-hashes all inputs on every chunk (59 chunks, about 2h47m wall). Acceptable; a hash cache would make resume O(new files).
- Result schema has no per-file timing (removed on purpose for determinism).
- `manifest.csv` records source file names verbatim; some names in `Locked PDFs/` embed passwords. Keep it local.
