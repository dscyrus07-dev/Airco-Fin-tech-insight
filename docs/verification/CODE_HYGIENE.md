# Code hygiene report — `devin/final-rc` (report-only; no behaviour changes)

## Dead / dev-only code

| Item | Why flagged | Action |
|---|---|---|
| `backend/_probe_audit.py` | tracked scratch script; hardcodes a foreign dev path `x:\FinTech SAAS\...` | propose delete (owner decision) |
| `backend/alembic.ini` | points at `app/database/migrations` — directory does not exist; alembic cannot run from it | dead config (credential redacted this wave); propose remove or wire env.py |
| `database/seeds/setup_supabase.py` | one-shot manual seed script | keep, now env-driven |
| `backend/data/parser_metrics.json` | runtime telemetry committed to git | propose untrack + ignore `backend/data/` |
| `backend/data/unsupported_formats/queue.json` | runtime queue file committed (currently `[]`) | already ignored for new writes; tracked copy propose untrack |

## Stale skipped tests (11 + 1)

- `tests/test_pipeline_orchestrator.py` — 10 tests `@pytest.mark.skip(reason="stale: mocks target a pre-processor pipeline API absent from this tree")`. Pre-processor refactor orphans; either port to `process_statement` or drop.
- `tests/test_pipeline_orchestrator.py::...` — 1 test skipped: `_tag_as_others is not present in pipeline_orchestrator` (same class).
- Conditional skips (env-gated, not stale): `test_detector.py` (orchestrator import), `test_serve_api.py`/`test_statements_analyze_api.py` (`importorskip fastapi`), `tests/golden/test_regression.py` (`GOLDEN_SAMPLES_DIR` unset).
- Env-only failures (see `comparison/final/REPORT.md` §2.1): 4 missing-`samples/` parser tests, 3 classifier-table drift tests (also failing on `devin/wave11`), 1 Windows `get_event_loop` test.

## Duplicate bank lists / alias maps — should be single-sourced

| Location | Shape |
|---|---|
| `backend/app/services/pipeline_orchestrator.py` `_BANK_NAME_MAP` (~line 74) | display-name → key normalization |
| `backend/app/services/analysis_service.py` (~line 47) | key → display-name map |
| `backend/app/api/routes/upload.py` `key in ("hdfc","hdfcbank")…` | key → legacy parser class routing |
| `statement_engine/extractors/registry.py` + `banks/*.json` | spec keys, aliases |

The same bank vocabulary lives in ≥4 places; a new bank requires edits in
several of them. Recommend single-sourcing into the registry + one generated
alias map (proposal only — behaviour change out of scope).

## TODO/FIXME

16 hits under `backend/app` + `backend/tools`; the only live one is
`auth_middleware.py:78` (threadpool SessionLocal — scaling note, not a defect).
Rest are context comments inside larger functions; none block release.

## Dependency pins

- `backend/requirements.txt`: 26/26 deps `==`-pinned (no ranges, no `latest`).
- `frontend/package-lock.json` present; `npm ci` reproducible. Frontend uses
  caret ranges in `package.json` but the lockfile pins the tree (npm ci
  semantics) — acceptable; consider `--save-exact` policy.
- Docker base images use `python:3.11-slim`, `node:20-alpine`,
  `postgres:15`, `redis:7-alpine`, `rabbitmq:3-management-alpine`,
  `quay.io/keycloak/keycloak:latest` — **`:latest` on keycloak is an
  uncontrolled float**; propose pinning a digest.

## Small mechanical fixes applied this wave

- `backend/alembic.ini`: removed committed production credential (dead config —
  URL now env-sourced placeholder).
- `database/seeds/setup_supabase.py`: password literal → env vars.
- `docs/security_audit.md`: credential string → placeholders.
- Doc-path comments updated for the `docs/` reorg (no code behaviour).
