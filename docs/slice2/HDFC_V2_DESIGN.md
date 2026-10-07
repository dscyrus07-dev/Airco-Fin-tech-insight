# HDFC V2 extractor - design (FROZEN 2026-10-07)

Status: FROZEN after independent falsification review (Devin) and owner approval. Changes after this point need an explicit design amendment.
Phase 1 targets the dominant HDFC layout A (the 1,556-file oracle-grade population plus the 9 small statements). Layouts A' and D are NOT Phase 1; they are queued below.
Evidence base: `HDFC_CORPUS_BASELINE.md` (Docker capture, 2,278 unique PDFs), `ISSUE_hdfc_legacy_closing_balance.md`,
a 332-file printed-summary probe, and a read of the old coordinate parser.

## 0. Principle
V2 is designed from the observed PDF layouts and independent evidence, not from the old parser. The old parser is an oracle for
transaction rows only where it is trustworthy; it is not an authority on balances, sides, or metadata.

Two facts from the evidence shape everything below:
1. **The old oracle is partly circular.** The old coordinate parser decides debit vs credit from the change in running balance (not from the
   column the amount sits in) and uses hard-coded geometry (x bounds 65/260/360/405/485/562, y 230-790). "Zero balance-chain breaks" on its output is therefore
   partly true by construction. Agreement with the oracle is necessary evidence, not sufficient.
2. **HDFC layout A prints its own reference.** The `STATEMENT SUMMARY` block (opening balance, Dr count, Cr count, debits, credits, closing balance) is present
   in **1,593 of 1,659** coordinate files (96.0%; independent full scan by Devin over all pages, 66 files absent, 1 file has it outside the last two pages). Printed opening matches the rows in 1,586 (99.6%), printed closing in 1,585 (99.5%); counts and sums both match exactly in 1,441 (90.5%). (My own last-two-pages scan parsed only 1,547; scan ALL pages.) The old parser read none of it. V2 can verify itself against the bank's own printed numbers.

## 1. Scope and goals
In scope (phase 1): HDFC savings/current account statements in layout A (compacted or spaced header), text-layer PDFs, unlocked (or unlocked by a supplied password
in memory), single account, any page count (1 to 277 seen).
Goals: (a) correct raw rows; (b) independently derived opening/closing/totals; (c) an explicit, explainable verdict per file; (d) deterministic output;
(e) rejection of anything that is not layout A instead of guessing.
Non-goals: repair of the bank's data, categorization, OCR, other HDFC products, replacing the old parser before parity.

## 2. Input / output contract
Implements the existing `StatementExtractor` protocol (`migration/contract.py`): `extract(pdf_path, password=None) -> ExtractionResult`.
- Stage is always RAW. No repair, no classification.
- No exceptions for ordinary failures: set `failure` with a rejection code (section 13).
- Output reuses `NormalizedTransaction` and `StatementMetadata`. Nothing new in the schema. V2-specific evidence goes in `StatementMetadata.extras` and `ExtractionResult.warnings`.
- `printed_total_debit` / `printed_total_credit` are filled from the printed summary (the contract already has them).
- Password is used in memory only, never logged or stored.

## 3. HDFC layouts
| Id | Header (compacted words) | Date | Evidence | Phase |
|---|---|---|---|---|
| A | `Date Narration Chq./Ref.No. ValueDt WithdrawalAmt. DepositAmt. ClosingBalance` (also spaced: `Value Dt Withdrawal Amt. ...`) | dd/mm/yy | 1,659 captured coordinate files, plus 9 tiny statements the old parser rejected | **1** |
| A' | `... Value Date Withdrawal Amount Deposit Amount Closing Balance*`, dd/mm/yyyy, no value-date column | dd/mm/yyyy | 10 files, only via old text/dynamic fallbacks | **Phase 2 / follow-up layout.** Reject `UNSUPPORTED_LAYOUT` in Phase 1; to be added as a layout-spec entry, not a rewrite |
| D | relationship-summary front page, then `Txn Date Narration Withdrawals Deposits Closing Balance` | ? | 2 candidate files (0b46d9623f, 23a5ef8663) | **Future-layout queue.** Reject `UNSUPPORTED_LAYOUT` in Phase 1 |
The Slice 2C registry already recognises A (commit 187f8b7). V2 selects its sub-extractor from that layout id.

