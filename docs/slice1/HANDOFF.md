# Slice 1 handoff: Verification V1 (observe-only)

Branch `feature/statement-verification-v1`, created from `main`. Nothing is committed. Evidence: `docs/slice1/out_run2/` (baseline, E2E, logs), `docs/slice1/out_run1_before_fixes/` (first run), `docs/slice1/FINDINGS_RUN1.md`.

## 1. Executive summary

Verification V1 works end to end. It runs on the raw parser rows before `repair_transaction_sides`, is attached to every processing result as an additive `verification` block, and reaches the job API response. A live run through the running stack (10 real uploads: HDFC, ICICI, SBI, Axis, Kotak) passed all contract checks and left the Excel at 9 sheets.

The baseline answers the question the slice was built for. Of the 350 PDFs sampled from the 14 banks that have a parser:

- **168 parsed**: VERIFIED 88 (52%), REVIEW 25 (15%), FAILED 55 (33%).
- **182 did not produce output at all**: 88 rejected as another bank's statement, 66 where no transactions were found, 28 with no text layer (unsupported scanned PDFs).

So the larger problem today is coverage and routing, not accuracy of what parses. Among statements that parse, the failures group into a few root causes (section 5), several of which are in how reference figures are scraped from the statement header, not in the transaction rows.

## 2. What changed (files and why)

Modified (additive only):
- `backend/app/services/banks/_shared/base_processor.py`, +27 lines: one hook after parsing and before repair that runs verification on the raw rows (guarded, cannot raise), attaches the repair stats afterwards, and puts `verification` on `BasePipelineResult` / `to_dict()`. CRLF preserved.
- `backend/app/services/frontend_result_builder.py`, +4 lines: passes `verification` through. Without this the block was dropped before the API response.

New:
- `backend/app/services/verification/{__init__,models,engine}.py`: pure stdlib. Six checks, state rules, `reasons`, `notes`, `failure_class`, `repair_masks_balance_failure`.
- `backend/tests/verification/{__init__,test_engine}.py`: 22 synthetic tests.
- `backend/scripts/baseline_run.py`, `backend/scripts/e2e_smoke.py`: baseline runner and live-stack contract test.
- `docs/slice1/` (run script, `RUN_SLICE1.bat`, run guide, findings, this file), `docs/SYSTEM_MAP.md`.

Not changed: parsers, repair, reconciliation, categorisation, Excel, upload, jobs, frontend, dataset. No new dependency in `requirements.txt` (pytest and pytest-asyncio are pip-installed inside throw-away test containers only).

Side effect to clean up: run 1 left `backend/data/parser_metrics.json` and `backend/data/unsupported_formats/` (the existing parsers write them). Untracked, safe to delete. Run 2 did not write there (tmpfs).

Git at start: branch `main`, 279 status lines (272 files differ only by CRLF/LF; the one real change is `.gitignore` +4). Recorded in `docs/slice1/baseline_git_*.txt`. Now: 3 tracked files with real changes (`.gitignore`, `base_processor.py`, `frontend_result_builder.py`).

## 3. Verification semantics

States: `FAILED` if the balance chain, opening-to-closing or printed-totals check fails; `REVIEW` if only schema, duplicate or header-period failed, or if there was no running balance to verify against; `VERIFIED` if nothing failed and the balance chain passed. A skipped check is never a failure and never a pass: it appears in `notes` (`printed_totals_unavailable`, `opening_or_closing_unavailable`, `header_period_unavailable`) and only blocks VERIFIED when it is the balance chain.

Every non-VERIFIED result has `reasons` (e.g. `balance_chain_broken`, `declared_closing_differs_from_last_row_balance`, `printed_total_debits_mismatch`) and a `failure_class`: `ROWS_SUSPECT`, `REFERENCE_MISMATCH_ONLY` (rows are internally consistent but a declared/printed figure disagrees), `DATA_QUALITY`, `INSUFFICIENT_EVIDENCE`. Repair stats are recorded, never scored.

## 4. What was tested and the results

