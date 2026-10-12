# Airco Insights

Bank-statement PDF → categorized transactions → Excel workbook, with an
evidence-gated statement engine (V2 layouts + T3 universal reader) that only
serves what independent checks verify.

## Layout

| Dir | What |
|---|---|
| `backend/` | FastAPI app, statement engine, legacy parsers, tools |
| `frontend/` | Next.js app (upload → analyze → confirm → process → download) |
| `auth/` | auth-service |
| `infra/docker/` | compose files |
| `database/` | seeds/migrations |
| `docs/` | see below |

## Docs (one source of truth)

- `docs/PRODUCT_STATUS.md` — per-bank serve/verdict status
- `docs/architecture/ARCHITECTURE.md` — engine map + tiers + onboarding
- `docs/operations/FEATURE_FLAGS.md` — all `STATEMENT_ENGINE_*` flags
- `docs/operations/RUNBOOK.md` — run/rollout/kill-switch/rollback
- `docs/operations/V2_ENABLEMENT.md` — serving allowlist evidence
- `docs/REPO_INVENTORY.md` — repo/worktree map
- `docs/engine/`, `docs/banks/`, `docs/verification/`, `docs/archive/` — design,
  per-bank, verification, and superseded docs
- `docs/AGENT_STATE.md` — wave ledger

## Local development

```bash
# backend (needs .env at repo root — DATABASE_URL etc.; never commit it)
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# frontend
cd frontend && npm ci && npm run dev   # :3000
```

Copy `.env.example` → `.env` and fill values. Secrets stay local; `.env*`
(except `.env.example`) is gitignored.

## Tests

```bash
cd backend && python -m pytest tests -q
cd frontend && npx vitest run && npx tsc --noEmit && npm run lint && npm run build
python backend/tools/regression_gate.py    # corpus gate (needs local corpus)
```

Some backend tests need the local `samples/` tree and a POSIX event loop —
see `comparison/final/REPORT.md` for the env-only failure list.

## Docker

```bash
cd infra/docker
docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file <env-file> up -d
# own-isolated acceptance stack (example override used by the final wave):
docker compose -p finrc -f docker-compose.yml -f docker-compose.finrc.yml --env-file <env-file> up -d --no-deps redis rabbitmq backend frontend
```

## Feature flags

All engine behaviour is env-gated, safe-off by default:
`STATEMENT_ENGINE_V2_MODE` (off), `STATEMENT_ENGINE_V2_SERVE_BANKS` (empty),
`STATEMENT_ENGINE_UNIVERSAL_MODE` (off). Full table:
`docs/operations/FEATURE_FLAGS.md`. Rollout order and kill switches:
`docs/operations/RUNBOOK.md`.
