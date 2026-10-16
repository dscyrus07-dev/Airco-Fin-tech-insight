# Runbook — statement engine operations

## Start / stop / reset

```bash
# any stack: pick compose + env file
cd infra/docker
docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file <env> up -d
docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file <env> down        # stop
docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file <env> up -d --no-deps <svc>  # restart one service
```

- Reset is env-level, not data-level: engine flags take effect on container
  recreate (`up -d --no-deps backend`) — no rebuild, no migration.
- **Demo stack warning:** the running demo (`airco_*` containers, project
  `docker`, worktree `wt-demo`) is the user's presentation stack. Never
  `down`, `prune`, or delete its volumes. Use an override file with distinct
  names/ports for your own stack (see `docker-compose.finrc.yml`).

## Rollout order (V2 + universal)

Engine flags are read per request; every step below is an env edit + backend
recreate. Defaults are all safe (`docs/operations/FEATURE_FLAGS.md`).

```
1. off                STATEMENT_ENGINE_V2_MODE=off              (baseline)
2. shadow             STATEMENT_ENGINE_V2_MODE=shadow           (observe only)
3. serve one bank     STATEMENT_ENGINE_V2_MODE=serve
                      STATEMENT_ENGINE_V2_SERVE_BANKS=hdfc
4. expand             SERVE_BANKS=hdfc,sbi,axis,idfc,paytm,citibank,city_union
5. universal shadow   STATEMENT_ENGINE_UNIVERSAL_MODE=shadow
6. universal serve    STATEMENT_ENGINE_UNIVERSAL_MODE=serve     (T3 → REVIEW only)
```

- Only banks on the evidence-backed allowlist (`V2_ENABLEMENT.md`) may be
  added at step 4. **indusind stays out** (mutation gate failure). Axis is on
  the allowlist but carries the audit `000df35f` truncation defect — see
  `docs/PRODUCT_STATUS.md` before adding it in production.
- Universal serve exposes T3 `REVIEW` rows for banks with no legacy/T2 path —
  never `VERIFIED`.

## UI entry-point flag

