# Cleanup Safety Audit — `4192b78` (`integration/v2-waves`)

Analysis only. **Nothing was deleted from this branch.** The throwaway trial
(`wt-trial`, deleted after use) is the only place removals were simulated.

- Base: `4192b78` · branch `devin/cleanup-audit` · worktree `wt-ca`
- Method: per-file evidence A–F (A static imports, B dynamic/string refs,
  C runtime coverage from tests + corpus probes, D external contracts,
  E tests/fixtures, F docs/hygiene). Missing or contradictory evidence → UNSURE.
- Full per-file detail: `docs/cleanup/VERDICTS.csv` (855 tracked files +
  untracked dirs) and `docs/cleanup/INVENTORY.csv`; endpoints: `ENDPOINTS.csv`.

## Executive summary

| verdict | files | notes |
|---|---|---|
| KEEP-CORE | 526 | product path: engine, routers, services, current UI, infra, docs |
| KEEP-FALLBACK | 227 | banks/* + services/core + pipeline/* — reached when v2 doesn't serve |
| KEEP-CONTRACT | 19 | public/API-key endpoints, migrations, keycloak client configs, backend/tools |
| KEEP-TEST | 7 | e2e scripts + synthetic fixtures |
| DELETE-AFTER-SOAK | 6 | legacy UI set (flag gate + components) — details below |
| SAFE-DELETE | 3 | `lib/api.ts`, `app/core/security.py`, `monitoring/error_logger.py` |
| UNSURE | 67 | script/tooling cohorts, `comparison/wave11`, `_probe_audit.py` (see list) |

Risk level: **low** — the only structural dead code found is 3 files and the
legacy-UI set that is already behind a working replacement. The backend has
**no** dead production modules: everything unreachable statically is pulled in
through lazy processor imports or the universal tier.

## SAFE-DELETE (evidence per item)

| path | A imports | B string refs | C runtime | D contract | E tests | F docs | note |
|---|---|---|---|---|---|---|---|
| `frontend/lib/api.ts` | 0 | 0 (Dashboard defines own `uploadStatement`) | no test hits | none | none | none | duplicate API helper |
| `backend/app/core/security.py` | 0 | 0 | 0% cov | none | none | none | JWT helpers orphaned by Keycloak auth |
| `backend/app/services/monitoring/error_logger.py` | 0 | 0 | 0% cov | none | none | none | `monitoring/__init__` only re-exports `health_monitor` |

Unused dependencies (manifest vs import graph):

- npm: `exceljs`, `file-saver` — only commented-out imports.
- pip: `xlsxwriter`, `passlib` — zero references in any source.
- (kept despite no static import: `uvicorn`, `python-multipart`,
  `psycopg2-binary`, `alembic` — entry-point/driver/CLI contracts.)

## DELETE-AFTER-SOAK — legacy UI set

Removal order (each step is one reviewable diff):

1. `frontend/app/page.tsx` dead imports (`StepForm`, `UploadStep`,
   `ModeSelection`) — page renders its own flow; imports are unused bindings.
2. `Dashboard.tsx` legacy stepper branch + `step`/`Step` state,
   `handleUserDetails`/`handleFilesChange`/`handleModeSelect`/`handleBack`/
   `handleReset`/`filesByBank`/batch plumbing, `ProcessingStep`+`ResultStep`
   imports — replace with the unified `<StatementWorkflow>` render.
3. `frontend/app/components/layout/StepForm.tsx`,
   `frontend/app/components/upload/UploadStep.tsx`,
   `frontend/app/components/upload/ModeSelection.tsx` — only consumer was the
   removed branch.
4. `frontend/app/analyze/page.tsx` + `components/analyze/AnalyzeFlow.tsx` —
   page already redirects to `/dashboard` when the flag is on.
5. `lib/flags.ts` + `unifiedEntry()` gates in `Dashboard.tsx`/`Header.tsx`
   (Analyze link gone permanently).
6. Tests: `layout/__tests__/StepForm.test.tsx`,
   `workflow/__tests__/flagOffEquivalence.test.tsx` (guards the removed path).

Proposed measurable exit criteria for "soak done" (recommendation — owner
decides): unified flow serves ≥2 consecutive releases OR ≥2 weeks with
`NEXT_PUBLIC_UNIFIED_ENTRY=1`, zero rollback, zero workflow-blocking bug
reports, and the E2E suite re-run green on the merged build.

Rollback notes: removal is frontend-only; rollback = revert the cleanup
commit. No schema/config/data migration involved. Legacy UI can also be kept
rehydratable for one release by keeping step-5 `ResultStep`/`ProcessingStep`
shared components (they are reused by the unified flow).

## KEEP lists

- KEEP-CORE: `app/main.py`, all 12 routers, `services/analysis_service`,
  `statement_engine/*` (extraction engine, registry, detector, checks,
  universal tier), `services/statements*`, `database/*`, `jobs`, `audit`,
  auth service, all `infra/docker` + compose, `database/migrations`,
  unified workflow (`components/workflow/*`, `hooks/useStatementWorkflow`,
  `lib/statementsApi`), `ProcessingStep`/`ResultStep` (shared by both flows),
  `app/page.tsx`, `Header`, contexts, build configs, all `docs/**`.
- KEEP-FALLBACK: every `app/services/banks/**` module (lazy-loaded by
  `pipeline_orchestrator` per detected bank), `services/core/*`
  (integrity guards used by every processor), `services/pipeline/**`
  (reporting/classification/aggregation/recurring pulled via
  `base_processor` lazy import), `universal/*` tier modules.
- KEEP-CONTRACT: `app/api/routes/*` (57 endpoints — `ENDPOINTS.csv`),
  `database/migrations`, `scripts/frontend-app-client.json`,
  `scripts/pkce-clear.json`, `backend/tools/*` (named in ops docs).
- KEEP-TEST: `e2e/*`, `e2e_pdfs/*` (synthetic), all `backend/tests`,
  `frontend` vitest files guarding kept code.

## Per-bank legacy parser table

| bank processor | status | retirement condition |
|---|---|---|
| hdfc, sbi, axis, idfc, paytm | v2-served (legacy = shadow/fallback) | bank stable on allowlist ≥N releases + comparator parity sign-off |
| citibank, city_union | v2-served, **no legacy processor exists** | n/a — already retired by absence |
| icici, kotak, canara, indian_bank, karnataka, union, bank_of_baroda, bank_of_india | legacy-only (layout absent or below evidence gate) | a v2 layout reaching the evidence gate + allowlist add |
| unknown | catch-all fallback for unsupported/misdetected | never — it's the safety net |
| indusind | v2 layout exists, excluded (E3 blocker) | not servable; no legacy processor |
| south_indian | no processor, no layout → `unknown` | needs processor or layout |

`process_statement` + the bank packages are the **production fallback today**:
any scanned/locked/unknown-layout/mismatch file lands there. They cannot be
removed until every bank above moves to v2-served — a per-bank migration,
not a code deletion.

## UNSURE — missing evidence named

| path/group | missing evidence |
|---|---|
| `backend/scripts/*` (23 files: baseline_run, detection_benchmark, e2e_smoke, mypaisaa_fetch/*, dev/*) | whether ops still runs them; refs only in `docs/archive/*` |
| `scripts/audit/_*.py` (10) | one-off verification scripts; may still be needed for parity checks |
| `scripts/dev/test_*.py` (10) | dev test scripts; unclear if runbook-invoked |
| `scripts/deploy/*`, `scripts/setup/*` (17+2 json) | deploy/runbook usage; referenced by ops docs → likely keep |
| `comparison/wave11/*` (6) | historical analysis artifacts — keep-vs-purge is a docs decision |
| `backend/_probe_audit.py` | named in PII_REMEDIATION/ARCH_INVENTORY/CODE_HYGIENE docs |
| `docs/archive/**` (18) | intentionally archived; purge only if history unwanted |

## Trial removal (Step 4) — throwaway `wt-trial`, then deleted

Trial A = SAFE-DELETE set removed; Trial B = A + DELETE-AFTER-SOAK set
(with the three referencing sites edited: `page.tsx` imports, `Dashboard.tsx`
legacy branch + flag gate, `Header.tsx` gate).

| check | Trial A | Trial B |
|---|---|---|
| `tsc --noEmit` | PASS (1 pre-existing error, identical on base) | PASS (same pre-existing error) |
| eslint `--max-warnings=0` | PASS | PASS |
| vitest | PASS 38/38 | PASS 34/34 (4 tests removed with the set) |
| `next build` | PASS | PASS (`/analyze` route gone) |
| backend import smoke (`app.main` + 12 routers) | PASS | PASS (unchanged) |
| `pytest tests/statement_engine` | PASS 256/256 | PASS (unchanged) |
| corpus compare ≥300 files vs base | see below | identical (engine untouched) |

Corpus compare: plain-probe on the same seeded 400-file sample
(`v2_router.route_pdf`, shadow mode) — verdict/layout/rows per sha8 compared
to the base-arm records: **400/400 matched, 0 differences** across status,
layout, fallback reason, row count and verdict.

Pre-existing environment failures (identical on untouched tree):
`tsc` reports one `TS2571` in `useStatementWorkflow.test.ts:102`; vitest shows
a benign `sessionToken` mock warning. Both exist on `4192b78` unmodified.

## Method and limits

- NOT RUN: browser E2E against the trial tree (UI-level; vitest + `next
  build` is the available evidence); full-corpus verdict diff (400-file
  seeded sample used; identical engine code means the result is
  representative); per-file coverage beyond the three sampled mode runs
  (shadow 400, serve 120, universal 80 → 264/288 measured modules executed,
  including every bank's lazy parser path actually invoked by corpus files).
- Coverage evidence: `coverage run` over pytest (298 tests) + corpus probes
  in shadow/serve/universal modes; hits recorded per module in
  `tools/cleanup_audit/cov_*.json`.
- The static import graph intentionally treats lazy imports
  (`_PROCESSOR_IMPORTS` package map, `from . import x`) as reachability —
  validated by corpus coverage hits.
- No PII anywhere: corpus files keyed by sha8 only; statement text never read
  or logged; `passwords.txt` never opened; locked files counted, not opened.
