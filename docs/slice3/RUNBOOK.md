# Runbook — Wave 11 demo stack

Scope: the running demo stack in `..\wt-demo` (compose project `docker`).
Never run `docker compose down`, `prune`, or delete its volumes — the user
presents from it.

## Recommended engine flags (edit `..\wt-demo\local.env`)

```
STATEMENT_ENGINE_V2_MODE=serve
STATEMENT_ENGINE_V2_SERVE_BANKS=hdfc,sbi,axis,idfc,paytm,citibank,city_union
STATEMENT_ENGINE_V2_SERVE_TIMEOUT_S=30
```

**Do not add `indusind`** — it failed the live mutation gate
(`V2_ENABLEMENT.md`). Empty `SERVE_BANKS` disables v2 serving entirely even in
serve mode; `MODE=off` makes every bank byte-identical to the `880b5e2` legacy
baseline.

Apply without rebuilding:

```bash
cd "X:/Airco Projects/Airco Insights fintech/wt-demo"
docker compose -f infra/docker/docker-compose.yml --env-file local.env up -d --no-deps backend
```

Verify: `curl http://localhost:8000/health` → `{"status":"ok"}`.

## Service map

| service | container | port |
|---|---|---|
| frontend | docker-frontend-1 | 3000 |
| backend | docker-backend-1 | 8000 |
| auth-service | docker-auth-service-1 | 8001 |
| keycloak | keycloak | 8080 |
| keycloak db | keycloak-postgres | 5433 |
| redis | redis | 6379 |
| rabbitmq | rabbitmq | 5672 / 15672 |
| nginx | nginx | 80 |

Login: dev-realm user (credentials in `local.env`, never in docs or reports).

## Rollback — exact commands

Stable pre-Wave-11 images are tagged `demo-rc-stable`
(backend, frontend, auth-service).

```bash
cd "X:/Airco Projects/Airco Insights fintech/wt-demo"

# 1. engine-only rollback (keeps the new build, kills v2 serving)
#    local.env:  STATEMENT_ENGINE_V2_MODE=off
docker compose -f infra/docker/docker-compose.yml --env-file local.env up -d --no-deps backend

# 2. full image rollback to the tagged stable build
docker tag docker-backend:demo-rc-stable  docker-backend:latest
docker tag docker-frontend:demo-rc-stable docker-frontend:latest
docker tag docker-auth-service:demo-rc-stable docker-auth-service:latest
docker compose -f infra/docker/docker-compose.yml --env-file local.env up -d --no-deps backend frontend auth-service

# 3. verify
curl http://localhost:8000/health
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
```

## Rebuild (only after all E5 gates pass)

```bash
cd "X:/Airco Projects/Airco Insights fintech/wt-demo"
git checkout devin/wave11   # or merge the wave branch into the demo base
docker compose -f infra/docker/docker-compose.yml --env-file local.env build backend frontend
docker compose -f infra/docker/docker-compose.yml --env-file local.env up -d --no-deps backend frontend
curl http://localhost:8000/health
# smoke: one file per demo bank (see DEMO_SCRIPT.md) before handing over
```

## Troubleshooting

- **Job stuck `queued`**: `docker logs docker-backend-1 --tail 50` — check
  `RABBITMQ_URL`, `REDIS_URL`, `DATABASE_URL` are set.
- **`Invalid parameter: redirect_uri` at login**: the Keycloak client only
  allows the demo's own port; don't relocate the frontend.
- **v2 verdicts missing**: check `STATEMENT_ENGINE_V2_MODE` and that the bank
  is in `SERVE_BANKS`; REVIEW files with a working legacy parser defer to
  legacy by contract.
