# Slice 2C — Analyze-First Bank & Layout Detection — Final Report

Honesty note: items marked **NOT RUN** were written but not executed by the implementer (no Docker/pytest/fastapi in the implementer environment). They await Devin/Docker verification.

## 1. Summary
Users upload 1..N PDFs; the system checks capability (encrypted/corrupt/scanned), detects bank and layout with evidence, and presents results for review. Nothing is processed until the user confirms. Confirmed documents go through the EXISTING job pipeline (verification gate, categorization, Excel unchanged).

## 2. Architecture
Upload -> `POST /api/statements/analyze` -> `check_pdf` + `detect_bank` + `detect_layout` -> analysis record (Redis, TTL) + PDFs in S3 -> user review -> `POST /confirm` -> `POST /process` -> existing `Job` / `redis_job_store` / event publisher -> pipeline.

## 3. Backend endpoints (all `Depends(get_current_user)`, prefix `/api/statements`)
POST `/analyze`, GET `/banks`, GET `/{analysis_id}`, POST `/{analysis_id}/documents/{document_id}/unlock`, POST `/{analysis_id}/confirm`, POST `/{analysis_id}/process`.

## 4. States
API: DETECTED / REVIEW / UNKNOWN / UNSUPPORTED / ERROR (engine state retained as `detail_state`). Workflow: AWAITING_CONFIRMATION / CONFIRMED / PROCESSING / BLOCKED.

## 5. Layout detection
New `statement_engine/layouts.py`: 7 column-header-signature layouts; UNKNOWN when unsure; layout is independent of bank. `parser_family` = `legacy:<processor_key>`.

## 6. Evidence
Per-document evidence items (kind, label, value, weight) exposed in the API and shown under "Why we think so".

## 7. User review / override
Confirm, change bank, or select bank for UNKNOWN. bank_hint is only a hint (conflicts flagged). Overrides are stored as an auditable `USER_OVERRIDE` event (detected bank, confidence, selected bank, user, timestamp).

## 8. Locked PDFs
Password used in memory only, never logged or stored. On unlock, a decrypted copy replaces the encrypted original. A locked doc cannot be confirmed before unlock.

## 9. Failure isolation
Per-document try/except; one bad PDF yields an ERROR item and does not fail the batch.

## 10. Security / isolation
Authentication required (no anonymous fallback). Strict owner-id equality (stricter than admin-aware `check_user_ownership`); foreign ids return 404. AuthMiddleware only sets audit headers; it does not block or alter these routes. Frontend proxy forwards Authorization / `kc_token` and normalizes errors.

## 11. Retention
`retention_service.sweep_once` also purges expired unconfirmed analyses (PDFs + records).

## 12. Frontend
`/analyze` page (auth-guarded like dashboard), `AnalyzeFlow` component (multi-select, analyze, grouped-by-bank summary, status chips, evidence, per-doc confirm/override, password unlock, Confirm all detected, Process confirmed, job polling, Excel download), `lib/statementsApi.ts`, `lib/statementsProxy.ts`, six Next proxy routes, "Analyze" link in Header. `tsc --noEmit` passes (0 errors).

## 13. Tests
- `tests/statement_engine/test_analysis_service.py` (23): PASSED locally (74/74 with the rest of the local runner).
- `tests/test_statements_analyze_api.py`: **NOT RUN** (needs fastapi/Docker).
- Detector/real-PDF tests (2B): passed in Docker earlier (73 pass / 0 fail / 0 skip).
- Frontend: type-check only; `next build` and browser flow **NOT RUN**.

## 14. Docker
Not run by implementer. Pending Devin (prompt in `docs/slice2/out/s2c/DEVIN_PROMPT.md`).

## 15. Known limitations
- Unlocked PDFs are stored as decrypted copies (no password retained).
- Layout detection is header-signature only; processing still uses legacy per-bank processors.
- User bank override lives in the analysis record and job input; not in a DB table yet.
- Verification gate is the existing pipeline's.
- No OCR; scanned PDFs are reported UNSUPPORTED.

## 16. Files changed by Slice 2C
New: `backend/app/services/analysis_service.py`, `backend/app/services/statement_engine/layouts.py`, `backend/app/api/routes/statements_analyze.py`, `backend/tests/statement_engine/test_analysis_service.py`, `backend/tests/test_statements_analyze_api.py`, `frontend/app/analyze/page.tsx`, `frontend/app/components/analyze/AnalyzeFlow.tsx`, `frontend/lib/statementsApi.ts`, `frontend/lib/statementsProxy.ts`, `frontend/app/api/statements/**` (6 routes).
Modified: `backend/app/main.py`, `backend/app/services/retention_service.py`, `backend/app/services/statement_engine/__init__.py`, `frontend/app/components/layout/Header.tsx`.
Already dirty before 2C: 295 entries (`out/s2c/git_before.txt`); after: 299 entries (`git_after.txt`). Nothing committed.

## 17. Next step
Devin Docker run + review, then GO/NO-GO. No Slice 3.

## Independent verification (Devin, clean Docker rebuild)
Report: `docs/slice2/out/devin/DEVIN_2C_REPORT.md`. Result: 8/8 services healthy; 105 passed / 0 failed / 0 skipped on the new suites (9/9 API tests, encrypted-PDF test PASSED); broader suite shows only the known failures (0 new); `tsc` and `next build` pass; API-level smoke S1-S8 pass (detection, unknown not assigned, locked/wrong/correct password, scanned UNSUPPORTED, batch isolation, override audit, no job before confirm, full flow to Excel); security: 401 on all routes, cross-user 404, no passwords in logs/Redis/responses/queue, retention purge works. Browser click-through was NOT automated.

Post-verification fixes (made by implementer after Devin's report; need a re-run):
1. Wrong-password unlock now returns the "That password did not open the file" message (`analysis_service.py`; test assertion added).
2. `/api/statements/analyze` proxy returns 400 instead of 500 on a bodyless POST (`frontend/app/api/statements/analyze/route.ts`).

Product note (not a 2C defect): overriding to a bank that does not match the PDF starts the job but the existing per-bank validator then rejects it. Consider warning users in the UI.

---
SLICE 2C STATUS: IMPLEMENTED AND VERIFIED (2 minor fixes since verification)
TEST STATUS: 105/0/0 in Docker (Devin); 0 new failures; tsc + build pass; browser click-through not automated
DOCKER STATUS: clean rebuild PASS, 8/8 healthy (Devin)
BACKEND URL: http://localhost:8000 (per prior Devin run)
FRONTEND URL: http://localhost:3000 (per prior Devin run)
API STATUS: VERIFIED (Devin smoke S1-S8, security E1-E4)
NEW FAILURES: none known
KNOWN FAILURES: 11 pre-existing (unchanged as of last Docker run)
FILES CHANGED: see section 16
FINAL GO/NO-GO: GO (after a quick rebuild to pick up the 2 minor fixes, then manual browser test)
