# User test guide — live rc stack (devin/final-2)

## URLs

| What | URL |
|------|-----|
| App (sign-in, upload, report) | http://localhost:3600 |
| Backend API | http://localhost:8601 (`/health`, `/docs`) |
| Keycloak admin | http://localhost:8080 (`admin` / see `KEYCLOAK_ADMIN_PASSWORD` in `.env`) |

## Sign in

The test user is `test@airco.com`. Its password is **not stored in this repo** —
set it before starting the stack:

```bash
export TEST_USER_PASSWORD='<your choice>'
# then run tools/final/wf_api.py::login or reset via Keycloak admin console:
# Users → test@airco.com → Credentials → Set password (temporary: off)
```

Second user for isolation checks: `avadmin@airco.com` (has the `admin` realm role).

## What to try

Synthetic demo PDFs live in `tools/final/demo_pdfs/` — upload via the Analyze page.

| File / action | Expected |
|---------------|----------|
| `demo_hdfc.pdf` … any `demo_<served>.pdf` | Detect → categorized → **VERIFIED** or REVIEW → Download Excel (signed `?t=` link) |
| `demo_locked_hdfc.pdf` | Prompts for password → `demo1234` → proceeds |
| `demo_scanned.pdf` | Honest `UNSUPPORTED` — no silent garbage |
| `demo_unknown.pdf` / `demo_wrongbank.pdf` | Bank not confirmed → confirmation/override prompt |
| `demo_truncated_canara.pdf` | Honest failure, no crash |
| Batch: select several PDFs | Per-file verdicts; "Download All" gives signed links |
| Rapid-fire >30 uploads in 1 min | 429 "Too many uploads" (`Retry-After` header) |
| A PDF over 500 pages | 413 `PDF_TOO_MANY_PAGES`, nothing stored |
| Open another user's job URL | 403; open without login | 401 |

## Bank serve list (20)

`hdfc sbi axis idfc paytm citibank city_union au_sfb bank_of_maharashtra
airtel_pb iob apgv south_indian pnb bob canara icici indian_bank karnataka kotak`

Banks not in the list (e.g. `bank_of_india`, `union`) process via the legacy
pipeline or fallback — never silently through V2.

## Stop / restart

```bash
cd "X:/Airco Projects/Airco Insights fintech" && set -a && source .env && set +a
export RETENTION_DRY_RUN=true DOWNLOAD_TOKEN_SECRET="<fresh 64-hex>" \
  RC_SERVE_BANKS="hdfc,sbi,axis,idfc,paytm,citibank,city_union,au_sfb,bank_of_maharashtra,airtel_pb,iob,apgv,south_indian,pnb,bob,canara,icici,indian_bank,karnataka,kotak" \
  RC_BACKEND_PORT=8601 RC_FRONTEND_PORT=3600
cd ../wt-fn
docker compose -p rc -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.rc.yml up -d
docker compose -p rc -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.rc.yml stop   # to stop
```

## Retention dry-run

`RETENTION_DRY_RUN=true` is **on** (shared remote DB is NOT being deleted).
Hourly sweep logs *would-delete* counts only. To arm real purging later:

```bash
export RETENTION_DRY_RUN=false RETENTION_ENABLED=true
# then `up -d backend` again — only after you are ready; deletes rows >7 days.
```

## Known limits

- Single in-process queue consumer: ~90 s per job; parallel bursts queue up.
- Saturation: 25 parallel uploads → ~17 answered <90 s, rest client-timeout
  but still enqueue (head-of-line; consumers are the bottleneck).
- Retention dry-run covers DB purge + temp files; S3 lifecycle JSON is
  inert on Supabase (app-side sweep is the enforcement).
- DevDependency advisories (15) are build-time only; runtime audit is clean.
