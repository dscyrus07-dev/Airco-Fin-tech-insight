# Airco Insights FinTech SaaS — Architecture Deep Dive

> **Version**: 2.0.0 | **Repo**: `https://github.com/dscyrus07-dev/Airco-Fin-tech-insight.git`

## 1. Executive Summary

Airco Insights is a **FinTech SaaS platform** that processes Indian bank statement PDFs, extracts transactions using bank-specific deterministic parsers, optionally enriches them with AI (Anthropic/Groq), and generates structured Excel reports.

**Tech Stack**:
- **Frontend**: Next.js 16, React 18, TailwindCSS, Lucide
- **Backend**: FastAPI, Python, Uvicorn, SQLAlchemy
- **Auth**: Keycloak 26 (OIDC/JWT) + standalone Auth Service
- **Database**: Supabase (managed PostgreSQL) — 15+ audit tables
- **Job Store**: Redis 7 Alpine — async job state, progress tracking
- **Message Queue**: RabbitMQ 3 — event-driven processing
- **Object Storage**: Supabase S3-compatible (boto3)
- **Reverse Proxy**: Nginx Alpine — SSL, routing
- **Containerization**: Docker Compose (3 profiles: base, local, EC2)

## 2. System Overview

```
                    ┌────────── NGINX (:80/:443) ──────────┐
                    │  SSL + reverse proxy + Keycloak proxy │
                    └───┬──────────┬───────────┬───────────┘
                        │          │           │
             ┌──────────▼──┐  ┌────▼─────┐  ┌──▼──────────┐
             │  FRONTEND   │  │ KEYCLOAK │  │  BACKEND    │
             │  Next.js    │  │  (OIDC)  │  │  FastAPI    │
             │  :3000      │  │  :8080   │  │  :8000      │
             └──────┬──────┘  └────┬─────┘  └──┬──────────┘
                    │   OIDC login  │           │ JWT verify
                    └───────────────┘           │
                                                │
                    ┌───────────────────────────┘
                    ▼
          ┌─────────────────┐  ┌──────────────────┐
          │  AUTH SERVICE   │  │  REDIS :6379     │
          │  :8001          │─►│  Job Store       │
          │  Keycloak bridge│  │  Progress Pub    │
          └─────────────────┘  └──────────────────┘
                    │                    │
                    ▼                    │
          ┌──────────────────┐          │ (job state R/W)
          │  RABBITMQ        │◄─────────┘
          │  file_processing │
          │  :5672/:15672    │
          └────────┬─────────┘
                   │ consumes file.uploaded
                   ▼
          ┌──────────────────┐  ┌──────────────────┐
          │  EVENT CONSUMER  │─►│  PIPELINE        │
          │  Job lifecycle   │  │  ORCHESTRATOR    │
          └──────────────────┘  │  Bank processors │
                                │  HDFC/ICICI/etc. │
                                └────────┬─────────┘
                                         │
                          ┌──────────────┼──────────────┐
                          ▼              ▼              ▼
                   ┌────────────┐ ┌────────────┐ ┌────────────┐
                   │ SUPABASE   │ │ SUPABASE   │ │ SUPABASE   │
                   │ S3 uploads │ │ S3 reports │ │ PostgreSQL │
                   │ airco-files│ │ airco-     │ │ audit+meta │
                   └────────────┘ │ reports    │ └────────────┘
                                  └────────────┘
```

| Component | Purpose | Technology |
|-----------|---------|------------|
| Frontend | UI for upload, job tracking, download | Next.js 16, React 18 |
| Backend | API, file processing, job management | FastAPI, Python |
| Auth Service | Token verification bridge to Keycloak | FastAPI microservice |
| Keycloak | Identity provider, OIDC/JWT | Keycloak 26 + PostgreSQL |
| Redis | Job state, progress tracking | Redis 7 Alpine |
| RabbitMQ | Async task queue | RabbitMQ 3 management |
| Supabase S3 | Object storage (PDFs, reports) | S3-compatible via boto3 |
| Supabase PG | Primary database | Managed PostgreSQL |
| Nginx | Reverse proxy, SSL | Nginx Alpine |