| Switch | Effect | Apply |
|---|---|---|
| `NEXT_PUBLIC_UNIFIED_ENTRY` unset/off | legacy `/dashboard` stepper + `/analyze` page (today's behaviour) | build-time env on the frontend image |
| `NEXT_PUBLIC_UNIFIED_ENTRY=on` | single entry: `/dashboard` renders Upload → Review → Processing → Report; `/analyze` redirects; header Analyze link hidden; Mode step skipped (free) | build-time env on the frontend image |

Rollback = unset the flag and rebuild the frontend image — both legacy pages
return unchanged (no data or backend change involved). Details:
`docs/UNIFIED_ENTRY_PLAN.md`, `docs/engine/V2_UI_NOTES.md`.

## Kill switches

| Switch | Effect | Apply |
|---|---|---|
| `STATEMENT_ENGINE_V2_MODE=off` | V2 never runs; output = legacy baseline | env + recreate backend |
| `STATEMENT_ENGINE_V2_SERVE_BANKS=` (empty) | serve mode but zero banks served | env + recreate |
| `STATEMENT_ENGINE_UNIVERSAL_MODE=off` | T3 reader never runs | env + recreate |
| remove a bank from `SERVE_BANKS` | that bank falls back to legacy next request | env + recreate |
| `STATEMENT_ENGINE_MISMATCH_GUARD=0` | disables wrong-bank guard — **do not do this in production** | env + recreate |

Verified live (final wave): flipping `V2_MODE=off` on a running stack then
re-processing the same file returned `engine: legacy, mode: off` and the
baseline workbook — no rebuild.

## Rollback

```bash
# engine-only rollback (keep image, kill serving)
STATEMENT_ENGINE_V2_MODE=off STATEMENT_ENGINE_UNIVERSAL_MODE=off \
  docker compose -f docker-compose.yml --env-file <env> up -d --no-deps backend

# image rollback to a tagged stable build
docker tag docker-backend:demo-rc-stable  docker-backend:latest
docker tag docker-frontend:demo-rc-stable docker-frontend:latest
docker compose -f docker-compose.yml --env-file <env> up -d --no-deps backend frontend
curl http://localhost:8000/health
```

Always tag a known-good image before rebuilding (`docker tag <img>:latest
<img>:stable-<date>`).

Served-list rollback (rc): to revert the 22-bank rollout-3 list to the prior
20-bank list, drop `federal,dhanlaxmi` from `RC_SERVE_BANKS` and recreate the
backend — `docker compose -p rc -f infra/docker/docker-compose.yml
-f infra/docker/docker-compose.rc.yml up -d --no-deps backend`. No rebuild
needed; `dbs` was never rolled (R3-1, see ENGINE_GAPS.md §6).

## What to watch

- `GET /health` → `{"status":"ok"}`; `docker compose ps` all `healthy`.
- `docker logs <backend>` — `v2 serve`, `universal_reader`, and
  `PipelineAbortError` lines. Honest T3 failures surface as
  `[universal_reader] ... (<CODE>)`; they are expected for unreadable layouts.
- Response `statement_engine` block — `engine`/`mode`/`verdict`/`tier` tell
  which tier served and at what trust. `needs_review` + `review_codes` are the
  operator-facing signals.
- Queue: RabbitMQ `file_upload_queue` dead-letters on handler reject —
  investigate before re-queueing.
- Retention: `DATA_RETENTION_DAYS=7` sweep removes statement artifacts;
  verify `RETENTION_ENABLED=true` in any env that touches real statements.

## Troubleshooting

- **Job stuck `queued`**: backend logs — check `RABBITMQ_URL`, `REDIS_URL`,
  `DATABASE_URL`.
- **`Invalid parameter: redirect_uri` at login**: Keycloak client allows only
  the demo's own port — don't relocate the frontend.
- **v2 verdicts missing**: check `V2_MODE` and that the bank is in
  `SERVE_BANKS`; REVIEW files with a working legacy parser defer to legacy by
  contract.
- **T3 timeouts under load**: `STATEMENT_ENGINE_UNIVERSAL_TIMEOUT` (45 s)
  counts wall-time in the isolated child; saturated hosts can trip it —
  results are honest failures, retry succeeds.

## Onboarded-bank stack (`onb`)

`docker-compose.onboard.yml` brings up an isolated stack (project `onb`,
containers `onb_*`, images `onb-*`) for testing onboarded banks. It reuses the
host Keycloak/auth service and remote DB; only redis/rabbitmq/backend/frontend
are new. Ports: backend 8401, frontend 3400 (env-overridable).

```bash
cd infra/docker
docker compose -p onb -f docker-compose.yml -f docker-compose.onboard.yml \
  --env-file <env> up -d --build    # start
docker compose -p onb -f docker-compose.yml -f docker-compose.onboard.yml \
  --env-file <env> down             # stop (onb_* only)
```

Enable another bank / roll back: set `ONB_SERVE_BANKS` (or `ONB_V2_MODE=off`)
and `up -d --no-deps backend` — no rebuild. To append promotion candidates to
the shipped allowlist instead of replacing it, set `ONB_EXTRA_SERVE_BANKS`
(e.g. `ONB_EXTRA_SERVE_BANKS=au_sfb,bank_of_maharashtra`); the compose file
joins it onto `ONB_SERVE_BANKS`'s default. Full details and the serving gate:
`docs/onboarding/WIRING.md`.

## Demo stack (wt-demo) specifics

Ports: frontend 3000, backend 8000, auth 8001, keycloak 8080, kc-db 5433,
redis 6379, rabbitmq 5672/15672, nginx 80. Flags live in
`wt-demo/local.env`. Demo allowlist:
`hdfc,sbi,axis,idfc,paytm,citibank,city_union` (see DEMO_READINESS.md,
DEMO_SCRIPT.md).

## Served list — current state (rollout `411f6ca`)

The `onb` default served list is now 14 banks (shipped in
`docker-compose.onboard.yml` as the `ONB_SERVE_BANKS` default):

`hdfc,sbi,axis,idfc,paytm,citibank,city_union,au_sfb,bank_of_maharashtra,airtel_pb,iob,apgv,south_indian,pnb`

- VERIFIED-capable (10): the original 7 + `au_sfb`, `bank_of_maharashtra`,
  `airtel_pb` (thin corpus: 3 usable files).
- Review-only (4, always "Needs review", `NO_INDEPENDENT_ANCHOR`, never
  VERIFIED): `iob`, `apgv`, `south_indian`, `pnb`.
- Axis carries the truncated-statement caveat — see `PRODUCT_STATUS.md`.

### Roll back to the old 7-bank list (one line)

```bash
ONB_SERVE_BANKS=hdfc,sbi,axis,idfc,paytm,citibank,city_union docker compose -p onb -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.onboard.yml --env-file <env> up -d --no-deps backend
```

### Add a bank

1. It must pass the evidence gate first (V3-style end-to-end proof — see
   `docs/onboarding/VERIFY3_REPORT.md`); do not add unverified banks.
2. Temporary (this boot only): `ONB_EXTRA_SERVE_BANKS=<id>` + recreate backend.
3. Permanent: edit the `ONB_SERVE_BANKS` default in
   `docker-compose.onboard.yml` and update `bank_status.json` +
   `PRODUCT_STATUS.md`.

### Served list per stack

| Stack | Served list |
|---|---|
| `onb_*` (:8401/:3400) | 14 banks above (compose default) |
| `ue_*` (:8101/:3000) | own env — 7-bank list unless `STATEMENT_ENGINE_V2_SERVE_BANKS` was overridden |
| `demo_*` / `airco_*` (wt-demo :8000/:3000) | `hdfc,sbi,axis,idfc,paytm,citibank,city_union` in `wt-demo/local.env` (DEMO_READINESS.md) |

## Reading a job's `statement_engine` block

`GET /api/jobs/{id}` → `result_data.statement_engine` (also persisted on the
`user_file_records` row). Fields:

| field | meaning |
|---|---|
| `mode` | engine mode that ran: `off` / `shadow` / `serve` |
| `engine` | who produced the workbook: `v2`, `legacy`, `universal` |
| `verdict` | independent audit verdict: `VERIFIED` (math clean), `REVIEW` (parsed but unproven), `FAILED` (refused), `null` (not run) |
| `layout_id` | which registered layout spec served, e.g. `HDFC_LAYOUT_1` |
| `detected_bank` | detector's bank id for the file |
| `anchored` | extraction bound to a printed anchor (open/close balance) |
| `needs_review` | operator flag: a human should look at this job |
| `review_codes` | plain-machine reasons — full glossary below |
| `advisory` | shadow-only comparison note (v2 vs legacy disagreement) |

## Review codes — complete glossary

Codes derive from per-check statuses only (`serve.py:review_codes`).

| code | plain meaning |
|---|---|
| `NO_INDEPENDENT_ANCHOR` | no printed opening/closing figure to verify against — the math can't be independently proven, so the file can never reach VERIFIED. Expected on summary-style exports. |
| `REFERENCE_MISMATCH` | a printed anchor exists but disagrees with the extracted math — treat output as wrong until investigated. |
| `CHAIN_BREAK` | running balances don't reconcile (balance[i] ≠ balance[i−1] ± amount) at ≥1 row — rows are missing, duplicated or mis-ordered. |
| `SIDE_MISMATCH` | an amount landed on the wrong debit/credit side somewhere. |
| `TOTALS_MISMATCH` | printed statement totals don't match the sum of extracted rows. |
| `DATE_ORDER` | transaction dates aren't monotonic where this layout promised they would be. |
| `DATE_OUTLIER` | a transaction date falls far outside the statement period or is implausible. |
| `OUTSIDE_PERIOD` | rows dated outside the declared from/to range. |
| `SCHEMA_ERRORS` | ≥1 row failed the per-row schema (missing date/amount/balance or unparseable shape). |
| `EXTRACTION_WARNINGS` | engine emitted warnings (e.g. lines after summary, skipped regions) — inspect the warnings list in the audit row. |

Other operator-visible verdict/audit signals (not `review_codes` but seen in
logs/audit): `UNSUPPORTED_BANK` (no parser and no spec), `NOT_A_PDF`,
`FILE_TOO_LARGE` (>20MB), `PDF_PASSWORD_INVALID`, `PDF_UNLOCK_FAILED`,
`SCANNED`/`MIXED` capability (image-only pages), `bank_unconfirmed` /
`foreign_bank` routing states (detector evidence insufficient/contradictory),
`ROWS_SUSPECT` (legacy integrity guard), `TIME_BUDGET` (universal reader cap).

## Finding a failed job's cause (recipe)

1. `GET /api/jobs/{id}` → `status` + `error_message`. Stage tag `[bank_routing]`
   = no bank accepted the file; `PDF_*`/`validation` = input rejected;
   `extract`/`parse` = bank matched, rows didn't.
2. `docker logs onb_backend --since <window> | grep <job_id>` — the
   `correlation_id` equals the job id. Look for the last `stage`/`verdict`
   line before failure.
3. DB audit (Postgres): `processing_jobs` row (verdict metrics,
   `validation_errors/warnings`), `job_events` rows (stage timeline, error
   strings), `statement_metadata` if present.
4. Sinks to check when a completed job lacks a workbook: report object in
   `airco-reports`, report file in `/app/tmp` (deleted by the retention sweep
   after 7 days), `excel_url` field in `result_data`.
5. Stuck `running`/`pending` after a backend restart: known gap — killed
   in-flight jobs keep `running` forever; pending jobs do resume. Resubmit the
   file (new job id). See `docs/operations/N8_ROBUSTNESS.md`.

## Rotating the Keycloak client secret (`frontend-app`)

Realm `airco-insights`, client `frontend-app` (confidential). Rotate whenever
the secret may have leaked (it currently sits as a default literal in
`tools/verify2/e2e2.py` — treat as compromised until rotated).

```bash
# 1. new secret
docker exec keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 --realm master \
  --user <admin> --password <admin_pw>
docker exec keycloak /opt/keycloak/bin/kcadm.sh \
  update clients/<frontend-app-uuid> -r airco-insights \
  -s secret=<new-secret>
```

2. Update every consumer: `KC_SECRET` for e2e tooling, `frontend`'s env
   (keycloak client config in `frontend/lib/keycloak.ts` reads env),
   any deploy scripts, and the backend's `KEYCLOAK_CLIENT_SECRET` if set.
3. Recreate the services that read it (`up -d --no-deps backend frontend`).
4. Verify: request a token
   `POST /realms/airco-insights/protocol/openid-connect/token` with the new
   secret → 200; old secret → 401.
5. What breaks if forgotten: frontend login loop (token exchange 401),
   e2e tooling login failure, backend JWKS validation unaffected (public
   keys, not the secret).

## Retention enforcement (7-day promise)

Enforced in code by `RetentionService` (hourly): S3 objects + file history (existing), and now
`retention_purge.purge_database` (hard-deletes `raw_transactions`, `job_events`, `report_generation_logs`,
`download_logs`, `statement_metadata`, `processing_jobs`, `api_request_logs`, `error_logs` older than
`DATA_RETENTION_DAYS`) and `purge_temp_dir` (files older than `TEMP_FILE_MAX_AGE_HOURS`, default 24).
Redis job index/status sets now expire after 8 days. The PDF password is no longer stored in the job blob.

Operator steps (not code):
- RabbitMQ: `docker exec <rabbitmq> sh /path/apply_retention_policy.sh` (see `infra/rabbitmq/`), adds a 7-day message TTL to both queues.
- S3: apply `infra/s3/lifecycle-7d.json` to `airco-files` and `airco-reports` if the provider supports lifecycle rules (Supabase may not; the in-app sweep covers file-history objects).
- Docker logs: set `max-size`/`max-file` on the backend logging driver.
- `audit_logs` (event names + filenames) is intentionally kept; decide separately.

Notes: `infra/s3/lifecycle-7d.json` only applies to AWS-style S3; Supabase Storage has no S3 lifecycle operations, so the in-app sweeper is the enforcement there. `RETENTION_DRY_RUN=true` also skips the temp-dir purge. Existing Redis index keys are given a TTL once at startup.
