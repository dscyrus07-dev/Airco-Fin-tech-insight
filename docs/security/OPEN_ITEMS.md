# Security open items — HD re-scan (devin/hard-1)

Re-verified on the rc stack after the PyJWT swap, upload rate limit, PDF page cap
and retention dry-run. Counts are from `docker logs rc_backend` (3 h window) or a
working-tree grep. No statement content, credentials, or secrets are reproduced.

| # | Item | Status | Evidence | Suggested fix |
|---|------|--------|----------|---------------|
| 1 | `apiKey` persisted in `localStorage` | **open** | `Dashboard.tsx` reads/writes `airco-form-data` incl. `apiKey` (lines ~81-227) | Drop apiKey from persisted form state, or use sessionStorage + clear-on-submit |
| 2 | S3 keys embedding user emails | **open** | 70 `users/<email>/…` key strings in backend logs | Pseudonymize key prefix (user UUID); stop logging full keys |
| 3 | Temp paths in payloads/errors | **open** | 137 `/app/tmp|tmp…` strings in logs | Log temp basename or job id only |
| 4 | `guest:guest` in log lines | **open** | 1 hit in 3 h (RabbitMQ default creds in URI) | Non-default RMQ credentials; scrub URI userinfo in logs |
| 5 | Filenames in INFO logs | **open** | 190 `*.pdf` strings in INFO logs | Demote to DEBUG or log sha8/job id |
| 6 | `pdf_password` in logs | **closed** | key name only in consumed-message dumps (`pdf_password",` — no value); value no longer persisted to job blob | — |
| 7 | `download_token` in logs | **closed** | 0 hits | — |
| 8 | JWT bearer tokens in logs | **closed** | 0 `eyJ…`-pattern hits | — |
| 9 | python-jose (CVE-2026-85394) | **closed** | verifier + auth-service on PyJWT; jose gone from requirements | — |
| 10 | PyJWT pin | **new item** | `pyjwt==2.10.1` has open advisories; fixes land at ≥2.12.1 / 2.15.0 | Bump pin to latest PyJWT and re-run `test_jwt_verifier.py` |
| 11 | Upload rate limiting | **closed** | 429 + `Retry-After` under concurrent burst; per-user isolation verified | — |
| 12 | PDF page cap | **closed** | 413 `PDF_TOO_MANY_PAGES` before S3 write; locked PDFs capped too | Corpus p99=139, max=398 — set `MAX_PDF_PAGES` ≥400 if real corpus must pass |
| 13 | Head-of-line blocking under saturation | **open (carried N8)** | 25 parallel uploads: 15-18 accepted, rest client-timeout at ~90 s; single worker drains ~1 job/3 min; 230+ pending queued | Worker scaling / async intake (report-only; do not fix here) |
| 14 | Frontend audit | **partial** | `npm audit --omit=dev` = 0; 15 dev-transitive advisories (vitest, braces, esbuild, tailwind chains) | Periodic `npm audit` in CI; dev-deps accepted risk |
| 15 | Backend audit | **open** | `pip-audit` = 21 advisory rows, all `pyjwt==2.10.1` (item 10) | See item 10 |

## Verified this pass

- Real Keycloak RS256 tokens verified by PyJWT on every request; admin role →
  200 on `/api/jobs/admin/all`, plain user → 403, expired/absent token → 401.
- Rate limit: 429 JSON body carries `detail.error` (user-facing message) and
  `Retry-After` header (raw capture `retry-after: 39`); other users unaffected.
- Page cap: over-cap plain AND locked PDFs → 413, zero S3 objects written, temp
  file removed; 100-page corpus file (sha8 `502e1f92`) accepted at default cap.
- Unified upload → process → signed download still works post-sweep;
  `tools/av/probes.py` 25/25.
