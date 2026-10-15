# Rotation Checklist — all credentials (owner-run, by hand)

N8 scanned the tree, history and live `onb` env. Values are never recorded
here — only where each credential lives and what rotation touches. Live secret
values currently sit in the **gitignored** `.env` files of the main worktree
(`X:\Airco Projects\Airco Insights fintech\.env`, `frontend\.env.local`) and in
container env; treat them as the source of truth until rotated.

| # | Credential | Where used | How to rotate | What breaks if forgotten |
|---|---|---|---|---|
| 1 | **Supabase Postgres `DATABASE_URL`** | backend SQLAlchemy, audit tables, file records | Supabase dashboard → reset DB password → update `DATABASE_URL` in every `.env`/deploy env → recreate backend | backend boot fails (`RuntimeError DATABASE_URL not set` / auth errors); all job history unreadable |
| 2 | **Supabase S3 `S3_ACCESS_KEY` + `S3_SECRET_KEY`** | `file_handler` boto3 client — source PDFs + workbooks in `airco-files`/`airco-reports` | Supabase → Storage → S3 keys → revoke + reissue → update env → recreate backend | uploads return `STORAGE_UPLOAD_FAILED`; downloads 404; retention sweep can't delete (objects linger — verify `sweep_once` after rotation) |
| 3 | **Keycloak client secret `frontend-app`** | frontend token exchange; e2e tools (`tools/verify2/e2e2.py` default literal `airco-frontend-secret` — **currently in the repo, treat as exposed**) | `kcadm.sh update clients/<uuid> -r airco-insights -s secret=<new>` → update `KC_SECRET`, frontend env, backend `KEYCLOAK_CLIENT_SECRET` if set → recreate | browser login loops (401 on token exchange); e2e login fails. Backend JWT verify unaffected (JWKS public keys) |
| 4 | **Keycloak admin credentials** | realm ops (client updates, user mgmt) | Admin console → master realm → admin user → password, or `KC_ADMIN_*` env on the keycloak container | loss of realm admin; can still reset via bootstrap env + recreate keycloak |
| 5 | **RabbitMQ `RABBITMQ_URL`** | `event_publisher`/`message_queue` (payloads contain `pdf_password`, `api_key`, PII — see N8_RETENTION) | create new vhost user or reset `guest` → update `RABBITMQ_URL` in compose env → recreate backend + rabbitmq together (connection is at boot) | publish fails → silent local-fallback processing; DLQ grows; queue-based processing stops |
| 6 | **Redis `REDIS_URL`** | job blobs, analysis records, rate-limit counters, index sets | Redis `--requirepass` or managed-Redis credential → update `REDIS_URL` → recreate backend | job create/poll fails (jobs endpoint 5xx); analysis fails |
| 7 | **`ANTHROPIC_API_KEY` / `CLAUDE_API_KEY`** | hybrid AI fallback path (legacy parsers, `enable_ai`) | console.anthropic.com → revoke + create → update env → recreate backend | AI-assisted classification silently degrades (falls back to rules) — check logs for auth errors |
| 8 | **`GOOGLE_API_KEY`, `GROQ_API_KEY`** | optional AI providers (same fallback path) | provider console → revoke + create → update env | same as #7 |
| 9 | **Per-user API keys (`api_keys` table / `platform_api_key_id`)** | external API auth (`get_api_principal`), rate limits keyed on them | `POST /api/v1/api-keys` (rotate = create new + revoke old); update client integrations | external integrations 401; leaked key = full upload/download access as that user — rotate promptly |
| 10 | **E2E test user `test@airco.com` password** (`Test123!` literal in `e2e2.py` — **in repo**) | Keycloak realm user, e2e tooling | `kcadm.sh set-password -r airco-insights --username test@airco.com --new-password <x>` → update `E2E_USER_PW` env where needed | anyone with repo access can log in as the test user → upload/download real processed data if tenant matches |
| 11 | **Supabase service-role / `SUPABASE_JWKS_URL` keys** | backend JWT verification (JWKS fetch) | Supabase → API keys → rotate `anon`/`service_role` → update `SUPABASE_JWKS_URL` consumers | token verification fails → all authenticated endpoints 401 |
| 12 | **Docker build secrets / GPG_KEY** (image env) | python base image (GPG key is the image's own verification key — not an app secret) | not app-managed; rotate only if custom | none app-side |
| 13 | **Session/JWT signing** | Keycloak realm keys (RS256) sign all access tokens | Keycloak → realm settings → keys → rotate RSA keypair | all issued tokens invalidate — users must re-login; JWKS consumers refetch automatically (backend caches 5 min) |
| 14 | **MyPaisaa integration** | `scripts/mypaisaa_fetch` — protected by IP whitelist, no credential (per `.env.example`) | coordinate IP whitelist change with vendor | fetch pipeline rejected (403) |

## Immediate priorities (from N8 findings)

1. **Rotate `frontend-app` client secret + `test@airco.com` password** — both
   live as literals in committed `tools/verify2/e2e2.py`.
2. **Rotate anything that ever passed through RabbitMQ/Redis plaintext** —
   `pdf_password` values supplied by customers are at rest in job blobs (24h)
   and any dead-lettered payloads (forever). Customer-supplied passwords can't
   be rotated by you — flag to users on request; the fix is a product change
   (don't put secrets in queue payloads).
3. Purge `dead_letter_queue` (36+ messages with PII+secrets) after rotating:
   `rabbitmqadmin purge queue name=dead_letter_queue`.
