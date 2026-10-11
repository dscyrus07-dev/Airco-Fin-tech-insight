# PII Fixture Remediation — Option A (forward anonymisation, no history rewrite)

Branch: `devin/pii-fixtures` (worktree `wt-pii`), base `880b5e2`. Design: `comparison/wave3/GOLDEN_PII_PLAN.md`.
No `filter-repo`, no rebase/amend, no branch/tag deletion, no push.

## What changed (tracked)

| scope | before | after |
|---|---|---|
| `backend/tests/golden/**` tracked files | 54 (50 JSON + 4 python helpers) | 52 (48 unique JSON renamed, helpers untouched) |
| golden JSON content | raw values | deterministically anonymised |
| `backend/data/unsupported_formats/queue.json` | 26 entries | `[]` |
| `.gitignore` | — | + `backend/data/unsupported_formats/` (runtime queue may carry source filenames) |

Every golden JSON renamed to `<bank>_<sha8-of-anonymised-payload>.json`; `sample_name` mirrors the new stem so the snapshot↔sample pairing invariant is preserved. Code references to old filenames: none existed (tests iterate directories), no code changed. Two pairs of originals (`bank_of_baroda`, `kotak`) were byte-equivalent duplicates once sensitive tokens and filename timestamps were normalised — they collapse to one fixture each (50 → 48 unique files, semantically lossless).

## Golden anonymisation method (per-file deterministic map)

- 10+ digit tokens (incl. `_`/`.`-adjacent, excluding decimal `.digit` continuations) → `9` + zero-padded index
- emails → `user<N>@example.invalid`
- `account_holder` values and their occurrences in narration strings → `CUST<N>`
- IFSC → `XXXX0XXXXXX` same-shape synthetic; PAN → `AAAAA0000A` shape
- All keys, row counts, amounts, balances, dates, decimal formatting untouched
- `account_number` was already empty in all 50 originals (extractor never persisted it)

## Pre-change audit (counts only, tracked files)

| category | repo-wide | inside golden | queue.json |
|---|---|---|---|
| 10+ digit tokens | 17,291 | 17,267 | 0 |
| emails | 39 | 11 | 0 |
| IFSC shapes | 343 | 315 | 0 |
| PAN shapes | 0 | 0 | 0 |
| Indian mobile shapes | 1,057 | 1,055 | 0 |
| filenames w/ 9+ digit runs | 44 | 44 (all golden) | — |

Per top-level folder (all categories summed): `backend` 18,711 · `scripts` 9 · `docs` 4 · `frontend` 3 · `START.bat` 1 · `auth` 1 · `database` 1.

Post-change re-scan of `backend/tests/golden/**`: **0 hits in every category.**

## Proof of test-semantic equivalence (all 50 original files checked)

- JSON key structure identical — 0 mismatches
- List/row counts identical — 0 mismatches
- Sum of all numeric fields identical (±1e-6) — 0 mismatches
- `sample_name == file stem` invariant preserved — 0 mismatches

## Tests before → after

| suite | before | after |
|---|---|---|
| `pytest tests/golden` | 6 passed, 1 skipped | 6 passed, 1 skipped |
| `tests/golden + tests/statement_engine/extraction + tests/pipeline + tests/mypaisaa` | 2 pre-existing failures | 177 passed, 2 failed, 1 skipped — same 2 |
| `pytest tests` (whole dir) | — | 376 passed, 8 failed, 1 skipped + 4 modules uncollectable |

Pre-existing/environmental only — none touch golden fixtures: `test_json_rule_engine` ×2 (HDFC classifier drift: 15 vs 11 debit categories, present at base); `tests/banks` PDF tests ×4 + finbit (sample PDFs absent — no `samples/` dir in worktree); `test_api_key_service` ×1 (asyncio event-loop policy, py3.11); collection errors on `test_pipeline_orchestrator`, `test_statements_analyze_api` (`_tag_as_others` absent at `880b5e2`), `test_analysis_service`, `test_real_pdfs` (`pikepdf` not installed). **No test passed before and failed after.**

