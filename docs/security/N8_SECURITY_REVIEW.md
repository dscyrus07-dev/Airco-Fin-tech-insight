# N8 — Security & Secrets Review (Track B, independent; defects left for Claude)

Scope: statement endpoints on `onb` (live-tested), secrets scan of tree +
full git history, history-purge rehearsal on a repo copy, dependency audit.
No secret values or statement content in this report.

## Endpoint security — measured results

| route | auth | result |
|---|---|---|
| `POST /api/upload/bank-statement-async` | optional (`get_current_user_optional` + `X-Airco-User-*` headers) | open; identity spoofable (below) |
| `GET /api/jobs/{job_id}` | optional → `_ensure_job_access` checks ownership **only when a verified user exists** | **unauthenticated 200 + full `result_data`** (measured on an authenticated user's job `9dc94cce`) |
| `GET /api/jobs/{job_id}/download` | same gap | **unauthenticated 200 + 36.9KB statement workbook** (measured) |
| `GET /download/{file_id}` | **none at all** | **unauthenticated 200 + workbook** for any file in `/app/tmp` (measured; 245 files present); filename = `Bank_account_<full_name>_<dates>_<uuid4-8hex>.xlsx` (32-bit suffix) |
| `POST /api/statements/analyze` | required (`get_current_user`) | 401 without token ✓; JWKS-verified decode, insecure fallback off ✓ |
| `GET /api/statements/{id}` | required | ownership via owner field (code-read) |
| `GET /api/jobs` list / profile | required | 401 without token ✓ |
| CORS | allowlist of known origins + credentials | `evil.example` origin not echoed ✓ |
| Path traversal `/download/..%2F` | n/a | rejected ✓ (basename check) |
| Error leakage | — | `PDF_UNLOCK_FAILED`/`NOT_A_PDF` etc. leak internal `/tmp/tmp*.pdf` paths (minor) |
| Rate limits | — | **none observed**: 25 parallel uploads all accepted server-side (client 30s timeouts; jobs still land) |
| Signed URLs | — | none in use: `excel_url` is an API route, `pdf_url` empty; no presigned URL lifetime to measure |
| Job-id entropy | uuid4 | 122-bit — unguessable in bulk; mitigation for the read-bypass, not a fix (ids leak via logs/history/referers) |

### Measured exploit chain (no PII)

1. Upload as JWT user → `job_id` (uuid4).
2. `curl /api/jobs/<id>` **with no Authorization header** → 200 + full job.
3. `curl /api/jobs/<id>/download` → 200 + statement xlsx.
4. `curl /download/<ReportName>` → 200 + statement xlsx.
5. Upload with `X-Airco-User-Id: <any string>` → record stamped with the
   attacker-chosen user id (identity spoofing on the anonymous path).

## Secrets in transport/storage (found in code, classified — not fixed)

- `pdf_password`, `api_key`, user identity and filenames travel inside the
  RabbitMQ `file_upload_queue` payload and the Redis job blob `input_data`
  (plaintext at rest in the broker/cache; 24h TTL on blob, **no expiry on
  dead_letter_queue** — 36+ messages hold these fields forever).
- Browser `localStorage["airco-form-data"]` persists `apiKey` + `userDetails`
  with no expiry (XSS-readable, survives logout).
- Logs contain `original_filename`, S3 object keys, job/user ids and per-file
  statement stats (page count, txn count, date range) at INFO.

## Secrets scan — tree + full git history (355 commits, all refs)

| scope | finding | severity |
|---|---|---|
| `tools/verify2/e2e2.py` | Keycloak client-secret literal + test-account password literal (functional — used to log in during N8) | **critical — rotate** |
| `docker-compose.*.yml`, `config.py` defaults | amqp `guest:guest`, `change-me-*`, `postgres:postgres` fallbacks | minor (dev defaults; compose-internal on onb) |
| `.env.example` | placeholders only + **leaks vendor IP whitelist** | minor info disclosure |
| history (355 commits) | **zero real secrets committed** — only the same literals/placeholders | clean |
| working tree `.env`/`frontend/.env.local` | live credentials, gitignored, never committed | expected — rotate per checklist |

Scanner: `tools/n8/secret_scan.py` (rule set: AWS/GCP/GitHub/Slack/Stripe/
SendGrid key shapes, JWTs, PEM blocks, credentialed URLs, conn strings,
password/secret assignments, env files). False-positive-prone rules were
hand-triaged; zero real values printed anywhere.

## History-purge rehearsal (on a COPY — real repo untouched)

Exact commands rehearsed in `C:\...\n8_purge\repo` (copy deleted after):

```bat
git clone --no-local "X:/Airco Projects/wt-n8" purge_copy
cd purge_copy
:: replacements file (values never committed here):
::   <secret1>==>REMOVED-KC-CLIENT-SECRET
::   <secret2>==>REMOVED-TEST-PASSWORD
::   <secret3>==>REMOVED-AMQP-CREDS
git filter-repo --replace-text ../replace.txt --force
```

Verified: **355 commits rewritten**, 42 replacement markers inserted, **0
residue** in `git log -p`, tree identical to HEAD except the touched literals.
Real-repo procedure identical but run on a fresh clone + force-push per branch —
owner decision; see `ROTATION_CHECKLIST.md` for what must rotate regardless
(purge does not un-leak).

## Dependency audit (nothing upgraded)

Backend `requirements.txt` — **106 known vulnerabilities in 5 packages**:

| package | installed | vulns | fix suggestion |
|---|---|---|---|
| `pypdf` | 5.1.0 | 85 | → ≥6.10.1 (bulk of advisories are parser DoS — relevant: untrusted PDFs hit this code) |
| `python-multipart` | 0.0.6 | 16 | → ≥0.0.27 (multipart DoS — the upload endpoint parses multipart) |
| `python-dotenv` | 1.0.0 | 2 | → ≥1.2.2 |
| `python-jose` | 3.5.0 | 1 | unmaintained — migrate to `joserfc`/`pyjwt` |
| `ecdsa` | 0.19.2 | 2 | no fix (timing side-channel, won't-fix upstream) — avoid in new code |

Frontend `package-lock.json` — **6 vulnerabilities**:

| package | severity | fix |
|---|---|---|
| `next` ^16.2.4 (resolved <16.3.8) | **critical** | upgrade to ≥16.3.8 (fix available; advisories incl. middleware/proxy bypass, cache poisoning, DoS) |
| `sharp` | high | fix available |
| `nanoid` | high | fix available |
| `postcss` | high | fix available |
| `source-map-js` | high | fix available |
| `baseline-browser-mapping` | moderate | fix available |

## Findings summary (for the DONE line)

- **CRITICAL**: unauthenticated read/download of any job + workbook by job_id
  (`_ensure_job_access` no-ops when `current_user=None`) — measured; and
  unauthenticated `/download/{file_id}` for every workbook in `/app/tmp`.
- **CRITICAL**: committed functional Keycloak client secret + test password
  (`tools/verify2/e2e2.py`) — rotate both.
- **MAJOR**: `pdf_password`/`api_key`/PII inside RabbitMQ payloads + Redis job
  blobs + never-expiring DLQ.
- **MAJOR**: audit tables (`raw_transactions` full rows, `statement_metadata`
  incl. header text, `processing_jobs`, `job_events`) have no retention —
  outlive the 7-day promise forever.
- **MAJOR**: identity spoofing via `X-Airco-User-*` headers on the optional-auth
  upload path.
- **MAJOR**: `pypdf@5.1.0` + `python-multipart@0.0.6` on the untrusted-input
  path carry ~100 published vulns; `next` carries a critical advisory.
- **MINOR**: no rate limiting on upload/analyze; no page-count cap; error
  details leak `/tmp` paths; filenames+stats in logs; browser `localStorage`
  retains apiKey/userDetails forever; `.env.example` leaks vendor IPs;
  Redis index sets never expire.
