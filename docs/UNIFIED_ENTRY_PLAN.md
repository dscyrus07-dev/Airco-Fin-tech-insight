# Unified entry point: analysis and merge plan

Copied from Claude's `18_UNIFIED_ENTRY_ANALYSIS_AND_PLAN.md` (scratchpad
`p/out/`). Baseline: `integration/v2-waves` at `5744400`. Everything below
was read from the code, not assumed.

## 1. What exists today: two front doors, one back room

**Door A, `/dashboard`** (legacy, 1,387-line `Dashboard.tsx`)
Details (Full Name, bank chips, "Add Another Bank") → Upload (files grouped
under each chosen bank; a Salaried/Business type per file) → Mode (Free, or
Hybrid, which is hard-locked `hybridLocked = true`) → Processing (one file
at a time, sequential) → Report (`ResultStep`: preview, spreadsheet editor,
engine badge, downloads).

- Submits through the Next route `/api/upload` to the backend
  `POST /api/upload/bank-statement-async`.
- The bank is whatever the user typed. Nothing checks it before the job
  starts. The post-hoc mismatch guard catches some cases, and an ICICI file
  labelled as HDFC was accepted by a legacy parser earlier in this project.
- Passwords are handled with `window.prompt()` in a retry loop.
- Also owns the profile panel and file history (uploaded and report lists,
  retention labels, delete).

**Door B, `/analyze`** (new, 355-line `AnalyzeFlow.tsx`)
Pick PDFs → Analyze (bank and layout detected, evidence shown) → Confirm or
override bank per file → Process → status text and a "Download Excel" link.

- Uses `/api/statements/analyze|confirm|process`, in the backend
  `statements_analyze.py` and `analysis_service.py`.
- Handles password-protected files properly (inline Unlock). Detection
  states are honest (DETECTED, REVIEW, UNKNOWN, UNSUPPORTED, ERROR), as are
  scanned-PDF messages and `hint_conflict`.
- Dead end: after processing there is no report view. No preview, no
  editor, no verification badge, no needs-review reasons, no history
  refresh. The V2 UI work lives only in Door A.
- Drops data that Door A collects: `account_type` is hard-coded `""`,
  `mode` is `"free"`, and full name falls back to the token name.

**The back room is already shared.**
`analysis_service._submit_existing_pipeline` builds the same `Job`, calls
`file_history_service.upsert_upload`, and publishes
`publish_file_processing_request` exactly as `upload_async.py` does. Both
end in `process_statement`. So this merge is a front-door merge, not a
pipeline merge. There is no risk to the engine, the flags, or `checks.py`.

## 2. Differences that must be resolved (and the decision for each)

