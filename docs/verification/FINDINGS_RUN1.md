# Slice 1: findings from run 1 (5 Oct 2026, 21:52 to 22:17)

Branch `feature/statement-verification-v1`. Observe-only: no parser, repair, Excel, upload or UI behaviour was changed.
Run 1 raw outputs are kept in `archive-external/slice1-out_run1_before_fixes/`. Run 2 (after the fixes below) writes to `archive-external/slice1-out/`.

## 1. Environment (from `02_environment.log`)

- Docker image `airco-backend-slice1`, built from `backend/Dockerfile` (`python:3.11-slim`), Python **3.11.17**.
- Live stack: backend container rebuilt with the new code, healthy after ~27 s.

## 2. Stage results of run 1

| Stage | Result | Classification |
|---|---|---|
| git state, image build, environment | PASS | |
| verification tests | FAIL (0 s) | **ENVIRONMENT**: `pytest` is not in `requirements.txt`, so it is absent from the image. Not a test failure. |
| existing suite | FAIL (0 s) | **ENVIRONMENT**: same cause. Not yet run, so there is no pre-existing/ours classification yet. |
| golden PDFs | FAIL (0 s) | **ENVIRONMENT**: same cause. Not yet run. |
| corpus baseline | COMPLETE (WARN) | 561 PDFs selected; see 3. |
| stack rebuild + health | PASS | |
| E2E, 10 uploads (HDFC, ICICI, SBI, Axis, Kotak, 2 each) | **10/10 PASS** | upload accepted, job completed, `verification` block present with all six checks, raw count equals UI count, Excel downloads with 9 sheets |

Fix applied: the script now installs pytest inside each throw-away container (nothing is added to the project) and no longer passes embedded quotes through PowerShell (that also broke the `pip list` step).

## 3. Baseline, run 1

561 PDFs were selected, but 351 belong to the 27 banks that have no processor yet, so the sample was mostly irrelevant. Run 2 samples only banks with a processor (25 per bank) and lists the others separately.

Of the 210 PDFs from supported banks:

- 112 parsed and were verified: **VERIFIED 59, REVIEW 15, FAILED 38**.
- 98 did not reach verification: 22 parsed zero transactions, 19 `NO_TRANSACTION_TABLE`/`NO_TRANSACTIONS`, 12 `INSUFFICIENT_TEXT` (no text layer: unsupported scanned PDFs), 45 rejected as "not this bank's statement" (Indian Bank 11, Bank of India 10, Paytm 8, Unknown 6, IDFC 4, HDFC 2, SBI 2, Baroda 1, Union 1).

Per bank (parsed): Union 13/13 VERIFIED, Baroda 11/12, Karnataka 10/14, Axis 8/13 (5 REVIEW), IDFC 6/10, **HDFC 0/9, SBI 0/12 (1 REVIEW)**, ICICI 2/13.

## 4. Root causes (grouped)

**F1. HDFC declared closing balance is wrong (9 of 9 FAILED). Pre-existing parser bug.**
The balance chain passes with 0 mismatches in every HDFC file, yet the opening-to-closing check fails in all 9, and declared opening equals declared closing in all 9. Cause: `hdfc/structure_validator.py` `CLOSING_BAL_PATTERNS` (`Closing\s*Bal(ance)?\s*[:.\s]*(number)`) reads the summary header row `Opening Balance | Dr Count | Cr Count | Debits | Credits | Closing Bal` followed by a values row, so it captures the first number after the label, which is the opening balance. The opening, Dr/Cr counts and totals patterns fail the same way (printed totals show as "unavailable" although HDFC prints them).
Impact beyond verification: `base_processor` uses `structure.closing_balance` first for reconciliation and aggregation, so HDFC's closing balance in the report is probably wrong. To confirm by opening one HDFC Excel. Not fixed (parser behaviour is out of scope).

**F2. SBI raw rows are wrong, and repair hides it (11 of 12 FAILED).** Pre-existing.
Up to 102 of 148 rows break the balance chain in one statement; in 11 statements repair changed rows (swap/delta repair), after which the existing reconciliation passes. This is exactly the failure mode the slice was built to expose. SBI's structure validator never provides an opening balance (12 of 12), so the opening-to-closing check is skipped.