## 4. Bank and layout detection
Order: detector (existing, evidence-based) -> layout registry -> V2 header lock.
- V2 accepts a file only if the registry returns the HDFC layout A id AND the table header is found on at least one page AND the HDFC IFSC (`HDFC0nnnnnn`) is present on page 1.
- Detector disagreement (the folder contains ICICI, IndusInd etc.) results in `NOT_HDFC`, never an attempt to parse.
- The old failure mode (lenient text/dynamic fallbacks accepting other banks) is explicitly not reproduced: there is no fallback parser.

## 5. Transaction extraction strategy
Geometry is read from the document, not hard-coded:
1. **The table header is printed on page 1 only** (checked on 14 multi-page files: header on page 1, data rows on every page). Locate the header words on the first page that has them, (`Date`, `Narration`, `Chq./Ref.No.`, `ValueDt`, `WithdrawalAmt.`, `DepositAmt.`, `ClosingBalance`) and take each column's anchor from the header word positions
   (left edge for text columns, **right edge** for the three amount columns, which are right-aligned), and **reuse those anchors for continuation pages of the same file**. Page width is constant inside a file but differs between files (638 pt in the large majority, 595 pt seen; Withdrawal header right edge 466 vs 435), so anchors must be derived per file, never hard-coded. A per-page sanity check compares the date/amount word edges on each later page with the anchors and warns on drift (page size or margin change).
2. Row start = a word at the date column matching `^\d\d/\d\d/\d\d$`. All following lines with no date belong to the previous row's narration (continuation), until the next row start or a table-end marker.
3. Amounts are assigned to a column by right edge proximity to the header anchor, with a tolerance derived from the header spacing. A single amount per row is expected in withdrawal OR deposit, plus the balance.
4. **Side comes from the column, not from the balance change.** The balance chain is then used as an independent check (section 10). A row whose column-side and balance-delta disagree is flagged, never silently "corrected".
5. Table end per page: first line after the last row that starts a footer block (`STATEMENT SUMMARY`, `HDFC BANK LIMITED`, `Generated On`, page footer text). Page header/address blocks are skipped by being above the header row, not by a fixed y.
6. Rows are kept in document order. No sorting, no de-duplication (identical rows can be legitimate).

## 6. Column mapping
Date -> `date`; Narration (+continuations) -> `description`; Chq./Ref.No. -> `ref_no`; ValueDt -> `value_date`; WithdrawalAmt -> `debit`; DepositAmt -> `credit`; ClosingBalance -> `balance`.
Per-row evidence kept in `extras`: page number, source line index.

## 7. Multi-page handling
The header appears on page 1 only; later pages carry rows without a header and use page 1's anchors (with the drift check above). Continuation lines may cross a page break: a narration continuation at the top of a page, with no date, attaches to the last row of the previous page.
Pages with no rows (summary-only last page) are allowed. Rows on a continuation page whose edges drift from the anchors beyond tolerance are a `EXTRACTION_INCONSISTENT` warning for the file.

## 8. Normalization rules
- Dates: `dd/mm/yy` -> ISO `YYYY-MM-DD`; 2-digit year -> 2000+yy (corpus years 2014-2026). Invalid calendar dates are an error for the file, not coerced.
- Amounts: `Decimal`, commas removed, no float anywhere. Negative balances (overdraft, seen as large negative closing) accepted; a trailing `Cr`/`Dr` suffix handled if present.
- Description: narration lines joined with a single space, whitespace collapsed, original case kept. (The comparator already tolerates whitespace/case differences as MINOR_DIFFERENCE.)
- Empty ref/value date -> `""` / `None`.

## 9. Opening / closing balance calculation (independent; never inherited)
- `opening_from_rows` = first row balance - first credit + first debit.
- `closing_from_rows` = last row balance.
- `StatementMetadata.opening_balance` / `closing_balance` are set from these derived values, with the printed summary as a cross-reference, never from a legacy regex.
- Printed opening/closing from the `STATEMENT SUMMARY` are stored in `extras` and compared (section 10).