## 3. Infrastructure Layer

### 3.1 Docker Compose Profiles

**Base** (`infra/docker/docker-compose.yml`): All services with ports + health checks.

**Local** (`docker-compose.local.yml`): Lite overlay — removes microservices, uses Supabase cloud DB.
```bash
docker compose -f infra/docker/docker-compose.yml \
               -f infra/docker/docker-compose.local.yml up -d
```

**EC2** (`docker-compose.ec2.yml`): Production — no external ports, adds microservices, SSL, hardened creds.
```bash
docker compose -f infra/docker/docker-compose.yml \
               -f infra/docker/docker-compose.ec2.yml up -d
```

| Feature | Local | EC2 |
|---------|-------|-----|
| Microservices | No (monolithic backend) | Yes (file/pdf/ai/report services) |
| app-postgres | No (Supabase cloud) | Yes (local PG) |
| Ports exposed | Yes (localhost) | No (Nginx only) |
| SSL | No | Yes (Certbot + Let's Encrypt) |
| RabbitMQ creds | guest/guest | hardened |
| Keycloak hostname | localhost:8080 | https://${PUBLIC_DOMAIN} |

### 3.2 Service Startup Order

```
keycloak-postgres → keycloak → auth-service → backend → frontend → nginx
                                    ↑              ↑
                                 redis ────────────┘
                                 rabbitmq ─────────┘
```

### 3.3 Volumes

- `redis_data` — Redis persistence
- `rabbitmq_data` — Message persistence
- `keycloak_postgres_data` — Keycloak PG
- `app_postgres_data` — App PG (EC2 only)
- `backend_tmp` — Ephemeral PDF temp files

## 4. Backend Architecture

### 4.1 Structure

```
backend/app/
├── main.py                     # FastAPI app, middleware, lifespan, routes
├── core/config.py              # All settings (env-based)
├── api/routes/                 # upload, upload_async, download, jobs, sync, feedback, profile, auth, audit_admin
├── services/
│   ├── redis_job_store.py      # Redis job CRUD
│   ├── job_store.py            # In-memory fallback
│   ├── job_progress.py         # Redis progress publishing
│   ├── message_queue.py        # RabbitMQ client (pika)
│   ├── event_publisher.py      # Publishes file.uploaded events
│   ├── event_consumer.py       # Consumes events → runs pipeline
│   ├── pdf_processor.py        # Fallback processor (no MQ)
│   ├── pipeline_orchestrator.py # Bank-specific routing
│   ├── file_history_service.py  # PG file records + fallback
│   ├── retention_service.py    # Data retention sweeper
│   ├── auth_client.py          # HTTP client to Auth Service
│   ├── audit/audit_service.py  # Supabase audit logging
│   └── banks/                  # 14 bank processors + shared utils
├── middleware/                 # auth, correlation, audit_context, request_logger
├── dependencies/auth.py        # Bearer auth deps (get_current_user, roles)
├── database/                   # session.py, models.py, audit_models.py
├── models/job.py               # Job, JobStatus, JobUpdate
└── utils/                      # file_handler (S3), logging, correlation
```

### 4.2 Middleware Stack (outer → inner)

1. **RequestLoggerMiddleware** — Logs every request to `api_request_logs` table
2. **AuditContextMiddleware** — Extracts `X-Tenant-ID`, `X-User-ID`, etc. from headers
3. **AuthMiddleware** — JWT extraction → Auth Service verification → user context headers
4. **CorrelationMiddleware** — `X-Correlation-ID` propagation
5. **CORSMiddleware** — Configured origins

### 4.3 API Routes

| Route | Auth | Purpose |
|-------|------|---------|
| `POST /api/upload/bank-statement` | `require_user_role` | Sync PDF processing |
| `POST /api/upload/bank-statement-async` | optional | Async PDF → returns job_id |
| `GET /api/jobs/{job_id}` | optional | Job status + progress |
| `GET /api/jobs/{job_id}/download` | optional | Download Excel result |
| `GET /api/jobs` | `get_current_user` | List user's jobs |
| `GET /download/{file_id}` | — | Direct file download |
| `POST /api/auth/*` | — | Login, register, refresh |
| `GET /api/audit/*` | `get_admin_user` | Audit admin |

### 4.4 Bank Processors

14 banks supported via lazy import in `pipeline_orchestrator.py`:

HDFC, ICICI, Axis, Kotak, SBI, Canara, IDFC, Karnataka, Paytm, Union, Bank of Baroda, Bank of India, Indian Bank, Unknown.

Each processor: bank-specific PDF text extraction → transaction parsing → shared post-parse (classification, reconciliation, aggregation, recurring detection, Excel reporting).

### 4.5 Processing Modes

| Mode | AI | API Key | Description |
|------|----|---------|-------------|
| `free` | No | No | Deterministic rule-based |
| `hybrid` | Yes | Yes (`sk-`/`gsk_`) | AI-enhanced categorization |

## 5. Frontend Architecture

- **Framework**: Next.js 16.2.4 (App Router), React 18.3.1
- **Styling**: TailwindCSS 3.4.1, Lucide icons
- **Excel**: ExcelJS 4.4.0, FileSaver 2.0.5
- **Structure**: `app/` with `page.tsx`, `layout.tsx`, `dashboard/`, `auth/`, `api/`, `components/upload/`
- **Keycloak**: Uses `NEXT_PUBLIC_KEYCLOAK_*` env vars for OIDC
- **API**: Talks to backend via `NEXT_PUBLIC_API_URL`
- **Mode Selection**: Free/Hybrid toggle, Hybrid currently locked, requires `sk-`/`gsk_` API key
- **Build args**: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_KEYCLOAK_*`, `NEXT_PUBLIC_AIRCO_API_KEY`

## 6. Auth Service & Keycloak

### 6.1 Keycloak

- **Image**: `quay.io/keycloak/keycloak:latest` (v26+)
- **Realm**: `airco-insights`, **Client**: `frontend-app`
- **DB**: Dedicated PostgreSQL 15 (`keycloak-postgres` :5433)
- **EC2**: HTTPS, strict hostname, CORS for public domain
- **Health**: OIDC discovery endpoint probe

### 6.2 Auth Service (`auth/auth-service/` :8001)

Standalone FastAPI microservice bridging Keycloak and backend:

- `GET /auth/verify-token` — Verifies JWT via Keycloak JWKS
- `GET /auth/user-info` — User details from token
- `POST /auth/login`, `/auth/register`, `/auth/refresh` — Local auth (Phase 1)

**KeycloakTokenValidator**:
1. Fetches JWKS from Keycloak (cached 5 min)
2. Decodes JWT header → finds `kid`
3. Verifies RS256 signature
4. Validates `iss`, `exp`, `iat`, required claims (`sub`, `email`)
5. Validates client claims (`aud`/`azp` against `frontend-app`)

### 6.3 Backend Auth Flow

1. `AuthMiddleware` extracts `Bearer` token
2. Calls `AuthClient.verify_token()` → Auth Service
3. Fallback: local JWKS fetch from Keycloak directly
4. Emergency: `AUTH_ALLOW_INSECURE_FALLBACK=true` (never in prod)
5. Sets headers: `X-Tenant-ID`, `X-User-ID`, `X-User-Email`, `X-User-Name`, `X-User-Role`, `X-Session-ID`

## 7. Database Layer (Supabase / PostgreSQL)

### 7.1 Connection

```python
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
```

Schema init uses `pg_advisory_lock` for multi-worker safety.

### 7.2 Core Tables (`models.py`)

- `merchants` — Normalized merchant → category mapping
- `transactions` — Extracted transactions (debit/credit/balance/category)
- `user_file_records` — File upload/processing history with retention metadata

### 7.3 Audit Tables (`audit_models.py`)

15+ tables: `tenants`, `users`, `sessions`, `audit_logs`, `batches`, `processing_jobs`, `job_events`, `hygiene_reports`, `report_generation_logs`, `download_logs`, `parser_metrics`, `statement_metadata`, `unsupported_format_queue`, `system_health_logs`, `api_request_logs`, `error_logs`, `raw_transactions`

### 7.4 Fallback Strategy

`FileHistoryService` falls back to in-memory `_fallback_records` dict on `OperationalError`. All operations have both DB and fallback paths.

## 8. Redis — Deep Dive

### 8.1 Overview

Redis 7 Alpine is the **primary job state store** and **real-time progress tracking** system. Replaces in-memory job store with persistent, multi-worker-safe solution.

### 8.2 Connection

```python
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
```

- Docker: `redis://redis:6379` | External: `redis://localhost:6379`
- Supports `rediss://` (TLS) for managed Redis (Upstash, Redis Cloud, etc.)

### 8.3 Client Architecture

`RedisJobStore` uses `redis.asyncio` with **per-event-loop client** pattern:

```python
@property
def _redis_client(self) -> redis.Redis:
    loop = asyncio.get_running_loop()
    loop_id = id(loop)
    if loop_id not in self._loop_clients:
        self._loop_clients[loop_id] = redis.from_url(
            self.redis_url, decode_responses=True
        )
    return self._loop_clients[loop_id]
```

- Per-event-loop client prevents "Future attached to different loop" errors
- `decode_responses=True` — auto string decoding
- Lazy initialization — clients created on first use

### 8.4 Key Schema

| Key Pattern | Type | TTL | Purpose |
|-------------|------|-----|---------|
| `airco:job:{job_id}` | String (JSON) | 24h (86400s) | Full Job object |
| `airco:job:user:{user_id}` | Set | — | Job IDs for a user |
| `airco:job:status:{status}` | Set | — | Job IDs by status |

**Job JSON**: `id`, `type`, `status`, `correlation_id`, `user_id`, `input_data` (file_path, user_info, mode, api_key, bank_name, etc.), `result_data` (progress, excel_url, stats, hygiene), `error_message`, `created_at`, `started_at`, `completed_at`

### 8.5 Operations

**Create**: `SETEX` job JSON (24h TTL) + `SADD` to user + status indexes
**Get**: `GET` key → deserialize JSON → fallback to in-memory if not found
**Update**: `GET` → modify → `SETEX` (refreshed TTL) + `SREM` old status + `SADD` new status
**List**: `SMEMBERS` user/status indexes → `GET` each → merge with fallback → sort by `created_at` desc
**Delete**: Pipeline `DEL` + `SREM` from user + status indexes

### 8.6 Progress Publishing (`job_progress.py`)

**Async path**: Fetch job from `redis_job_store` → merge progress into `result_data.progress` → update job

**Sync path** (fallback for parser threads): Direct `redis.from_url()` → `GET` → merge → `SETEX`

Progress stages: `queued` → `hygiene` → `hygiene_complete` → `parsing` → `report` → `completed`

Frontend polls `GET /api/jobs/{job_id}` and reads `result_data.progress`.

### 8.7 Fallback Strategy

Every Redis operation catches `redis.RedisError` and falls back to in-memory `JobStore`:
```python
except redis.RedisError as exc:
    logger.warning("Redis error; using in-memory fallback", error=str(exc))
    return await fallback_job_store.{operation}(...)
```

`list_jobs` merges both Redis and fallback results to avoid data loss.

### 8.8 TTL & Cleanup

- Job TTL: 24 hours, refreshed on every update
- `cleanup_old_jobs()` is a no-op (TTL handles expiration)
- `RetentionService` sweeps PostgreSQL records + S3 objects (not Redis)

### 8.9 Docker Config

```yaml
redis:
  image: redis:7-alpine
  ports: ["6379:6379"]
  volumes: [redis_data:/data]
  healthcheck: ["CMD", "redis-cli", "ping"]
```

No auth, no custom config, ~40MB image, AOF persistence via volume.

### 8.10 Managed Redis for Cloud Deploy

| Provider | URL Format | Notes |
|----------|-----------|-------|
| Upstash | `rediss://default:pwd@host:port` | Serverless, TLS |
| Redis Cloud | `rediss://default:pwd@host:port` | Managed, TLS |
| Railway | `redis://default:pwd@host:port` | Built-in plugin |
| AWS ElastiCache | `rediss://host:port` | IAM/auth token |

Set `REDIS_URL` env var — code already supports `rediss://` via `redis.from_url()`.

## 9. RabbitMQ — Event-Driven Processing

### 9.1 Topology

```
Exchange: file_processing (topic, durable)
  └── Queue: file_upload_queue (durable, routing_key: "file.uploaded")
  └── Queue: dead_letter_queue (durable, for exhausted retries)
```

### 9.2 Message Flow

```
POST /api/upload/bank-statement-async
  → Save PDF to temp + upload to S3
  → Create Job in Redis (status: pending)
  → Publish to RabbitMQ (exchange: file_processing, key: file.uploaded)
  → Return job_id immediately

EventConsumer._handle_file_uploaded()
  → Mark job RUNNING in Redis
  → Run hygiene check → publish progress to Redis
  → Run bank processor (pipeline_orchestrator)
  → Upload Excel to S3 (airco-reports)
  → Mark job COMPLETED in Redis (with result_data)
  → Update audit job in PostgreSQL
```

### 9.3 Reliability

- **Heartbeat**: 300s (for long processing tasks)
- **Prefetch**: 1 (fair dispatch)
- **Durable** queues + **persistent** messages
- **Retry**: Max 3 attempts with `x-retry-count` header, then dead-letter
- **Consumer thread**: Daemon thread, auto-reconnect (5s interval)

### 9.4 Fallback (No RabbitMQ)

If RabbitMQ is down: `publish_message()` returns `False` → async upload falls back to `process_pdf_job()` in-process. Job still tracked in Redis.

### 9.5 Management UI

`http://localhost:15672` — `guest/guest` (local) or configured creds (EC2)

## 10. Object Storage (Supabase S3)

- **Buckets**: `airco-files` (uploads), `airco-reports` (Excel)
- **Object keys**: `users/{user_id}/uploads/{uuid}.pdf`, `users/{user_id}/reports/{name}.xlsx`
- **Client**: boto3 with S3v4, path-style addressing (required for Supabase)
- **Retries**: 3 attempts for transient errors
- **Note**: `SystemHealthLog` has `minio_healthy` column but MinIO is not used — Supabase S3 exclusively (`STORAGE_TYPE=supabase-s3`)

## 11. Nginx Reverse Proxy

**Local** (`nginx.local.conf`): HTTP :80, routes `/` → frontend, `/admin` `/auth` `/realms/` `.well-known` `/resources/` `/js/` → Keycloak, `/health` → backend. 25MB max body, 300s timeouts.

**EC2** (`nginx.ec2.conf.template`): HTTP :80 → HTTPS redirect + ACME challenge. HTTPS :443 with TLS 1.2/1.3, Certbot SSL certs, dynamic upstreams via Docker DNS.

## 12. End-to-End Workflow

### 12.1 Async Upload (Primary)

1. **User → Frontend**: Select bank, upload PDF, choose mode
2. **Frontend → Backend**: `POST /api/upload/bank-statement-async` with JWT
3. **Backend Auth**: AuthMiddleware verifies JWT via Auth Service → Keycloak
4. **Backend saves PDF**: To temp dir, optional pikepdf password decryption
5. **Backend → S3**: Upload PDF to `airco-files` bucket
6. **Backend → Redis**: Create job (status: pending, 24h TTL)
7. **Backend → PostgreSQL**: Upsert `user_file_records` (status: uploaded)
8. **Backend → RabbitMQ**: Publish `file.uploaded` event
9. **Backend → Frontend**: Return `{job_id}` immediately
10. **Frontend polls**: `GET /api/jobs/{job_id}` → reads Redis progress

### 12.2 Background Processing

11. **RabbitMQ → EventConsumer**: Delivers message from `file_upload_queue`
12. **EventConsumer → Redis**: Mark job RUNNING, publish `hygiene` progress
13. **Hygiene check**: Validate PDF structure, pages, transactions
14. **EventConsumer → Redis**: Publish `hygiene_complete` + `parsing` progress
15. **Pipeline Orchestrator**: Route to bank-specific processor
16. **Bank Processor**: Extract transactions, classify, aggregate, generate Excel
17. **EventConsumer → S3**: Upload Excel to `airco-reports` bucket
18. **EventConsumer → Redis**: Mark job COMPLETED with `result_data` (excel_url, stats, hygiene)
19. **EventConsumer → PostgreSQL**: Update `processing_jobs` audit + `user_file_records` (status: completed)
20. **Frontend**: Poll detects COMPLETED → shows download link

### 12.3 Download Flow

21. **User clicks download**: `GET /api/jobs/{job_id}/download`
22. **Backend**: Verifies user ownership, fetches from S3 or local temp
23. **Backend → PostgreSQL**: Log download in `download_logs`
24. **Backend → Frontend**: Stream file with correct Content-Type
25. **Frontend**: FileSaver saves Excel to user's device

### 12.4 Sync Upload (Alternative)

Same flow but steps 6-20 happen synchronously within the HTTP request. No RabbitMQ, no Redis job. Returns Excel file directly.

## 13. Deployment Strategies

### 13.1 Local Development (Docker Compose)

```bash
docker compose -f infra/docker/docker-compose.yml \
               -f infra/docker/docker-compose.local.yml up -d
```

- All services on localhost with exposed ports
- Supabase cloud for DB (`DATABASE_URL` env var)
- Keycloak on `localhost:8080`
- No SSL (Nginx HTTP only)

### 13.2 EC2 Production (Docker Compose)

```bash
docker compose -f infra/docker/docker-compose.yml \
               -f infra/docker/docker-compose.ec2.yml up -d
```

- All services internal (no exposed ports except Nginx :80/:443)
- SSL via Certbot + Let's Encrypt
- Microservices enabled (file/pdf/ai/report services)
- Hardened credentials
- Nginx with HTTPS, dynamic upstreams

### 13.3 Vercel (Frontend) + Railway (Backend) Viability

**Frontend → Vercel**:
- Next.js 16 is natively supported by Vercel
- Set env vars: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_KEYCLOAK_*`, `NEXT_PUBLIC_AIRCO_API_KEY`
- No server-side API routes needed (frontend talks directly to backend)
- `images.unoptimized: true` already set — no Vercel image optimization config needed

**Backend → Railway**:
- FastAPI deploys well on Railway
- Set env vars: `DATABASE_URL` (Supabase), `REDIS_URL` (Upstash/Railway Redis), `RABBITMQ_URL` (CloudAMQP/Railway), `S3_*` (Supabase), `KEYCLOAK_*`, `AUTH_SERVICE_URL`
- RabbitMQ consumer thread works in Railway's persistent containers
- Redis async client works with managed Redis (`rediss://`)

**Keycloak → Railway or Self-hosted**:
- Keycloak can run on Railway as a Docker service
- Or use managed Keycloak (e.g., Keycloak as a Service providers)
- Needs its own PostgreSQL (Railway PostgreSQL or Supabase separate schema)

**Required external services for Vercel+Railway**:
- Supabase (PostgreSQL + S3 storage) — already configured
- Upstash or Railway Redis — set `REDIS_URL`
- CloudAMQP or Railway RabbitMQ — set `RABBITMQ_URL`
- Keycloak instance — set `KEYCLOAK_URL`

**Limitations**:
- Vercel serverless functions have timeout limits — backend must be on Railway (not Vercel)
- RabbitMQ consumer needs persistent process — Railway works, Vercel doesn't
- File processing can take minutes — Railway container is better suited

## 14. Environment Variables Reference

### Backend

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | (required) | Supabase PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `RABBITMQ_URL` | `amqp://...@localhost:5672/` | RabbitMQ connection |
| `S3_ENDPOINT` | (required) | Supabase S3 endpoint URL |
| `S3_ACCESS_KEY` | (required) | S3 access key |
| `S3_SECRET_KEY` | (required) | S3 secret key |
| `S3_BUCKET` | `airco-files` | Upload bucket |
| `S3_BUCKET_REPORTS` | `airco-reports` | Report bucket |
| `S3_REGION` | `ap-southeast-2` | S3 region |
| `S3_ADDRESSING_STYLE` | `path` | Required for Supabase |
| `STORAGE_TYPE` | `supabase-s3` | Storage backend |
| `AUTH_SERVICE_URL` | `http://localhost:8001` | Auth Service URL |
| `KEYCLOAK_URL` | `http://localhost:8080` | Keycloak public URL |
| `KEYCLOAK_INTERNAL_URL` | (defaults to KEYCLOAK_URL) | Keycloak internal URL (Docker) |
| `KEYCLOAK_REALM` | `airco-insights` | Keycloak realm |
| `KEYCLOAK_ALLOWED_AZP` | `frontend-app` | Allowed authorized party |
| `AUTH_ALLOW_INSECURE_FALLBACK` | `false` | Emergency unverified decode |
| `ANTHROPIC_API_KEY` | — | Claude API key (hybrid mode) |
| `GROQ_API_KEY` | — | Groq API key (hybrid mode) |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model |
| `DATA_RETENTION_DAYS` | `7` | File retention period |
| `RETENTION_ENABLED` | `true` | Enable retention sweeper |
| `RETENTION_SWEEP_INTERVAL_MINUTES` | `60` | Sweep interval |
| `CORS_ORIGINS` | localhost + production domains | Allowed CORS origins |
| `TEMP_DIR` | `./tmp` | Temp file directory |

### Frontend

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API URL |
| `NEXT_PUBLIC_KEYCLOAK_URL` | Keycloak URL |
| `NEXT_PUBLIC_KEYCLOAK_REALM` | Keycloak realm |
| `NEXT_PUBLIC_KEYCLOAK_CLIENT_ID` | Keycloak client ID |
| `NEXT_PUBLIC_AIRCO_API_KEY` | Pre-configured AI API key |

## 15. Port Mapping Reference

| Service | Internal Port | External (Local) | External (EC2) |
|---------|--------------|------------------|----------------|
| Frontend | 3000 | 3000 | Nginx only |
| Backend | 8000 | 8000 | Nginx only |
| Auth Service | 8001 | 8001 | internal only |
| Keycloak | 8080 | 8080 | Nginx only |
| Redis | 6379 | 6379 | internal only |
| RabbitMQ AMQP | 5672 | 5672 | internal only |
| RabbitMQ Mgmt | 15672 | 15672 | internal only |
| Keycloak PG | 5432 | 5433 | internal only |
| App PG (EC2) | 5432 | — | internal only |
| Nginx HTTP | 80 | 80 | 80 |
| Nginx HTTPS | 443 | — | 443 |
