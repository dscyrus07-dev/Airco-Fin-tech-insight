# Onboarded-bank wiring — `onb` stack

How the banks registered by the overnight onboarding (`devin/onboard-all`,
`[OB] DONE` at `e63bcdb`) are wired into backend, UI, and a dedicated Docker
stack. See `OVERNIGHT_REPORT.md` for per-bank statuses and
`docs/operations/FEATURE_FLAGS.md` for flag semantics.

## What "wired" means

Every bank registered during onboarding has a `LayoutSpec`, a banks/*.json
detector/config entry, and a `DETECTOR_TO_SPEC_BANK` mapping, so:

- `serve.spec_key_for(bank_id)` resolves for all of them.
- `GET /api/statements/banks` lists a bank **only when servable**
  (`STATEMENT_ENGINE_V2_MODE=serve` *and* its spec key is in
  `STATEMENT_ENGINE_V2_SERVE_BANKS`). Onboarded banks are `SHADOW_ONLY` or
  `REVIEW_ONLY` — none are on the shipped allowlist, so they are not listed
  and not processable under shipped config. That is deliberate.
- Analyze detects them and reports the real detected bank; confirm of a
  detected-but-not-allowlisted bank is rejected honestly; override to a
  non-servable, no-legacy bank is rejected.
- `SUPPORTED_BANK_PROCESSORS` carries display-name → spec-key aliases for the
  V2-only banks so a job created for an allowlisted spec-only bank resolves
  its spec inside the existing pipeline. No legacy parser was added and
  `process_statement` is untouched.
- `GET /api/upload/supported-banks` still lists only banks with legacy
  processors — unchanged by design.

## Serving gate (unchanged)

```
served ⇔ STATEMENT_ENGINE_V2_MODE=serve
      ∧ spec_key ∈ STATEMENT_ENGINE_V2_SERVE_BANKS
```

The overnight report classified **0 banks `READY_TO_SERVE`**, so the onb
allowlist is the demo allowlist, unchanged:

```
hdfc,sbi,axis,idfc,paytm,citibank,city_union
```

A `SHADOW_ONLY`/`REVIEW_ONLY` bank can be force-served by adding its spec key
to the allowlist, but every such bank failed at least one onboarding gate —
read its `docs/onboarding/banks/<id>.md` first. Even when served, V2 results
remain REVIEW-capped by the verdict policy where anchors are missing.

## The `onb` Docker stack

`infra/docker/docker-compose.onboard.yml` layered on `docker-compose.yml`,
compose project `onb`:

| piece | value |
|---|---|
| containers | `onb_backend`, `onb_frontend`, `onb_redis`, `onb_rabbitmq` |
| images | `onb-backend`, `onb-frontend` |
| backend host port | `${ONB_BACKEND_PORT:-8401}` → 8000 |
| frontend host port | `${ONB_FRONTEND_PORT:-3400}` → 3000 |
| Keycloak / auth service | **reused from the host** (`host.docker.internal:8080` / `:8001`) — not duplicated |
| database / storage | remote settings passed through from `local.env` |
| engine env | `V2_MODE=serve`, `SERVE_BANKS` = demo allowlist, `UNIVERSAL_MODE` off, `MISMATCH_GUARD=1` |
| frontend | built with `NEXT_PUBLIC_UNIFIED_ENTRY=1` (build-time) |

All ports and lists are overridable env vars (`ONB_BACKEND_PORT`,
`ONB_FRONTEND_PORT`, `ONB_V2_MODE`, `ONB_SERVE_BANKS`, plus the inherited
`${...:-...}` knobs).

### Start

```bash
cd infra/docker
docker compose -p onb -f docker-compose.yml -f docker-compose.onboard.yml \
  --env-file <path-to>/local.env up -d --build
```

Requires the host Keycloak (`:8080`) and auth service (`:8001`) to be running
(the `airco_*`/`keycloak*` stack provides them).

### Stop

```bash
docker compose -p onb -f docker-compose.yml -f docker-compose.onboard.yml down
```

Only `onb_*` containers are affected.

### Enable another bank on this stack

```bash
ONB_SERVE_BANKS="hdfc,sbi,axis,idfc,paytm,citibank,city_union,<spec_key>" \
docker compose -p onb -f docker-compose.yml -f docker-compose.onboard.yml \
  --env-file <path-to>/local.env up -d --no-deps backend
```

Engine env is read per container start — no rebuild needed. The bank will then
appear in `/api/statements/banks` with `v2_served: true` and become
processable. Gate: only do this for banks the evidence says are ready; today
that set is empty.

### Roll back a bank or the whole engine

- Remove the bank from `ONB_SERVE_BANKS`, recreate the backend — it falls back
  to legacy/next request.
- `ONB_V2_MODE=off` (or `shadow`) + recreate backend — V2 never serves.
- The shipped code defaults are untouched; other stacks are unaffected.

## Keycloak

The dev `frontend-app` client (realm `airco-insights`) needs redirect URIs and
web origins for the onb frontend origin (`http://localhost:3400`,
`http://127.0.0.1:3400`). They were added additively via the admin API;
existing entries were not modified or removed. If the stack moves to a
different `ONB_FRONTEND_PORT`, add the corresponding URIs the same way.

## UI behaviour for onboarded banks

- The unified flow reads `GET /api/statements/banks`, so a bank appears in the
  review dropdown / chips / "supported banks" text only when the backend
  reports it — i.e. when servable.
- `v2_served` drives the "verified engine" tag; onboarded banks show no such
  tag under shipped config.
- A document detected as a non-servable bank shows that bank as detected but
  offers no Confirm; manual override is offered only for servable banks on
  UNKNOWN/REVIEW rows, with a plain note that overriding may fail validation.
- `FALLBACK_BANK_LIST` remains legacy-only; the `BankName` type accepts the
  new ids for API-driven data.