## Report-only hits outside the fixture scope (35 files, NOT changed)

Code-level constants, test literals, config examples, and docs — listed for Claude:

- `START.bat`, `auth/auth-service/app/services/auth_service.py`, `backend/_probe_audit.py`, `backend/alembic.ini`, `backend/app/middleware/audit_context.py`, `backend/app/services/audit/audit_context.py`
- `backend/app/services/statement_engine/contracts.py`
- `backend/scripts/mypaisaa_fetch/bank_validator.py`
- `backend/tests/mypaisaa/test_parser.py`, `backend/tests/pipeline/test_lite_excel_export.py`, `backend/tests/test_async_upload.py`, `backend/tests/test_persistence_service.py`, `backend/tests/test_statements_analyze_api.py`
- `backend/tests/statement_engine/test_analysis_service.py`, `test_capability_and_states.py`, `test_detector.py`, `test_real_pdfs.py`, `extraction/test_generic_engine.py`, `extraction/test_registry_store_and_router.py`, `extractors/test_hdfc_v2_synthetic.py`
- `database/schemas/supabase_audit_schema.sql`
- `docs/BANK_INTEGRATION_GUIDE.md`, `docs/INDIAN_BANK_IMPLEMENTATION_SUMMARY.md`, `docs/SECURE_INSIGHTS_SYSTEM_OVERVIEW.md`, `docs/security_audit.md`
- `frontend/app/page.tsx`, `frontend/package-lock.json`
- `scripts/audit/_audit_verify.py`, `scripts/deploy/deploy-to-aws.ps1`, `scripts/deploy/deploy-to-ec2.sh`, `scripts/dev/test_banks.py`, `scripts/setup/setup-keycloak-realm.sh`, `scripts/setup/setup-keycloak.sh`, `scripts/setup/setup-local-keycloak.ps1`, `scripts/setup/test-login.sh`

## What stays in git history

The 50 original golden blobs and the 26-entry queue blob remain in history on every ref that ever contained them — Option A anonymises going forward only. Anyone with repo access can still read the original values via `git show`. Rotate/revoke assumption: any account data in those blobs must be treated as disclosed for its lifetime.

## Follow-up purge decision (NOT executed — user decision required)

**Plan:** `git filter-repo` (or BFG) to strip `backend/tests/golden/**` pre-anonymisation blobs + the queue.json history, then force-push every ref and rebase downstream branches.

**Refs that would need rewriting/rebasing** (all currently contain the old blobs):

- Branches: `main`, `integration/v2-waves`, `feature/statement-engine-v2-foundation`, `feature/statement-verification-v1`, `devin/wave1`, `devin/wave2`, `devin/wave3`, `devin/wave4`, `devin/wave5`, `devin/wave6`, `devin/wave8`, `devin/wave10`, `devin/pii-fixtures`
- Tags: `rollback/pre-wave5-b2bb4a4`, `v2.0-slice-2c-stable`
- Open worktrees (`wt-trackA`, `wt-trackB`, `wt-wave10`, `wt-p8b`, `wt-pii`) hold unpushed commits that would need rebase onto rewritten bases.

**Risks:** rewritten SHAs invalidate all `READY FOR DEVIN: <hash>` gates and cross-branch verification records in `docs/AGENT_STATE.md`; unpushed work on `devin/wave*`/`feature/*` branches must be rebased or is orphaned; `rollback/pre-wave5` tag loses its purpose if rewritten; any external clone retains the data (purge is only complete once all copies are refreshed and cached blobs expire — GitHub-side requires a support request to drop cached objects).

**Recommendation:** defer the rewrite until waves 6/8/10 land on `integration/v2-waves` and outstanding verification records are consolidated, then do one coordinated rewrite + force-push of a short ref list.
