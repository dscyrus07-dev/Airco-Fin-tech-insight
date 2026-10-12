# Freeze proposal (NOT committed)

Nothing has been staged or committed. Tag proposal: `v2.0-slice-2c-stable`.

## Key finding: line-ending noise
`git status` shows 275 modified tracked files, but only 6 contain real changes. The other 269 differ only in line endings (index is LF, working tree is CRLF): ~295k inserted/deleted lines of pure noise. They must NOT be committed. To commit a CRLF working file without noise, use `git -c core.autocrlf=input add <file>` (converts to LF on add, leaves the working copy alone). `base_processor.py` is the only real-change file that is CRLF on disk.

Categories: A = Slice 2C, B = Slice 2B / Slice 1 foundation, C = earlier user work (MyPaisaa fetch pipeline + its config/ignore rules), D = generated/runtime/dataset (never commit), E = unknown (needs your decision).

## A. Slice 2C (propose commit) — 20 entries
- backend/app/api/routes/statements_analyze.py
- backend/app/main.py
- backend/app/services/analysis_service.py
- backend/app/services/retention_service.py
- backend/app/services/statement_engine/layouts.py
- backend/tests/statement_engine/test_analysis_service.py
- backend/tests/test_statements_analyze_api.py
- docs/verification/ARCHITECTURE_INVENTORY.md
- docs/verification/SLICE2C_FINAL_REPORT.md
- frontend/app/analyze/page.tsx
- frontend/app/api/statements/[analysisId]/confirm/route.ts
- frontend/app/api/statements/[analysisId]/documents/[documentId]/unlock/route.ts
- frontend/app/api/statements/[analysisId]/process/route.ts
- frontend/app/api/statements/[analysisId]/route.ts
- frontend/app/api/statements/analyze/route.ts
- frontend/app/api/statements/banks/route.ts
- frontend/app/components/analyze/AnalyzeFlow.tsx
- frontend/app/components/layout/Header.tsx
- frontend/lib/statementsApi.ts
- frontend/lib/statementsProxy.ts

