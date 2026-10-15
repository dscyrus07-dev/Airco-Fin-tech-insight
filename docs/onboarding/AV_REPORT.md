# AV results — auth/download fix verification on `rc` (branch devin/auth-verify @597bf64)

## §1 suites
- backend `test_download_auth.py` + `test_async_upload.py` + `test_auth_integration.py`: **18/18 PASS**
- full backend suite: **858 pass / 8 fail / 18 skip** — the 8 are the same pre-existing failures as base (`56fee15`): axis ×2 + canara + finbit + icici (missing `samples/` fixtures), json_rule_engine ×2 (assertion drift 15≠11), rate-limit (order-dependent asyncio loop; passes solo). **Zero new failures.**
- frontend: tsc clean, eslint clean, vitest **59/59**, `next build` green.

## §2 attack probes on rc — 27 checks, all PASS
| probe | expected | actual |
|---|---|---|
| no-auth `GET /api/jobs/{id}` | 401 | 401 |
| no-auth `GET /api/jobs/{id}/download` | 401 | 401 |
| no-auth `GET /api/upload/download/{id}` | 401 | 401 |
| userB bearer on A's job (status) | 403 | 403 |
| userB bearer on A's job (download) | 403 | 403 |
| userB bearer on `/api/upload/download/{X}` | 403 | 403 |
| admin bearer on A's job | 200 | 200 |
| spoof `X-Airco-User-Id` on `/api/profile/history` | 401 | 401 |
| spoof header on `DELETE /api/profile/files/{id}` | 401 | 401 |
| spoof headers on upload (no bearer) | anonymous job, 200 | 200, user_id=anonymous |
| anon job read by userB | 403 | 403 |
| anon job read by userA (not owner) | 403 | 403 |
| A's job-X `?t=` token on job Y | 401 | 401 |
| tampered signature | 401 | 401 |
| tampered expiry field | 401 | 401 |
| expired token (minted ttl=-60s in-container) | 401 | 401 |
| non-admin `/download/{non-JOB file}` | 403 | 403 |
| admin `/download/{non-JOB file}` | 200 | 200 |
| path traversal (auth'd + anon) | refused | 404/404 |
| anonymous upload returns `download_token` | yes | yes |
| anon `GET /api/jobs/{id}?t=` poll | 200 | 200 |
| anon `GET /api/jobs/{id}/download?t=` | 200 | 200 |
| anon job without token | 401 | 401 |
| token(X) on `/download/JOB<other>_f.xlsx` | 401 | 401 |
| owner bearer on non-owned JOB file | 403 | 403 |
| token survives `docker restart rc_backend` | 200 (secret set) | 200 |

Extra: `GET /api/jobs/{id}` on COMPLETED jobs issues a fresh `download_token` in
`result_data` (PASS). Unset `DOWNLOAD_TOKEN_SECRET` → per-process random secret
→ tokens die on restart (documented fail-closed behaviour; not changed).

## §3 UI on rc (Playwright/Chromium)
- real Keycloak sign-in (confidential client → auth-service exchange): **PASS**
- expired session: **PASS** — honest "Invalid authentication credentials" alert, no silent data
- full upload→process→report at 1280: **PASS** (report reached)
- **report-page "Download Excel" / batch "Download All": FAIL — defect AV-1**
- Dashboard history download button: **NOT RUN** — `/api/profile/history` is empty
  for async-uploaded jobs (pre-existing gap; button's bearer-fetch transport
  verified at HTTP level: 200 + correct `content-disposition` filename)
- width 360: renders, no horizontal scroll — **PASS**; console errors: 0

## Defects
### AV-1 (MAJOR) — signed token never reaches the rendered download link
`sha: 597bf64` — `frontend/app/api/jobs/[jobId]/route.ts:31` injects `?t=` into
`excel_url` only `if (!resultData?.excel_url)`; the backend already persists
`excel_url` in `result_data`, so the branch never runs. Report-page
`<a href={excelUrl}>` and batch "Download All" links are therefore unsigned →
any browser click hits `GET /api/jobs/{id}/download` with no bearer → **401**.
Repro: `GET http://localhost:3600/api/jobs/{id}` (bearer) → `result_data.excel_url`
has no `?t=`; bare `GET :3600/api/jobs/{id}/download` → 401.
Fix direction (for owner): drop the `!excel_url` guard or have the backend sign
at issue-time. Workaround today: Dashboard history bearer-fetch download.

### AV-2 (minor) — token-authorized `/download/JOB<missing-job>_f.xlsx` → 500
`download.py` authorizes via the `JOB` prefix, then `audit_service.create_download_log`
raises `ValueError("Processing job not found")` unhandled → 500 instead of 404.
Unreachable with current filename scheme (no files carry `JOB_` prefixes) — latent.

## §4 leaks — rc backend logs + job payloads
- `download_token` values in logs: **0 — clean**
- `guest:guest`: 3 hits — `app.services.message_queue` connect log (carried N8)
- `/app/tmp` paths: 26 lines; line 298-style entries also log full S3 key
  `airco-reports/users/<email>/reports/...` — user email inside the key (minor)
- secrets / statement content: 0
- `/api/jobs` payloads still embed `excel_path` + `excel_object_key` (S3 key) — carried N8 minor

## §5 dependency inventory (scratch-bump results; NOT merged)
| package | current | advisories | min fixed | bump breaks suites? |
|---|---|---|---|---|
| pypdf | 5.1.0 | ~30 (PYSEC-2026-18xx…415x, CVE-2026-57204) | 6.19.0 | **no** — 858/8 identical |
| python-multipart | 0.0.6 | 10 (PYSEC-2024-38, 2026-1850/51/52, 3036-3040) | 0.0.31 | **no** |
| python-dotenv | 1.0.0 | PYSEC-2026-2270 | 1.2.2 | **no** |
| python-jose | 3.5.0 | CVE-2026-85394 | **none — unfixed** | n/a |
| next | 16.2.4 | ~28 incl. middleware bypass, SSRF, RCE (critical) | 16.3.8 | **no** — tsc/vitest/build green |
| sharp | 0.34.5 | libvips/libheif/librsvg CVEs | 0.35.5 | **no** |
| nanoid | 3.3.11 | GHSA-28wg/2v37/xwg4 | 3.3.18 | **no** |
| postcss | 8.4.31 (next-nested), 8.5.10 | GHSA-qx2v/6g55/fxqj/r28c | 8.5.23 | **no** |
| (transitive) ecdsa | 0.19.2 | PYSEC-2026-1325 | — | — |
| (transitive) source-map-js, baseline-browser-mapping | — | high/moderate | audit-fix | remain after bumps: 6→2 vulns |

Backend bump run (multipart 0.0.31 + dotenv 1.2.2 + pypdf 6.19.0):
**858 pass / same 8 pre-existing fails — clean.**
Frontend bump run (next 16.3.8 + nanoid 3.3.18 + postcss 8.5.23 + sharp 0.35.5):
**tsc clean, vitest 59/59, `next build` green; npm audit 6→2 vulns.**

## Env/config changes made
- `infra/docker/docker-compose.rc.yml`: +`DOWNLOAD_TOKEN_SECRET` env passthrough
  (required; value supplied at up-time, never written to disk/logs).
- Keycloak: created realm role `admin` + user `avadmin@airco.com` (synthetic
  fixture pw `AvTest!234`) for the admin→200 probes. No other realm changes.
- `frontend-app` client is **confidential** (`publicClient:false`): raw ROPC
  needs `client_secret`; browser flow unaffected (exchange via auth-service).

## NOT RUN
- Dashboard history download **button** UI leg — no history rows exist for
  async-uploaded jobs (pre-existing data-path gap); transport verified by HTTP.
- Replica test (single backend container only) — restart test stands in.
- `TRUST_FORWARDED_USER_HEADERS=true` path — spec says keep it off on rc.
