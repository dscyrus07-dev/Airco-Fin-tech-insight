# Wave 9B — V2 Statement Engine UI Notes

Base: `89c7b21` (`integration/v2-waves` merged tip). Branch `devin/wave9` (worktree `wt-wave9b`). Local only, never pushed.

## What the UI renders (contract §3 block)

| Engine block state | Badge | Panel |
|---|---|---|
| `engine: "v2"`, `verdict: "VERIFIED"`, `anchored: true` | `Verified · independently checked` (emerald) | "How this was checked" details |
| `engine: "v2"`, `verdict: "REVIEW"` or `needs_review` | `Needs review` (amber) | Amber details panel with plain-language reasons |
| `engine: "v2"`, other verdict | `Unable to verify` (neutral) | details |
| `engine: "legacy"` + `advisory.verdict` | neutral "Checked with your bank's usual parser — …" | advisory reasons; FAILED adds "failed safely" line |
| block absent / `mode: "off"` minimal block | **nothing** | nothing |

"Nothing is shown when the block is absent" is an exact requirement and is tested.

## Review-code wording table

Single source: `REVIEW_REASON_LABELS` in `frontend/lib/statementEngine.ts`. All 11
stable codes (`NO_INDEPENDENT_ANCHOR`, `REFERENCE_MISMATCH`, `CHAIN_BREAK`,
`SIDE_MISMATCH`, `TOTALS_MISMATCH`, `DATE_ORDER`, `DATE_OUTLIER`,
`OUTSIDE_PERIOD`, `SCHEMA_ERRORS`, `EXTRACTION_WARNINGS`, `BANK_MISMATCH`) map to
plain-language sentences; unknown codes are humanized (`SOME_CODE` → "some code"),
never shown raw.

## Components

- `app/components/results/engine/VerificationBadge.tsx` — verdict badge, `role="status"` + `aria-label`.
- `app/components/results/engine/ReviewReasons.tsx` — code → wording list.
- `app/components/results/engine/EngineDetails.tsx` — native `<details>/<summary>` panel (Tab-focusable, Enter toggles; jsdom-verified). Amber when attention needed. Shows mismatch sentence, reasons, FAILED-safe note, "Statement Check" sheet note, and the internal `layout_id` (metadata only — no statement data).
- `ResultStep.tsx` — the Wave-9 inline implementation was **removed**; it now uses the shared components and `parseStatementEngine`. Batch overview line gained `N of M statement(s) need review`.

## Parser

`parseStatementEngine(raw)` in `lib/statementEngine.ts` is defensive: returns `null`
for absent/non-object blocks, coerces bad field types, drops unknown verdicts to
`null`, tolerates missing `advisory`/`detected_bank`/`review_codes`.

## Contract deltas observed (serve.py vs V2_API_CONTRACT.md)

None breaking; tolerated by the parser:

1. `detected_bank.confidence` is the detector enum name (`VERY_HIGH|HIGH|MEDIUM|LOW`), `null` for `source:"user"`.
2. v2 `FAILED` is never served as v2 data — the block arrives as `engine:"legacy"` with `advisory.verdict:"FAILED"`. UI shows "could not verify / failed safely" wording, never a Verified badge.
3. `needs_review` may be `true` together with `verdict:"REVIEW"`.
4. `review_codes` may appear both top-level and inside `advisory`; `EngineDetails` unions and dedupes them.

## Bank list

- `StepForm` (step-1 bank picker) and `AnalyzeFlow` (detection override select) both call `GET /api/statements/banks` (`listBanks()`).
- Fallbacks when the API fails or returns empty: `StepForm` → `SUPPORTED_BANK_OPTIONS` (existing bundled list); `AnalyzeFlow` → `FALLBACK_BANK_LIST` in `lib/banks.ts`, whose ids mirror `PIPELINE_BANK_NAME` in `analysis_service.py` so override decisions keep working.
- Engine names are never displayed. `AnalyzeFlow` keeps the existing `· verified engine` suffix for `v2_served` banks.
- `StepForm` casts API names to the `BankName` union; runtime values are plain strings so new backend banks work without a type update.

## Dashboard