## 10. Balance-chain validation (checks, each reported separately)
C1 chain: for every row, `prev_balance + credit - debit == balance` (Decimal, zero tolerance). Failing rows listed.
C2 side agreement: column side vs sign of balance change per row. This is the check the old parser could not do.
C3 printed opening and closing vs derived. Expected to match whenever C1 holds.
C4 printed Dr/Cr counts and debit/credit sums vs derived. **Rule found (evidence below):** HDFC prints a reversal as a NEGATIVE amount in the Withdrawal column (e.g. `-20,000.00`, balance goes up) or, rarely, in the Deposit column. The bank's summary counts it on the printed side with a negative amount. Canonical output keeps non-negative debit/credit consistent with the balance (a negative withdrawal becomes a credit), so V2 flags the row `extras.reversal=true, printed_side=withdrawal|deposit` and reconciles C4 with:
   `printed_dr_count = debit_rows + nW - nD`, `printed_cr_count = credit_rows - nW + nD`, `printed_debits = sum_debits - sW - sD`, `printed_credits = sum_credits - sW - sD`
   (nW/sW = count/sum of negative withdrawal rows, nD/sD = negative deposit rows). Evidence: of the 150 files whose raw counts/sums differ from the printed summary, this rule explains 124 exactly (83%); the other 26 are mostly files with balance-chain breaks or an unparsed negative token and are first-slice investigation items. With the rule, C4 becomes an exact check, not a REVIEW bucket.
Classification of a C4 mismatch (validated by an independent full run: 152 mismatching files of 1,593; reversal signature covers 130, 94 of them adjacent pairs; 22 are chain-broken row loss):
   - negative-amount tokens found and the rule above reconciles exactly -> `VERIFIED` with the reversal rows flagged;
   - equal-delta signature (dDr = -dCr and dDebits = dCredits) without a proven reversal token -> `REVIEW`; adjacency is NOT required (36 files carry the signature without an adjacent pair);
   - mismatch together with a broken chain (row loss/duplication) -> `FAILED`, never REVIEW.
C5 date monotonic non-decreasing (warn on exception).

## 11. Statement-period validation
Header `From : dd/mm/yyyy To : dd/mm/yyyy` is parsed. The rule is bidirectional. Rows outside the period are a warning, not a failure: 372 coordinate files (374 including the text/dynamic captures) have them, rows after the printed To in 299 files (never more than 1 day) and rows before From in 99 files (up to 62 days earlier; 26 files have both). A hard rule would reject good statements. First/last row dates are recorded in `extras`.

## 12. Confidence scoring (deterministic, explainable)
No ML. Verdict from the checks:
- `VERIFIED`: C1, C2, C3 pass; C4 matches or the file has no summary; no structural warnings.
- `REVIEW`: C1-C3 pass but C4 variance, period warning, or continuation-attach warnings.
- `FAILED`: any of C1, C2, C3 fails, or counts/sums disagree with unexplained rows.
Numeric confidence is not invented; the verdict plus the list of passed/failed checks is the confidence. Verdict is the existing verification vocabulary so the comparator/verification tooling can consume it.