## B. Slice 2B / Slice 1 foundation (propose commit) — 109 entries
- backend/app/services/banks/_shared/base_processor.py
- backend/app/services/frontend_result_builder.py
- backend/app/services/statement_engine/analyzer.py
- backend/app/services/statement_engine/banks/_masks.json
- backend/app/services/statement_engine/banks/airtel_pb.json
- backend/app/services/statement_engine/banks/au_sfb.json
- backend/app/services/statement_engine/banks/axis.json
- backend/app/services/statement_engine/banks/bandhan.json
- backend/app/services/statement_engine/banks/bank_of_baroda.json
- backend/app/services/statement_engine/banks/bank_of_india.json
- backend/app/services/statement_engine/banks/bank_of_maharashtra.json
- backend/app/services/statement_engine/banks/canara.json
- backend/app/services/statement_engine/banks/central_bank.json
- backend/app/services/statement_engine/banks/citibank.json
- backend/app/services/statement_engine/banks/csb.json
- backend/app/services/statement_engine/banks/dbs.json
- backend/app/services/statement_engine/banks/dcb.json
- backend/app/services/statement_engine/banks/deutsche.json
- backend/app/services/statement_engine/banks/equitas_sfb.json
- backend/app/services/statement_engine/banks/federal.json
- backend/app/services/statement_engine/banks/fino_pb.json
- backend/app/services/statement_engine/banks/hdfc.json
- backend/app/services/statement_engine/banks/hsbc.json
- backend/app/services/statement_engine/banks/icici.json
- backend/app/services/statement_engine/banks/idbi.json
- backend/app/services/statement_engine/banks/idfc.json
- backend/app/services/statement_engine/banks/indian_bank.json
- backend/app/services/statement_engine/banks/indusind.json
- backend/app/services/statement_engine/banks/iob.json
- backend/app/services/statement_engine/banks/ippb.json
- backend/app/services/statement_engine/banks/karnataka.json
- backend/app/services/statement_engine/banks/kotak.json
- backend/app/services/statement_engine/banks/kvb.json
- backend/app/services/statement_engine/banks/paytm.json
- backend/app/services/statement_engine/banks/pnb.json
- backend/app/services/statement_engine/banks/rbl.json
- backend/app/services/statement_engine/banks/sbi.json
- backend/app/services/statement_engine/banks/sbm.json
- backend/app/services/statement_engine/banks/south_indian.json
- backend/app/services/statement_engine/banks/standard_chartered.json
- backend/app/services/statement_engine/banks/tmb.json
- backend/app/services/statement_engine/banks/uco.json
- backend/app/services/statement_engine/banks/ujjivan_sfb.json
- backend/app/services/statement_engine/banks/union.json
- backend/app/services/statement_engine/banks/yes.json
- backend/app/services/statement_engine/capability.py
- backend/app/services/statement_engine/contracts.py
- backend/app/services/statement_engine/detector.py
- backend/app/services/statement_engine/registry.py
- backend/app/services/verification/engine.py
- backend/app/services/verification/models.py
- backend/scripts/baseline_run.py
- backend/scripts/detection_benchmark.py
- backend/scripts/e2e_smoke.py
- backend/tests/statement_engine/test_capability_and_states.py
- backend/tests/statement_engine/test_detector.py
- backend/tests/statement_engine/test_real_pdfs.py
- backend/tests/verification/test_contract.py
- backend/tests/verification/test_engine.py
- docs/verification/FINDINGS_RUN1.md
- docs/archive/HANDOFF.md
- docs/archive/RUN_SLICE1.bat
- docs/archive/RUN_SLICE1.md
- docs/slice1/RUN_TESTS_ONLY.bat
- docs/archive/baseline_branch.txt
- docs/archive/baseline_git_diff_stat.txt
- docs/archive/baseline_git_status.txt
- docs/slice1/out_run1_before_fixes/RUN_STATUS.json
- docs/slice1/out_run1_before_fixes/RUN_STATUS.txt
- docs/slice1/out_run1_before_fixes/baseline.csv
- docs/slice1/out_run1_before_fixes/baseline.jsonl
- docs/slice1/out_run1_before_fixes/baseline_summary.md
- docs/slice1/out_run1_before_fixes/e2e_01_hdfc.json
- docs/slice1/out_run1_before_fixes/e2e_02_hdfc.json
- docs/slice1/out_run1_before_fixes/e2e_03_icici.json
- docs/slice1/out_run1_before_fixes/e2e_04_icici.json
- docs/slice1/out_run1_before_fixes/e2e_05_sbi.json
- docs/slice1/out_run1_before_fixes/e2e_06_sbi.json
- docs/slice1/out_run1_before_fixes/e2e_07_axis.json
- docs/slice1/out_run1_before_fixes/e2e_08_axis.json
- docs/slice1/out_run1_before_fixes/e2e_09_kotak.json
- docs/slice1/out_run1_before_fixes/e2e_10_kotak.json
- docs/slice1/out_run2/RUN_STATUS.json
- docs/slice1/out_run2/RUN_STATUS.txt
- docs/slice1/out_run2/banks_without_processor.json
- docs/slice1/out_run2/baseline.csv
- docs/slice1/out_run2/baseline.jsonl
- docs/slice1/out_run2/baseline_summary.md
- docs/slice1/out_run2/e2e_01_hdfc.json
- docs/slice1/out_run2/e2e_02_hdfc.json
- docs/slice1/out_run2/e2e_03_icici.json
- docs/slice1/out_run2/e2e_04_icici.json
- docs/slice1/out_run2/e2e_05_sbi.json
- docs/slice1/out_run2/e2e_06_sbi.json
- docs/slice1/out_run2/e2e_07_axis.json
- docs/slice1/out_run2/e2e_08_axis.json
- docs/slice1/out_run2/e2e_09_kotak.json
- docs/slice1/out_run2/e2e_10_kotak.json
- docs/slice1/out_run2/needs_manual_review.csv
- docs/slice1/pristine/base_processor.py
- docs/slice1/pristine/frontend_result_builder.py
- docs/slice1/run_all_slice1.ps1
- docs/slice2/DETECTION_FINDINGS.md
- docs/slice2/KNOWN_FAILURES.md
- docs/slice2/RUN_SLICE2B.bat
- docs/slice2/RUN_SLICE2B_TESTS_ONLY.bat
- docs/slice2/SLICE2B_FINAL_REPORT.md
- docs/slice2/known_failures.txt
- docs/slice2/run_slice2b.ps1

## C. Pre-existing user work (commit only if you confirm) — 23 entries
- .env.example
- .gitignore
- backend/scripts/mypaisaa_fetch/README.md
- backend/scripts/mypaisaa_fetch/api_client.py
- backend/scripts/mypaisaa_fetch/bank_validator.py
- backend/scripts/mypaisaa_fetch/config.py
- backend/scripts/mypaisaa_fetch/downloader.py
- backend/scripts/mypaisaa_fetch/input_loader.py
- backend/scripts/mypaisaa_fetch/logging_utils.py
- backend/scripts/mypaisaa_fetch/lookup.py
- backend/scripts/mypaisaa_fetch/manifest.py
- backend/scripts/mypaisaa_fetch/models.py
- backend/scripts/mypaisaa_fetch/parser.py
- backend/scripts/mypaisaa_fetch/pipeline.py
- backend/scripts/mypaisaa_fetch/ratelimit.py
- backend/scripts/mypaisaa_fetch/report.py
- backend/tests/mypaisaa/conftest.py
- backend/tests/mypaisaa/test_api_client.py
- backend/tests/mypaisaa/test_downloader.py
- backend/tests/mypaisaa/test_input_loader.py
- backend/tests/mypaisaa/test_parser.py
- backend/tests/mypaisaa/test_pipeline.py
- backend/tests/mypaisaa/test_report.py

## D. Generated / runtime / dataset (EXCLUDE) — ~15,420 entries (mostly New Dataset/)
Includes: `New Dataset/` (8.1 GB, ~29.6k files of statement data), `backend/data/` (sqlite learning store, parser metrics, unsupported-format queue), `docs/slice2/out*/` run outputs and benchmark data.

## E. Unknown (needs decision) — 2 entries
- docs/CLAUDE_PROJECT_CONTEXT.md  (the Airco Insights project doc; likely yours to keep: confirm)
- docs/SYSTEM_MAP.md

## Line-ending-only files (EXCLUDE): 269