| Test | Command / stage | Result |
|---|---|---|
| Verification unit tests | `pytest tests/verification` in the Python 3.11.17 image | **22 passed** |
| The key failure-mode test | `test_dropped_row_fails_even_though_repair_would_hide_it` | passes: raw verification FAILED; after `repair_transaction_sides` the existing `compute_reconciliation` reports reconciled with 3 rows instead of 4 |
| Live UI/API contract | `e2e_smoke.py`, 10 uploads | **10/10 pass** (9 checks each: upload, job, block present, v1/observe-only, six checks, non-VERIFIED explained, raw count vs UI count, Excel opens, 9 sheets) |
| Corpus baseline | `baseline_run.py`, 25 per bank, move-plan files excluded | **COMPLETE**, 350 PDFs |
| Existing suite | `pytest tests` | **BLOCKED, PRE-EXISTING**: `tests/test_pipeline_orchestrator.py` imports `_tag_as_others`, which does not exist in `pipeline_orchestrator.py` (committed that way in the initial commit; neither file is modified). The collection error aborted the whole session, so no existing test result yet |
| Golden PDFs | `pytest tests/golden` | 6 unit tests pass; the live-pipeline golden test failed with "no matching PDF" because run 2 mounted the wrong folder. **ENVIRONMENT**; golden PDFs are in `samples/` |

Both blocked stages are fixed in the script (`--continue-on-collection-errors`, pytest-asyncio, correct golden mount) and need one rerun: `RUN_SLICE1.bat` with `-TestsOnly` (about 2 minutes). Until then "existing suite" and "golden" are NOT proven.

Environment: Docker image from `backend/Dockerfile` (`python:3.11-slim`), Python 3.11.17, pdfplumber 0.11.9, pdfminer.six 20251230, PyMuPDF 1.27.2.3, pypdf 5.1.0, pypdfium2 5.14.0, pikepdf 10.5.1, openpyxl 3.1.2, xlsxwriter 3.2.9, pandas 3.0.2, numpy 2.1.3, pytest 9.1.1.

## 5. Baseline results (supported banks, parsed statements only)

| bank | PDFs | parsed | VERIFIED | REVIEW | FAILED | not parsed |
|---|---|---|---|---|---|---|
| axis | 25 | 21 | 14 | 7 | 0 | 4 |
| bank_of_baroda | 25 | 14 | 13 | 0 | 1 | 11 |
| bank_of_india | 25 | 5 | 3 | 0 | 2 | 20 |
| canara | 25 | 3 | 2 | 0 | 1 | 22 |
| hdfc | 25 | 11 | 1 | 0 | 10 | 14 |
| icici | 25 | 21 | 5 | 10 | 6 | 4 |
| idfc | 25 | 22 | 9 | 0 | 13 | 3 |
| indian_bank | 25 | 4 | 3 | 0 | 1 | 21 |
| karnataka | 25 | 22 | 15 | 2 | 5 | 3 |
| kotak | 25 | 4 | 4 | 0 | 0 | 21 |
| paytm | 25 | 9 | 3 | 5 | 1 | 16 |
| sbi | 25 | 17 | 1 | 1 | 15 | 8 |
| union | 25 | 15 | 15 | 0 | 0 | 10 |
| unknown | 25 | 0 | 0 | 0 | 0 | 25 |

Check results across the 168 parsed (pass / fail / skip): schema 145/23/0, balance chain 124/43/1, opening-closing 102/40/26, printed totals 17/13/138, duplicates 157/11/0, header period 139/9/20. Failure class of the 70 non-VERIFIED: ROWS_SUSPECT 59, DATA_QUALITY 11, REFERENCE_MISMATCH_ONLY 10. The full per-bank table (pass rates, average transactions, repair involvement) is in `out_run2/baseline_summary.md`.

Printed totals can only be checked for 30 of 168 statements (138 skipped): most banks' structure validators do not expose them, and for HDFC the extraction fails (below).

## 6. Root causes (grouped; evidence is in the logs and CSVs)