| Topic | Door A | Door B | Decision |
|---|---|---|---|
| Bank choice | typed first, trusted | detected first, confirmed | Detect first. Manual choice becomes a per-file override. Pre-selecting a bank becomes an optional hint (`bank_hint` already exists on `/analyze` and produces `hint_conflict`). |
| Multiple banks | bank chips, files per bank | per-file bank | Per-file bank, shown as grouped summary chips (`summary.groups` already exists). The chip UI goes away. |
| Full Name | required on step 1 | none | Optional field, prefilled from the profile. Sent with process. |
| Account type (Salaried/Business) | per file, required | none (lost) | Per file, in the review row. Default "Auto-detect" (the type already exists). Sent with confirm/process. It feeds categorization (`base_processor`) and report metadata, so it must not be lost. |
| Mode | Free or locked Hybrid | always free | Remove the step. Free is the only working mode. Keep `ModeSelection.tsx` unused behind the `hybridLocked` constant and re-add when Hybrid unlocks. |
| Processing | sequential, one job | all confirmed at once, polled | Parallel jobs, polled every 2–3 s, one status row per file. |
| Passwords | `window.prompt` retry | inline unlock | Inline unlock (Door B's). `/api/check-pdf` and `/api/unlock-pdf` stay for API users. |
| Results | `ResultStep` | download link only | Door A's `ResultStep` per file, once its job completes, including engine badge, reasons and needs-review. |
| History / profile / retention | in `Dashboard.tsx` | none | Kept, extracted so the workflow and the profile panel are separate components. Reload history after each job completes. |
| Header | "Analyze" button | n/a | Remove the Analyze link. One nav: Dashboard, API Keys, Profile. |
| Stepper | Details, Upload, Mode, Processing, Report | none | Upload, Review, Processing, Report. |

## 3. Target experience

`/dashboard` is the only entry. `/analyze` redirects there (kept as an
alias for old links and bookmarks).

- **Upload**: drop up to 20 PDFs. Optional collapsed "Details": holder
  name; "I already know the bank" hint.
- **Review**: one row per file: detected bank and confidence, layout,
  evidence on expand, state badge, bank dropdown for override or when
  UNKNOWN, statement type, inline password unlock. Buttons: Confirm all
  detected, Process confirmed. UNSUPPORTED and scanned files are shown
  with their honest message and are not processable.
- **Processing**: per-file progress, using the existing `ProcessingStep`
  look where practical.
- **Report**: per-file `ResultStep` (or a tab/accordion per file) with the
  verification badge, review reasons, and the Excel/spreadsheet tools.
  Partial failure shows per-file errors without hiding successful ones.
- Start over keeps the profile panel and history intact.

## 4. Backend alignment (small and additive)

- `POST /statements/{id}/confirm`: each decision may carry `account_type`
  (`salaried|business|auto_detect|""`).
- `POST /statements/{id}/process`: optional `full_name`, and per-document
  `account_type` / `statement_label`.
- `_submit_existing_pipeline`: use those values instead of `""`; unchanged
  when absent, so existing clients behave identically.
- Validation: account_type allow-list; `full_name` length-capped and
  stripped.
- Nothing changes in `process_statement`, the engine, the flags, or the
  legacy `/upload/*` endpoints. They stay for API clients and for rollback.
- Analysis records already expire (`expires_at`) and are purged. The UI
  must handle an expired analysis (404/410) by returning to Upload with a
  clear message.

## 5. Frontend structure

- Split `Dashboard.tsx` into a shell (`Dashboard`: header, profile panel,
  history) and a new `StatementWorkflow` that owns the four steps. Move
  the history helpers out as they are, with no behaviour change.
- New hook `useStatementWorkflow` (state machine:
  `upload → review → processing → report`, per-document status, polling
  with cleanup). Reuse `lib/statementsApi.ts`; extend `confirmDocuments`
  and `processConfirmed` with the new optional fields.
- New components: `UploadDropzone`, `ReviewTable` (extracted from
  `AnalyzeFlow`), `ProcessingList`, `ReportList` (wraps `ResultStep`). The
  V2 components (`VerificationBadge`, `ReviewReasons`, `EngineDetails`)
  are reused unchanged.
- Delete nothing in the first release. After one stable release remove
  `StepForm`, `UploadStep`, `ModeSelection` and `AnalyzeFlow`.
- Feature flag `NEXT_PUBLIC_UNIFIED_ENTRY` (default off). Off means
  today's `/dashboard` and `/analyze` behave byte-for-byte as now. The
  demo stack keeps the flag off until the user turns it on.

## 6. Risks and how the plan handles them

- **Report view regressions**: `ResultStep` expects a `ProcessingResult`
  from `job.result_data`; the same payload is available from
  `/api/jobs/{id}`. Tests with the existing engine fixtures.
- **Lost metadata**: account type and name are explicitly threaded through
  (section 4) with a test that the job's `user_info` carries them.
- **Parallel jobs vs sequential**: the worker already handles concurrent
  jobs (Door B did this). Cap at 20 files, as the backend does.
- **Wrong-bank on override**: override keeps its warning; the mismatch
  guard stays on.
- **Unsupported banks**: shown honestly; no promise of processing.
  Universal reader (T3) is a separate flag and out of scope here.
- **Auth/session**: both guards use `getValidSessionAccessToken`; unify
  into one guard.
- **Mobile**: the 360 px horizontal scroll on the analyze page is fixed as
  part of the new layout.

## 7. Phases

1. Baseline: record current test results and screenshots of both doors; no
   change.
2. Backend additive fields plus tests.
3. API client and hook, with unit tests.
4. New components.
5. Wire `/dashboard` behind the flag; `/analyze` redirect behind the same
   flag.
6. End-to-end checks with synthetic PDFs; flag-off equivalence check.
7. Docs: `PRODUCT_STATUS`, `V2_UI_NOTES`, `DEMO_SCRIPT` (flow description
   only).
8. Later, after sign-off: flip the default, then remove legacy components.

## Baseline (recorded at `5744400`, worktree `wt-ue`)

(frontend/backend results recorded below as they run)
