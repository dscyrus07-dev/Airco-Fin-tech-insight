# Old HDFC raw-output capture — pilot report

Scope kept: existing HDFC parser/validators unchanged, no V2 extractor, schema unchanged, nothing committed, full corpus NOT run.

## 1. What was built
- `backend/scripts/capture_old_output.py` — runs steps 1-4 of the old HDFC pipeline unchanged (PDF integrity, structure validator, `HDFCParser.parse`, `HDFCTransactionValidator`) plus verification v1 on the RAW parser rows, exactly as `BaseBankProcessor` orders them. It never runs `repair_transaction_sides`, reconciliation, classification, recurring, aggregation or Excel.
- `backend/app/services/migration/old_result.py` — `load_extraction_result()` turns an `old_result.json` into the comparator's `ExtractionResult`.
- `backend/tests/migration/test_old_result.py` — 5 tests on a synthetic document (no customer data).
- `.gitignore`: added `comparison/` (captures contain customer data).

## 2. Output layout (default `<repo>/comparison/hdfc/`, git-ignored)
`results/<sha256>.json` per PDF + `manifest.json` + `manifest.csv`. PDFs are referenced by path and SHA-256, never copied. Each `old_result.json` (schema `airco.old_result/1`) holds: source (sha256, size, name), producer fingerprint (git commit, SHA-256 of the 8 parser-related source files, Python and library versions, tool version), status + error, per-step results, full structure metadata, printed totals, native RAW rows (incl. `raw_line`, `line_number`), post-validation rows, a normalized block (documented boundary: `to_normalized` on raw rows, amounts as strings), row-derived facts (opening/closing from rows, sums, balance-chain breaks), verification v1 report, and detector context (curation only). No passwords are accepted or stored; encrypted PDFs are recorded as `LOCKED`.
Manifest columns: path, sha256, status, error, parse method, transaction/debit/credit counts, opening/closing, printed Dr/Cr counts, verification state, masked account, detector bank, chain breaks, closing-from-rows, result path.
Properties verified: deterministic (16/16 byte-identical on a full forced re-capture; parser timing is stripped), resumable (re-run reused 16/16), per-file isolation (every failure recorded, run continues), `--time-budget` for chunked runs.

## 3. Pilot (16 PDFs: the golden-covered ones, 2 locked-folder files, size extremes, even spread)
Result: 8 OK, 8 ERROR.
- 8 OK: all `coordinate` parse method, 24-616 rows, balance chain unbroken (0 breaks) on every one, detector agrees (hdfc).
- 8 ERROR, none a true old-parser failure on a real HDFC statement:
  - 6 `HDFCStructureError` "does not appear to be an HDFC statement": detector says icici, indusind or kotak (or unknown). These are misfiled files in the HDFC dataset folder (one is the Kotak file sitting in `tests/golden/hdfc/`).
  - 2 `PDFIntegrityError`: scanned/no text (0 chars).
- Cross-check with existing golden snapshots: 4/4 OK golden PDFs match in row count (392, 366, 577, 24) and every row's date, debit, credit and balance. The 5th golden HDFC file is the Kotak misfile (golden also records 0 rows).

## 4. Findings that matter before V2
1. **Old metadata closing balance is wrong on 8/8 OK statements.** `HDFCStatementMetadata.opening_balance` is None and `closing_balance` equals the balance BEFORE the first transaction (e.g. 15541.29 vs the real closing 22772.71). Rows are correct (chain unbroken); verification v1 already reports `opening_closing_check` FAILED / REFERENCE_MISMATCH_ONLY on all 8. So the old metadata is not a trustworthy reference: the comparator must not treat old metadata balances as truth. The capture stores row-derived opening/closing so parity can be judged against rows, and the loader warns when metadata closing != last row balance. I have not investigated whether this misleads production reconciliation (the pipeline uses `meta.closing or parse.closing`); that is a separate finding.
2. **The corpus is not clean.** The "HDFC Bank" dataset folder contains non-HDFC and scanned files (6/16 and 2/16 here). Before the full run, curate by detector agreement and report exclusions rather than counting them as old-parser failures.
3. **Correction to my earlier note:** golden snapshots do contain per-row date/amount/balance/description (post-pipeline), but only for 4 HDFC PDFs, after repair, and without raw lines, ref numbers, printed totals or metadata. Hence the dedicated capture is still needed, but goldens are a valid independent cross-check (passed).
4. Printed Dr/Cr counts and totals were None on all 8 OK files, so the old structure validator extracts no printed totals for these layouts; row-sum and chain checks must stand in for printed totals.

## 5. Caveats
- The pilot ran on my Linux VM (Python 3.10, pdfplumber 0.11.10, pdfminer 20260107). The authoritative corpus capture must run in the backend Docker image so extraction uses production library versions; the producer fingerprint changes automatically, so captures from different environments are never mixed silently.
- Only 16 of the HDFC PDFs have been captured; counts are not representative of the corpus. Layout coverage in the pilot is narrow (all `coordinate`; no `dynamic` or `text` fallback seen).
- Corpus size: 2,349 PDFs under the HDFC dataset folder tree, of which 1,423 sit in `Locked PDFs` folders (recorded as LOCKED, not captured, since no passwords are used) and about 926 are unlocked; ~3 s per PDF in the pilot, so roughly 50 minutes for the unlocked set.

## 6. Proposed next steps (not started)
1. Your decision on the pilot findings (especially #1 and the curation rule).
2. Devin runs the full capture in the backend container (chunked with `--time-budget`, resumable), then I summarize the manifest: OK/ERROR by cause, parse-method mix, chain breaks, verification states.
3. Only then design the V2 HDFC extractor boundary (RAW rows + metadata derived from rows/printed fields).

## Docker validation and full-corpus result (added after the pilot)
- The tool ran in the backend Docker image (Python 3.11.17, pdfplumber 0.11.9, pikepdf 10.5.1) over all 2,349 HDFC-folder PDFs in resumable 240 s chunks. Verified by an independent run: 2,278 unique SHA-256 results, one producer fingerprint, resume reuses everything, forced re-capture is byte-identical, no passwords or PDFs in captures, git untouched, `comparison/` ignored. Container tests: 121 passed.
- Results are classified CAPTURED / LOCKED / SCANNED_UNSUPPORTED / NON_HDFC / PARSER_ERROR. A non-HDFC file is an exclusion, not an old-parser failure. Counts and analysis: `HDFC_CORPUS_BASELINE.md` (local).
- Caveat on categories: PARSER_ERROR is an upper bound. Most of those files are not HDFC bank statements (payslips, receipts, other banks); only about 11 look like real HDFC statements the old parser missed.
- Additional capture fields since the pilot: detector bank/state/confidence, layout id, table-header fingerprint, page count, derived balances and chain breaks.
- Known legacy defect recorded, not repaired: metadata `closing_balance` (see `ISSUE_hdfc_legacy_closing_balance.md`).