## 13. Error / rejection categories (V2 returns `failure`, no rows)
`LOCKED`, `SCANNED_NO_TEXT`, `NOT_HDFC`, `UNSUPPORTED_LAYOUT` (A', D, unknown header), `NO_TABLE_HEADER`, `NO_ROWS` (header found, zero rows, and printed summary does not say zero), `EXTRACTION_INCONSISTENT` (hard geometric ambiguity: overlapping amount columns). A legitimately empty statement (printed counts 0/0) returns success with zero rows.

## 14. Canonical output mapping
`ExtractionResult(engine="v2", stage="RAW", metadata=StatementMetadata(bank_name="HDFC Bank", bank_key="hdfc", account_number, account_holder, opening/closing from rows, statement_from/to from header, extras={printed_summary, checks, first/last row date, layout_id}), transactions=[NormalizedTransaction...], printed_total_debit/credit, verification_status, warnings)`.
Account number and holder are read from the page-1 header block (`AccountNo`, name line). PII stays inside the result object; logs carry only SHA-256 and counts.

## 15. Regression strategy (the oracle corpus is a behavioural contract, adjudicated)
Tiers, in order:
- T0 unit fixtures: synthetic word lists (no customer PDFs in git) for header anchoring, continuation, page breaks, amount right-edge assignment, summary parsing, date/Decimal rules.
- T1 golden snapshots: the 2 available row-for-row matches (366, 577 rows) become mandatory tests.
- T2 oracle: the 1,556 oracle-grade files, via `run_parity`. Each difference between V2 and the old capture must be **classified**, never waved through: V2_BUG, OLD_BUG (side/amount from balance delta; metadata), AMBIGUOUS. Adjudication uses the printed summary and column evidence. Goal: V2_BUG = 0, AMBIGUOUS minimised and listed.
- T3 flagged: the 25 chain-break and 103 suspect-row files are reported, not gated.
- T4 small statements: the 9 confirmed layout-A files the old parser rejected; truth = printed summary + visible rows.
- T5 negatives: the 389 NON_HDFC and the 35 old text/dynamic captures must not yield rows from V2 (reject with a code).
Shadow run first (V2 alongside old, results stored, never user-visible), parity report, then V2 primary, then delete old HDFC code.

## 16. Acceptance criteria
Primary: on the oracle corpus, V2 produces transaction-level output consistent with the trusted legacy capture **while independently calculating and validating balances**, and does not inherit the legacy closing-balance defect.
Concretely:
1. V2_BUG = 0 on T2; every old-vs-V2 difference classified; OLD_BUG differences documented with evidence.
2. For every successful file: opening and closing are derived from rows; where printed, they match (C3) in 100% of VERIFIED files. Metadata is never taken from the legacy regex.
3. C2 (side agreement) reported per file; zero unexplained disagreements.
4. T1 golden: 100% row-identical. T4: all 9 recovered and VERIFIED against printed summary.
5. T5: 0 files produce rows when they should be rejected.
6. Deterministic: byte-identical re-run output. No float. No password or PII in logs.
7. Performance: no worse than 2x the old coordinate parser wall time on the 277-page file; memory bounded per page.
8. All new code covered by T0 tests; no PDFs or customer data committed.

## 17. Explicitly excluded from V2 phase 1
Layout D (relationship-summary statements), layout A' until reviewed, scanned/image PDFs, credit-card and loan statements, payslips/receipts, multi-account statements, other banks (including those misfiled in the HDFC folder), any text/dynamic "best effort" fallback, repair of bank data, categorization, Excel output, replacing metadata consumers (separate P1 issue).

## 18a. Layout-family extension point
Layout-specific facts live in a declarative `LayoutSpec` (header words that anchor each column, which columns exist, date format, side encoding, summary labels). The shared machinery (anchoring, row assembly, normalization, checks) reads the spec. Adding A' or D later means adding a spec entry plus fixtures, not changing the machinery. This is the pattern intended for other banks.

## 18. Proposed module layout
`app/services/statement_engine/extractors/hdfc/` with pure, individually testable modules: `anchors.py` (header -> column anchors), `rows.py` (words -> rows), `summary.py` (printed block), `metadata.py` (page-1 block, period), `checks.py` (C1-C5), `extractor.py` (orchestration, implements `StatementExtractor`). Only `extractor.py` touches pdfplumber.

## 18b. Review notes folded in (independent falsification review, Devin)
- Old-parser failure on the 9 one-page statements is the `< 3 transactions` validity gate (`parser.py` line 310), not the y-bounds (their rows sit at y~251, inside the band).
- Column side vs balance-derived side disagrees on 7 of 54,071 rows (0.013%) in a 150-file sample, all of them reversal rows; so anchored column side + C2 flagging is safe.
- Date-first narrations exist only in non-layout-A captures; the column-anchored date test stays.
- For the locked check use pdfplumber/pikepdf; pypdf keeps `is_encrypted` true for owner-encrypted files even after `decrypt("")`.
- Coordinate median rows is 289.

## 19. Open questions for review
1. ~~C4 variance~~ RESOLVED: negative-amount reversals (section 10). Open: the 26 unexplained files (list kept locally).
2. ~~Rows outside the printed period~~ RESOLVED (data): 372 coordinate files; rows after the printed "To" date in 299 (never more than 1 day later), rows before "From" in 99 (97 of them by 1 day, 2 files by 10+ days; 26 files have both). Policy: warning, never a failure; record first/last row date.
3. ~~2-digit year~~ RESOLVED (data): rows span 20yy only (2014-2026); 0 invalid calendar dates across all captured coordinate rows. Rule 2000+yy stands; invalid date is a file error.
4. ~~Tiny statements~~ RESOLVED (data): only 1 coordinate file in the captured set has <=3 rows and the 9 rejected files have 1-2 rows. No minimum-row rule.
5. ~~Layout A'~~ DECIDED: Phase 2 follow-up. ~~Layout D~~ DECIDED: future-layout queue.
6. ~~Printed summary absent~~ RESOLVED: absent in 66 of 1,659 files (4.0%). Policy: a file without a parseable printed summary is at most REVIEW, never VERIFIED. The summary scan covers all pages.
7. Shadow-run storage and retention (7-day compliance applies to stored captures).
