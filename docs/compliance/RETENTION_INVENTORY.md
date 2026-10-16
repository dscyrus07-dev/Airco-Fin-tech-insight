# Retention Inventory — 7-day promise (measured on `rc`, 2026-10-16)

Report only — no code changed. Counts measured live (remote Postgres, rc Redis,
rc RabbitMQ, Supabase S3). "Expired mechanism" = what enforces deletion today;
"smallest change" = the generic enforcement step, not an implementation.

## Database (Postgres) — counts older than 7 days

| table | stores | total | >7d | expiry today | smallest change |
|---|---|---|---|---|---|
| `raw_transactions` | full extracted statement rows (account-level PII) | 675 | **159** | none | retention sweeper DELETE where created_at < now()-7d |
| `statement_metadata` | statement metadata incl. holder fields | 670 | **158** | none | same sweep row |
| `processing_jobs` | job payloads + `upload_object_key`/`report_object_key` | 829 | **172** | none | same; also strip object keys from persisted payload |
| `job_events` | per-job event trail | 2,116 | **322** | none | cascade with processing_jobs sweep |
| `user_file_records` (file history) | file rows + object keys | 829 | **172** | none | sweep; this is what the UI "history" shows |
| `api_request_logs` | request paths (37k rows) | 34,712 | **15,656** | none | rolling DELETE/partition drop |
| `report_generation_logs` | `excel_file_path` etc. | 673 | **159** | none | sweep |
| `api_keys` | `key_hash` + `key_prefix` only (no plaintext) | 30 | 30 | by design — long-lived credentials | revoke flow, not retention |
| `audit_logs` / `download_logs` | audit events | 3 / 0 | 0 | none yet (new tables) | include in sweep when they fill |
| `users` | `password_hash` (auth) | 11 | 10 | auth table — out of 7-day scope | n/a |

**PDF passwords**: no `pdf_password`/`password` column exists in any public
table — passwords are not persisted in Postgres. ✓

## Redis (rc) — live TTLs

| keyspace | stores | TTL observed | expiry today | smallest change |
|---|---|---|---|---|
| `airco:analysis:*` | analyze payloads (statement text/meta) | ~24,000–25,000 s (~7 h) | expires ✓ | none needed |
| `airco:job:<uuid>` | job blob — **carries a `pdf_password` field** (empty in sample; real value when a locked PDF is uploaded) | ~21,000 s (~6 h) | expires ✓, but plaintext while alive | drop the field after unlock / store hash instead |
| `airco:job:user:<uid>` | user→job-id index set | **TTL=-1** | **never expires** | `EXPIRE` on write (e.g. 30d) — holds ids only, low risk |

## RabbitMQ (rc)

| queue | stores | now | expiry today | smallest change |
|---|---|---|---|---|
| `file_upload_queue` | upload payloads (statement metadata + file refs; N8 proved statement content + secrets persist in payloads) | 1 in-flight | durable, **no message TTL, no policy** | queue `x-message-ttl` or payload-field minimisation |
| `dead_letter_queue` | rejected/failed payloads | 0 | durable, no TTL, no reaper | `x-message-ttl` on DLQ + scheduled purge |

## S3 (Supabase buckets)

| bucket | stores | objects | >7d | lifecycle rules | smallest change |
|---|---|---|---|---|---|
| `airco-files` | uploaded source PDFs (`users/…`) | 850 | 2 | **none** | bucket lifecycle rule expire 7d, or sweeper issues delete-by-age |
| `airco-reports` | generated workbooks (`users/…`) | 537 | 1 | **none** | same |

Note: keys embed the user email (`users/<email>/reports/…`) — email lands in
bucket listings and backend logs (minor).

## Logs & filesystem

| place | stores | expiry | smallest change |
|---|---|---|---|
| backend container logs | `/app/tmp` paths, S3 object keys (with user email), `guest:guest` AMQP URL; no amounts/IFSC/narration observed | docker json-file defaults | redact path/key fields in the two log lines |
| `/app/tmp` (container FS) | staged uploads + generated `.xlsx`/`.pdf` | persists until container is recreated | post-upload delete + post-report delete (sweep on startup) |
| browser `localStorage` | apiKey/userDetails (carried N8) | never | move to sessionStorage / clear on logout |

## Summary — places with NO expiry

Postgres: `raw_transactions`, `statement_metadata`, `processing_jobs`,
`job_events`, `user_file_records`, `api_request_logs`,
`report_generation_logs` — **all have rows >7 days and zero enforcement**.
Redis: `airco:job:user:*` index sets (ids only). RabbitMQ: both durable queues
(message TTL unset; DLQ un-reaped). S3: both buckets (no lifecycle rules).
`/app/tmp` inside the container. Browser localStorage.

Only `airco:analysis:*` and `airco:job:<uuid>` blobs expire (~6–7 h TTL).
The 7-day promise is therefore currently met for nothing except the two Redis
keyspaces — the DB, queues, buckets and files all retain data indefinitely.
