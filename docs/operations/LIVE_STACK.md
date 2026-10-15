# LIVE_STACK — the N9 release-candidate stack (`rc`)

Local-only release candidate built from `devin/n9-final` (N7 tip + N9 fixes).
**Nothing is exposed to the internet.** All host listeners are on localhost /
private LAN only; Keycloak and the database are the shared dev instances, same
as `onb`.

## URLs

| surface | local | LAN (same network devices) |
|---|---|---|
| Frontend | http://localhost:3600 | http://192.168.0.105:3600 |
| Backend API | http://localhost:8601 | http://192.168.0.105:8601 |
| Health | http://localhost:8601/health -> `{"status":"ok","engine":"airco-insights","version":"2.0.0"}` | same on LAN IP |

Ports 8501/3500 requested by the brief were occupied on this machine
(Streamlit owned `127.0.0.1:8501`, another process `[::1]:3500`); the "next
free" clause was used: backend **8601**, frontend **3600**.

## Containers / images

| container | image | port | role |
|---|---|---|---|
| `rc_backend` | `rc-backend` | 8601->8000 | FastAPI + statement engine |
| `rc_frontend` | `rc-frontend` | 3600->3000 | Next.js unified entry |
| `rc_redis` | redis:7-alpine | internal | job state |
| `rc_rabbitmq` | rabbitmq:3-management-alpine | internal | job queue |

Reused read-only (unchanged): host Keycloak `localhost:8080`, auth-service
`localhost:8001`, remote Postgres (`DATABASE_URL` from `.env`), S3-compatible
storage. Keycloak client `frontend-app` gained redirect URIs and web origins
for `http://localhost:3600[/auth/callback]` and `http://127.0.0.1:3600[...]`
(admin API; nothing else changed).

## Engine configuration (exact served list)

```
STATEMENT_ENGINE_V2_MODE=serve
STATEMENT_ENGINE_UNIVERSAL_MODE=off
STATEMENT_ENGINE_MISMATCH_GUARD=1
NEXT_PUBLIC_UNIFIED_ENTRY=1
STATEMENT_ENGINE_V2_SERVE_BANKS=hdfc,sbi,axis,idfc,paytm,citibank,city_union,
  au_sfb,bank_of_maharashtra,airtel_pb,iob,apgv,south_indian,pnb,bob,canara,
  icici,indian_bank,karnataka,kotak
```

= the 14 default banks + the six N7 `GO` candidates. `bob` is the
allowlist id; the API reports it as `bank_of_baroda` (same spec, alias).

## Logging in

Browse to http://localhost:3600 -> Sign in -> Keycloak form. Use the shared
test account; credentials live in `local.env` at the repo root
(`TEST_USER_EMAIL` / `TEST_USER_PASSWORD`) — never printed here. A second
account `n9test2@airco.com` was created via the admin API for the two-user
isolation test (password documented in `tools/final/` only).

## Health checks

```bash
curl -s http://localhost:8601/health                      # {"status":"ok",...}
curl -s http://localhost:3600 -o NUL -w "%{http_code}"    # 200
docker ps --filter name=rc_ --format "{{.Names}} {{.Status}}"
bash tools/final/smoke.sh                                 # full smoke (banks + one upload each)
```

## Stop / restart

```bash
cd infra/docker
docker compose -p rc -f docker-compose.yml -f docker-compose.rc.yml \
  --env-file "<repo>/.env" stop            # stop, keep containers
docker compose -p rc -f docker-compose.yml -f docker-compose.rc.yml \
  --env-file "<repo>/.env" up -d           # start again
```

`RC_SERVE_BANKS`, `RC_BACKEND_PORT=8601`, `RC_FRONTEND_PORT=3600` must be set
in the environment (they were passed inline at launch; see report §7).

## Roll back to `onb`

`onb` is untouched and still running the shipped default 14-bank list on its
original ports (8000/3000). Rollback = stop `rc` (above); nothing else is
required — `rc` wrote no code/config into `onb`, the shipped
`bank_status.json`, or the Keycloak client beyond the added 3600
redirect/origins (harmless to onb). To remove the Keycloak additions later:
admin API -> client `frontend-app` -> delete the four `*:3600*` URIs.

## Resource use (idle, `docker stats --no-stream`)

backend ~173 MiB / ~0.2% CPU; frontend ~38 MiB; redis ~5 MiB; rabbitmq
~145 MiB. Working set stays < 2 GiB; a 67-page statement peaked ~1.6 GiB in N8
measurements on the same backend build.

## Optional: temporary protected tunnel (owner only — NOT done here)

If a short-lived remote demo is ever needed, do it only after: (1) Keycloak
auth confirmed on every route (N8 found unauthenticated job endpoints — fix
first), (2) rate limiting in front of upload/analyze, (3) retention verified
(7-day policy), (4) synthetic files only — never real customer statements.
Then a `cloudflared tunnel --no-autoupdate` or `ngrok --oauth` with an
allow-listed IdP group can terminate on `localhost:3600`. No public tunnel
was opened during N9; LAN URLs above are as far as it goes.