1. **HDFC: the declared closing balance is the opening balance (10 of 11 FAILED).** Balance chain passes 11/11; declared opening matches the chain 11/11; declared closing differs from the last row balance in 10/11. `hdfc/structure_validator.py` `CLOSING_BAL_PATTERNS` capture the first number after the label, which in HDFC's summary table is the opening balance; the opening, Dr/Cr count and totals patterns fail the same way. `base_processor` uses `structure.closing_balance` first for reconciliation and aggregation, so HDFC reports are probably showing a wrong closing balance. Rows are fine. *Pre-existing, unfixed (parser behaviour).*
2. **SBI: raw rows are wrong and repair rewrites them (15 of 17 FAILED).** 259 of 4,885 rows break the chain; repair changed exactly 259. The opening balance is never extracted for SBI, so opening-to-closing cannot run. After repair the existing pipeline passes. Whether the repaired amounts are right needs a hand check against the PDFs (the balance column is trustworthy, so repair is often right, but nothing in the pipeline records that it happened).
3. **IDFC: 13 of 22 FAILED**, 69 mismatching rows, all repaired; printed totals disagree in 3 of 19.
4. **Karnataka: repair changed 708 rows although only 148 broke the raw chain** (5 statements). Repair is cascading beyond the raw failures, most likely from a wrong declared opening (declared closing differs from last row in 2). Needs one file inspected.
5. **ICICI: empty descriptions in 15 statements** (DATA_QUALITY, hurts categorisation); 4 duplicate findings; printed credit total mis-extracted (0.86 vs 1,259,072.93).
6. **Axis: 7 REVIEW from rows without exactly one amount**, probably non-transaction lines (opening balance line, wrapped text). The next run records what those rows are.
7. **Paytm and IDFC printed totals** disagree with raw sums; for Paytm the chain holds, so either the printed figure covers another scope or is mis-extracted. Human judgement needed.
8. **Header period:** 9 statements have rows 1 to 2 days outside the declared period (likely bank value-date behaviour); one SBI file has 11 rows a year early (probable date parse issue).
9. **Coverage:** Kotak 21 of 25 not parsed (17 parse zero transactions), Canara 22 of 25 (`NO_TRANSACTION_TABLE`), Indian Bank 21 of 25 (wrong-bank rejections), Bank of India 20 of 25, Paytm 16 of 25, "unknown" 25 of 25 (17 scanned). These are parser layout gaps or misfiled documents (an ICICI folder file is a payslip).
10. **Wrong-bank rejections: 88.** The bank's own processor refuses the file. Some are misfiled in the dataset; some may be genuine statements the processor's marker check rejects. Not separable without human review.
11. **Scanned / no text layer: 28 files**, correctly flagged as `INSUFFICIENT_TEXT` (no OCR). Detection only checks total text length.

## 7. What remains

MANUAL REVIEW REQUIRED
- `out_run2/needs_manual_review.csv` (251 rows): 88 wrong-bank, 66 no-transactions-found, 59 ROWS_SUSPECT, 28 scanned, 10 REFERENCE_MISMATCH_ONLY.
- Open one HDFC Excel and confirm the closing balance shown is wrong (finding 1).
- Hand-check 3 SBI statements: are the repaired amounts correct? (finding 2).
- Paytm/IDFC: what do the printed totals cover? (finding 7).
- Business decision: how should MyPaisaa receive REVIEW and FAILED statements?

NEXT ENGINEERING STEP
- Rerun with `-TestsOnly`, then classify the existing-suite and golden results (PRE-EXISTING / OURS / ENVIRONMENT / UNRELATED).
- Fix or delete the broken import in `tests/test_pipeline_orchestrator.py` (pre-existing).

KNOWN LIMITATIONS
- V1 cannot detect an error that keeps the balance chain intact (e.g. a wrong description, or consistently swapped amounts that still chain); counts can only be cross-checked for the few banks that print them.
- Declared opening/closing and printed totals are regex-scraped per bank and are unreliable for at least HDFC and ICICI. V1 reports the disagreement and its class; it does not decide which side is wrong.
- Duplicate check: some findings have empty descriptions or zero amounts; next run shows amounts so the rule can be judged on evidence.
- State thresholds are v1. Do not tune them to improve the percentages.