- Per-job `VerificationBadge` next to the file/report title; renders only when `statement_engine` data is present (defensive `parseStatementEngine`).
- "Needs review" filter chip next to the Uploaded/Reports toggle; filters both the batch-grouped history view and the session lists.
- **Known gap (backend, not UI):** `/api/profile/history` items do not currently persist `statement_engine`, so badges/filter only populate for rows processed in the live session or once the backend adds the field to history payloads. The UI tolerates both.

## Accessibility / responsive

- Badge is `role="status"` with a full `aria-label`; icons are `aria-hidden`.
- Reasons panel uses native `<details>/<summary>`: Tab reaches it, Enter/Space toggles — verified in jsdom tests.
- Chips/panels use `flex-wrap`, `max-w-full`, `break-words`; no fixed widths → no horizontal scroll at 360px.

## Tests

- `npm test` (vitest + jsdom + testing-library): **27 tests, 2 files**.
  - 4 real `serve.py` block shapes mocked: v2 VERIFIED, v2 REVIEW (`NO_INDEPENDENT_ANCHOR`), v2 FAILED-as-legacy-advisory, legacy+advisory — with DOM snapshots (`__snapshots__/statementEngine.test.tsx.snap`) as render artifacts.
  - parser defensiveness, full wording-table coverage, badge visibility rules, keyboard expand, BANK_MISMATCH sentence, FAILED-never-served wording, StepForm API/fallback bank list.
- `npx tsc --noEmit`: 0 errors. `npm run build`: pass.

## Baseline notes

- `npm run lint` fails at baseline **and** after changes: `next lint` was removed in Next 16 (installed: 16.2.4) and there is no eslint config. Environment/tooling issue, not a regression — flagged for a separate fix (needs an eslint config decision).
- Backend: `serve.py` timeout default aligned 45s → 30s (+ `V2_SERVE_DESIGN.md`). FAILED-not-served, kill-switch-between-requests and off-mode byte-identical-workbook tests already existed in `tests/statement_engine/test_serve.py` / `test_shadow_wiring.py` (38 tests, all pass).

## What I could not check

- True pixel screenshots / real-browser render at 360px: no browser automation in this env; DOM snapshots + flex-wrap classes cover structure. Manual checklist `docs/MANUAL_TEST_CHECKLIST.md` §D covers the visual pass.
- Live `GET /api/statements/banks` response against a running backend (tests mock it with the documented shape).
- Dashboard badges on historical rows until the backend persists `statement_engine` in history payloads.

## Unified entry (devin/unified-entry, 2026-10-12)

`NEXT_PUBLIC_UNIFIED_ENTRY=on` merges the two front doors into one workflow on
`/dashboard`: Upload → Review → Processing → Report.

- New components (`app/components/workflow/`): `StatementWorkflow` (shell +
  stepper), `UploadDropzone`, `ReviewTable` (per-file bank override, statement
  type, inline unlock, evidence), `ProcessingList` (parallel jobs, one
  `ProcessingStep` per file), `ReportList` (the existing `ResultStep` per
  finished job, with retry for history-backed result_data).
- New hook `app/hooks/useStatementWorkflow.ts`: state machine + 2.5 s polling
  with cleanup; expired analyses (404/410) return to Upload with a message.
- Backend additive fields: `confirm` accepts per-document `account_type`;
  `process` accepts `full_name` + per-document `account_type`/`statement_label`;
  threaded into `_submit_existing_pipeline` (`user_info`, `upsert_upload`).
  Absent fields produce exactly the previous payload (asserted in tests).
- Flag off: `/dashboard` and `/analyze` are byte-identical to before
  (asserted by `flagOffEquivalence.test.tsx`).
- 360 px horizontal scroll fixed on the new screens (E2E: scrollWidth −
  clientWidth = 0 at 360/768/1280).
- E2E (Playwright, synthetic PDFs, flag on): detection, override (+ honest
  mismatch failure), inline unlock, unsupported/scanned honest messages and
  no process button, parallel processing with per-file reports, history
  refresh, `/analyze` redirect, header without Analyze link, zero console
  errors. Legacy-engine jobs show no verification badge (correct — the badge
  needs engine metadata).
