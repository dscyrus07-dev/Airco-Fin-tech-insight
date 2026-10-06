# Slice 2D — Architecture Inventory (read-only)

Nothing was deleted, moved, or committed. Measured on branch `feature/statement-engine-v2-foundation` (working tree dirty; no freeze tag exists yet).

## 1. Verdict
**Cleanup is NOT safe yet.** Every extraction path still runs through the old per-bank processors (`pipeline_orchestrator._get_bank_processor` -> `banks/<bank>/processor.py` -> `BaseBankProcessor._run_pipeline`). The new Statement Engine only does detection/layout/confirmation; it has no extractor, so there is nothing yet to compare or replace the parsers with. Deletion is gated on the migration steps in section 8.

## 2. How a statement is processed today
Analyze (new) -> confirm -> `Job` -> `pipeline_orchestrator.process_statement` -> `SUPPORTED_BANK_PROCESSORS` alias map -> `_PROCESSOR_IMPORTS` (14 processors) -> `BaseBankProcessor._run_pipeline` (one shared 10-step pipeline):
1 PDF integrity -> 2 bank structure validation -> 3 parse -> 4 transaction validation -> 5 verification v1 (observe-only, runs on RAW parser rows) + balance repair/reconcile -> 6 rule classification (+ optional AI fallback) -> 7 recurring -> 8 aggregation -> 9 data-integrity guard -> 10 Excel/metrics/audit.
Callers of the orchestrator: `services/event_consumer.py`, `services/pdf_processor.py`. Other modules that import `banks.*`: `api/routes/upload.py`, `audit_service`, `claude_intelligence`, `groq_intelligence`, `metadata_extractor`, `pipeline/classification/rule_engine`, `pipeline/normalize`, `pipeline/reporting/lite_metrics`.

## 3. A universal contract already exists
`services/pipeline/models.py` defines `NormalizedTransaction` (date ISO, description, debit, credit, balance, ref_no, value_date, recurring fields, category, confidence, source, extras) and `StatementMetadata` (bank, account, holder, opening/closing, period). `pipeline/normalize.py` converts parser output to it, and `tests/golden` already snapshots results in that shape. Slice 3 should REUSE this, not invent a new StatementResult.

## 4. Per-bank inventory
14 bank packages, each with the same 11 files (parser, processor, structure_validator, transaction_validator, reconciliation, rule_engine, `<bank>_classifier`, ai_fallback, recurring_engine, aggregation_engine, rules.json). 51,055 lines in `app/`; ~27,000 are under `banks/`.

| Bank | LOC | Golden snapshots | Unit tests | In detector registry |
|---|---|---|---|---|
| hdfc | 3,470 | 5 | golden only | yes |
| icici | 2,796 | 5 | test_icici_parser | yes |
| axis | 2,483 | 5 | test_axis_parser | yes |
| sbi | 2,154 | 5 | golden only | yes |
| kotak | 2,102 | 5 | golden only | yes |
| canara | 1,862 | 5 | test_canara_parser | yes |
| bank_of_baroda | 1,776 | 2 | golden only | yes |
| idfc | 1,546 | 3 | golden only | yes |
| union | 1,395 | 5 | golden only | yes |
| paytm | 1,362 | 1 | golden only | yes |
| karnataka | 1,284 | 3 | golden only | yes |
| bank_of_india | 1,046 | 3 | none | yes |
| unknown (generic fallback) | 945 | 1 | golden only | n/a |
| indian_bank | 689 | 2 | none | yes |

Gaps: bank_of_india and indian_bank have no unit tests and thin golden coverage; paytm has 1 snapshot, bank_of_baroda/indian_bank 2.

## 5. What is duplicated vs. genuinely bank-specific
Similarity of each bank's file to HDFC's (names normalised):
- `aggregation_engine`, `recurring_engine`, `processor`: 90-100% identical for most banks (bank_of_india, indian_bank, unknown differ). Pure duplication; the shared `pipeline/aggregation` and `pipeline/recurring` engines also exist.
- `reconciliation`: ~74% identical (shared `pipeline/reconciliation` also exists).
- `rule_engine`, `*_classifier`, `ai_fallback`: 3-45%, bank-specific classification rules (partly in `rules.json`).
- `parser`, `structure_validator`, `transaction_validator`: 9-54%. This is the real bank-specific logic and the highest-risk part of any migration.
Implication: the duplicated engines can be collapsed first (lowest risk); parsers are the part that needs the old-vs-new comparator.

## 6. Hidden dependencies that must be replaced before deletion
- `SUPPORTED_BANK_PROCESSORS` alias map and `_PROCESSOR_IMPORTS` (orchestrator) and the new `PIPELINE_BANK_NAME` map in `analysis_service`: three places that know bank names.
- Parsers set attributes read by `_run_pipeline` (`_hygiene_result`, `_collected_parser_metrics`, `BANK_NAME`); a V2 extractor must provide equivalents or the pipeline must be adjusted.
- Structure validators produce opening/closing/period metadata used by verification and reconciliation.
- Transaction validators have two return shapes (tuple vs object); `_run_pipeline` special-cases both.
- Shared helpers imported from outside `banks/`: `_shared.date_normalizer`, `category_registry`, `hygiene_check`, `generic_bank`, `finbit_analytics`. These stay.
- `upload.py`, `audit_service`, `metadata_extractor`, intelligence modules reference bank packages; each must be checked individually.
- Verification v1 runs on RAW parser rows before repair; V2 output must keep that ordering.

## 7. Known baseline
11 known failing tests (axis x2, canara, finbit x2, icici, json_rule_engine x2, api_key rate limit, `_tag_as_others` collection error) plus 1 golden failure; unchanged by Slice 2C. They must be fixed or explicitly waived before they can be used as a "before" baseline.

## 8. Safe path to cleanup (gates)
0. Freeze: commit and tag the current state (needs your explicit go-ahead; the tree has ~299 uncommitted entries, so decide what goes in).
1. Old-vs-new comparator over the golden corpus (counts, per-row debit/credit/balance, opening/closing, period, verification verdict).
2. Slice 3: V2 extractor that emits `NormalizedTransaction`/`StatementMetadata`, layout families + bank config, run in shadow mode.
3. Migrate HDFC first; require comparator parity (target: 100% on balances/counts, no new verification failures) on all golden + sample PDFs.
4. Only then delete the old HDFC parser/structure/transaction validators and their routing; repeat per bank.
5. Collapse the duplicated aggregation/recurring/reconciliation copies once pipeline/* is proven equivalent (can happen independently and earlier).
6. Remove the alias map/compat layer after the last bank.

## 9. What I recommend deleting now
Nothing. Candidates for the first safe cleanup (after the freeze tag + comparator): duplicated `aggregation_engine`/`recurring_engine` copies in the 11 banks where they are byte-near-identical, and unused scratch folders in `backend/` (`temp`, `tmp`, `_probe_audit.py`, root-level `docs/slice2/out_run*`), each verified unreferenced first.