OUT OF SCOPE (documented, not done)
- Fixing parsers (HDFC patterns, SBI sides, Karnataka, Indian Bank legend rows), changing repair, Excel, UI, the 1,239-file move, OCR, layout families.
- Security items from the audit (unauthenticated download, `api_key` and `pdf_password` returned in the job payload via `GET /api/jobs/{id}`), noted again: the job response includes `input_data`.

## 8. Recommendation for Slice 2 (from the evidence, not the original plan)

The data says the biggest loss is not accuracy but files that never produce output (182 of 350, 52%), and the next biggest is figures scraped wrongly from headers. So:

1. **Content-based bank detection and routing first.** 88 of 182 non-parsed files were rejected by the folder's bank processor. Detect the bank from the PDF text, route to the right processor, and re-run this same baseline: the change in `wrong_bank_for_folder` is directly measurable. It is also what the multi-upload UI needs.
2. **Reference-extraction fixes, one bank at a time, measured by the baseline** (HDFC closing/opening/counts/totals first: it should flip about 9 FAILED statements to VERIFIED with no change to rows; then ICICI printed totals, SBI opening).
3. **Make repair visible in quality scoring** (observe first): SBI, IDFC and Karnataka show repair rewriting 259, 69 and 708 rows.
4. **Only then** layout work for Kotak, Canara, Indian Bank and Bank of India, with the verification engine as the acceptance test. Do not start gating output on verification until items 1 and 2 have cleaned the reference noise.

---

## Addendum: existing suite and golden classification (run of 6 Oct 2026, 10:57)

Method: the same tests were run on a copy of `backend/` with `base_processor.py` and `frontend_result_builder.py` reverted to HEAD and the verification package removed (`out/logs/04b_*`, `05b_*`).

| Suite | With our changes | Without our changes | Verdict |
|---|---|---|---|
| Verification tests | 22 passed | n/a | OURS, green |
| Existing suite | 9 failed, 134 passed, 1 collection error | 9 failed, 134 passed, 1 collection error (identical FAILED list) | **All PRE-EXISTING. Zero failures caused by Slice 1.** |
| Golden | 6 passed, 1 failed | 6 passed, 1 failed (same test) | **PRE-EXISTING** |

Per failure:
- `tests/test_pipeline_orchestrator.py` collection error: imports `_tag_as_others`, which `pipeline_orchestrator.py` no longer has. PRE-EXISTING (stale test or removed function).
- `test_axis_parser` x2, `test_canara_parser`, `test_icici_parser`: the tests read PDFs from `/samples/New Bank Samples Results/...`, a path that does not exist in the container. ENVIRONMENT in this run (fixtures not mounted); also fail without our changes. Re-run with that folder mounted before calling them code bugs.
- `test_finbit_analytics` x2, `test_json_rule_engine` x2: PRE-EXISTING, unrelated to verification.
- `test_api_key_service ... rate_limit_allows_then_blocks`: PRE-EXISTING, unrelated (likely needs Redis/time).
- Golden `910010002434549_1661418866251.json: category assignment mismatch`: PRE-EXISTING (snapshot vs current categorisation in the dirty tree). Not ours; needs a decision on whether the snapshot or the rules are right.

Known defect in my script: the A/B judge's summary line for stage 04b ("16 pre-existing, 2 ours, 2 fixed") is WRONG. It miscounts because it picks up non-test lines. The raw logs show the FAILED lists are identical, so the true split is 10 pre-existing / 0 ours. Stage 05b is marked PASS in RUN_STATUS although pytest exited 1; this is the intended "comparison stage", but the label is confusing. Fix the judge before reusing the script.

Final status: Slice 1 added no test failures. Remaining failures are pre-existing or environment and are listed above for manual decision. Stop before Slice 2.