**F3. ICICI descriptions are empty on many rows (10 of 13 statements, up to 551 rows).** Pre-existing. Hurts categorization. Also 5 ICICI duplicate findings that need a look (see F8), and the printed credit total is mis-extracted in one file (printed 0.86 vs raw 1,259,072.93).

**F4. Indian Bank parser read the column legend as transactions.** In one file 928 of 929 rows break the chain and the description is `TRAN DATE -(MMDD) - INR INR CR TRAN TIME`.

**F5. Karnataka: repair rewrote 326 of 341 rows in one statement** (389 of 451 in another) while the chain still has 42 and 151 raw mismatches. Likely ordering/layout issue; needs a look at one file.

**F6. IDFC and Paytm printed totals disagree with raw sums by up to 25% / 64%.** The balance chain holds for Paytm, so either the rows are complete and the printed figure is mis-extracted, or the printed figure covers a different scope. Manual interpretation needed.

**F7. Header period: boundary rows.** Canara, HDFC and SBI show 1 to 6 rows 1 to 2 days outside the declared period (likely bank value-date behaviour); SBI `647704` has 11 rows dated 2021-01 against a 2021-11 period (probable date-parse problem).

**F8. Duplicate check needs refinement from evidence.** Several "duplicates" have an empty description and may be zero-amount rows that the schema check already reports. Run 2 records amounts and a zero-amount count per group so this can be judged, rather than loosened by guess.

**F9. 45 files were rejected by their own bank's processor as another bank's statement.** The dataset still contains misplaced files (the 1,239-file move plan was excluded, so these are additional or ambiguous). Goes to the manual review queue.

## 5. Changes made after run 1 (all inside Slice 1, observe-only)

- Engine: every non-VERIFIED result now carries machine-readable `reasons` (e.g. `balance_chain_broken`, `declared_closing_differs_from_last_row_balance`, `printed_total_debits_mismatch`, `no_running_balance`), informational `notes` for unavailable evidence, and a `failure_class` (`ROWS_SUSPECT`, `REFERENCE_MISMATCH_ONLY`, `DATA_QUALITY`, `INSUFFICIENT_EVIDENCE`). The state rules were NOT changed.
- Opening/closing check now also reports the chain-implied opening and the last row balance, and whether the declared figures match them (this is what exposed F1).
- `repair_masks_balance_failure` flag on every report.
- Tests: 15 to 22. The central test now also asserts that the existing `compute_reconciliation` reports "reconciled" after repair on a statement with a dropped row, while raw verification fails.
- Baseline runner: samples only banks with a processor, groups outcomes, writes `needs_manual_review.csv`, `banks_without_processor.json` and the per-bank table (pass rates, duplicates, schema, period, average transactions, repair involvement).
- E2E: also asserts that a non-VERIFIED result is explained.

## 6. Manual review queue

`archive-external/slice1-out/needs_manual_review.csv` (written by run 2). Categories: wrong-bank-for-folder, unsupported scanned PDF, no transactions found, FAILED/ROWS_SUSPECT statements. Open questions needing a human: F6 (what the printed totals cover), F7 (is a row dated before the header period legitimate for that bank), F1 impact on delivered reports.

## 7. Not done / limitations

- Existing suite and golden PDFs have not run yet (run 1 failed for environment reasons). Run 2 will give the first real result.
- Verification rules are v1. Thresholds and the FAILED/REVIEW boundary should be reviewed with the run 2 numbers, not tuned to look better.
- Declared closing/opening figures are regex-scraped per bank and are demonstrably unreliable for HDFC; v1 reports the disagreement and its class but does not decide which side is wrong.
- Scanned-PDF detection (`PDFIntegrityValidator`) flagged 12 files as `INSUFFICIENT_TEXT`. It only checks total text length; per-page and mixed-page cases are a known limitation for the next slice.

## 8. Side effect of run 1 (fixed in the script)

Running the existing parsers wrote `backend/data/parser_metrics.json` and `backend/data/unsupported_formats/` into the working tree (the parsers record metrics and samples of unsupported formats there). They are untracked, were not deleted (the sandbox cannot delete) and are safe to remove. Run 2 mounts a throw-away `tmpfs` over `/app/data`, so nothing is written to the repo.
