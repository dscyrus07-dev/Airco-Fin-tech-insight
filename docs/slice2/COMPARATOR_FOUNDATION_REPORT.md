# Slice 2D — Comparator Foundation Report

Scope kept: no old parser changed or deleted, no V2 extractor built, no duplicate aggregation/recurring cleanup, nothing committed.

## 1. Files changed
New (all untracked): `backend/app/services/migration/{__init__,contract,comparator}.py`, `backend/tests/migration/{__init__,test_comparator}.py`, `docs/slice2/{ARCHITECTURE_INVENTORY,FREEZE_PROPOSAL,COMPARATOR_FOUNDATION_REPORT}.md`.
Modified existing files: none.

## 2. Tests
`tests/migration/test_comparator.py`: 20 tests on controlled fixtures (exact match, whitespace/case-insensitive descriptions, minor description change, missing/extra transaction, wrong debit/credit side, per-row balance mismatch, opening/closing mismatch, tolerance (strict default), period mismatch, bank mismatch, ordering, duplicates, printed totals, verification-verdict difference, parser failure old/new/both, non-RAW stage rejected, determinism, batch failure isolation + report, `allow_minor`). All pass in my local runner: 94/94 total (74 earlier + 20 new). NOT yet run under real pytest/Docker.

## 3. Comparator contract
Reuses `pipeline.models.NormalizedTransaction` and `StatementMetadata`; no new schema. Wrapper `ExtractionResult(engine, metadata, transactions, stage="RAW", printed_total_debit/credit, verification_status, failure, warnings)`. Protocol `StatementExtractor.extract(pdf_path, password=None) -> ExtractionResult`.
Statement level: bank, period, opening/closing balance, account number, transaction/debit/credit counts, total debits/credits, printed totals (per engine), duplicates, verification verdict.
Transaction level: exact-key match on (date, debit, credit, balance), description compare (whitespace/case-insensitive), then leftovers: same date+balance but different amount -> MAJOR; same date+amounts but different balance -> BALANCE_MISMATCH; otherwise MISSING / EXTRA; ordering.
Classes (worst first): PARSER_FAILURE, MAJOR_DIFFERENCE, MISSING_TRANSACTION, EXTRA_TRANSACTION, BALANCE_MISMATCH, MINOR_DIFFERENCE, EXACT_MATCH. A statement passes only on EXACT_MATCH (minor passes only if `allow_minor=True`). Default tolerance is zero. `run_parity(corpus, old, new)` isolates failures per file and produces counts, per-bank breakdown and a markdown report.
Verification boundary: `ExtractionResult.validate()` raises `ContractError` unless `stage == "RAW"`, so repaired output cannot be compared and hide extraction errors.

## 4. What a V2 extractor must implement
1. `name` and `extract(pdf_path, password=None) -> ExtractionResult`.
2. Return RAW rows (the same point at which verification v1 runs today: after parse/validation, before `repair_transaction_sides`, before classification).
3. Fill `StatementMetadata` (bank_key, account, period, opening/closing) and `NormalizedTransaction` (ISO date, debit/credit as Decimal or None, balance, description, ref_no, value_date).
4. Report failure through `failure` rather than raising; password stays in memory only.

## 5. Proposed HDFC V2 boundary
Input: decrypted PDF path. Output: `ExtractionResult` as above. The old HDFC side is adapted by running only steps 1-4 of `BaseBankProcessor._run_pipeline` (PDF validation, `HDFCStructureValidator`, `HDFCParser.parse`, `HDFCTransactionValidator`) and mapping through `pipeline.normalize.to_normalized`, taking opening/closing from `structure_result.metadata` as the pipeline does today. That old adapter is not built yet (it needs a small refactor-free wrapper and Docker to run); the V2 side does not exist. Downstream (classification, recurring, aggregation, Excel) keeps consuming `NormalizedTransaction` unchanged.

## 6. Risks discovered
- `to_normalized` converts dates to ISO and coerces amounts; the old side is therefore not byte-raw. Both engines must go through the same normalizer, otherwise differences will be normalizer differences, not parser differences.
- Transaction validators return two shapes (tuple vs object); the old adapter must handle both.
- Pre-existing: 11 known failing tests and 1 golden failure; golden snapshots do not store raw rows or printed totals, so they give counts/balances but not row-level truth. Row-level parity needs a fresh dump of old output per PDF.
- 269 tracked files differ only by CRLF line endings (see FREEZE_PROPOSAL.md); without a `.gitattributes` or normalization, any future commit/diff is noisy and a merge of those files would be painful.
- `New Dataset/` is 8.1 GB / ~29.6k files and not ignored except `bank_statements/` subfolders; it must stay out of commits.
- Comparator has been tested on synthetic fixtures only; it has not yet seen a real old-extractor result.
