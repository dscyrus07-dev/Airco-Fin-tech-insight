# N8 — Data Retention Ledger (measured on `onb`)

Method: code/config walk + a live proof on the `onb` stack. A synthetic 1-page
statement (`probe_clean.pdf`, sha8 of file-content hash only) was uploaded as an
anonymous job (`job8 4baee914`), processed to completion, then
`retention_expires_at` was set to the past and `RetentionService.sweep_once()`
was invoked manually. Every sink was inventoried before and after. No statement
content, customer names or secret values appear in this report.

## Sink ledger

| # | Where data lands | Deleter | SLA (code) | Measured after manual sweep | Verdict |
|---|---|---|---|---|---|
| 1 | Source PDF → S3 `airco-files` object | `RetentionService` → `file_history_service.purge_expired_record` | `retention_expires_at` = created+7d | object **GONE** | holds |
| 2 | Generated workbook → `/app/tmp` (docker vol `onb_backend_tmp`) | same purge, temp cleanup branch | at sweep | file **GONE** | holds |
| 3 | `user_file_records` row | soft-delete only (`deleted_at`, `deletion_status`) | none for row itself | row persists: `original_filename`, `report_filename`, `upload_object_key` (dangling), `statement_engine` block, user id, full_name | metadata forever |
| 4 | `processing_jobs` audit row | nobody | none | row persists (filename, counts, verdicts, timings) | **no retention** |
| 5 | `raw_transactions` (JSONB, complete extracted rows) | nobody | none | 1 row persists after sweep; 575 rows exist in DB | **7-day promise broken — statement content lives forever** |
| 6 | `job_events` | nobody | none | 3 rows persist; 1811 rows in DB | **no retention** |
| 7 | `statement_metadata` (masked acct, dates, aggregates, indicators, `extra`, statement header incl. first-page text) | nobody | none | 1 row persists; 572 rows in DB | **no retention; header text can contain content/PII** |
| 8 | Redis `airco:job:<id>` blob (`input_data` = `pdf_password`, `api_key`, `file_path`, `user_info`, `original_filename`, `upload_object_key`; `result_data` = paths, profiles, stats) | key TTL | 86400s | TTL verified ~24h | holds, but **secrets sit in Redis plaintext for 24h** |
| 9 | Redis index sets (`airco:job:user:<id>`, `airco:job:status:<s>`, `airco:analysis:index`) | nobody | none | `NO_TTL` measured | job/user ids forever (minor) |
| 10 | Redis `airco:analysis:<id>` | key TTL + `purge_expired` | 25h | TTL verified | holds |
| 11 | RabbitMQ `file_upload_queue` payload (`full_name`, `user_email`, `original_filename`, `file_path`, `pdf_password`, `api_key`) | consumer ack | at ack | consumed on happy path | holds, but **secrets+PII traverse the broker** |
| 12 | RabbitMQ `dead_letter_queue` | nobody | none | **36+ messages inventoried, no TTL/expiry; payloads carry full PII+secret fields** | **7-day promise broken — DLQ never expires** |
| 13 | Docker logs (`local` driver, no explicit rotation config) | driver defaults (~5×20MB) | none | `original_filename`, S3 object key, job_id, user id, per-file hygiene block (filename, page count, txn count, date range) written to INFO logs | filenames/metadata persist until rolled |
| 14 | Legacy `transactions` table | n/a | — | 0 rows — dead table | n/a |
| 15 | Browser `localStorage["airco-form-data"]` (`userDetails`, `apiKey`, `mode`, `step`) | nobody | none | no TTL/expiry path in code | **API key + user details persist indefinitely client-side** |
| 16 | Browser `sessionStorage` (`kc_token`, `kc_refresh_token`, PKCE verifier) | tab close | session | by design | holds |
| 17 | System temp (`tempfile.NamedTemporaryFile`, backend `/tmp`, + `_decrypted` sibling) | worker `cleanup_file` in `finally` | at job end | cleaned on happy path (measured 0 left) | **orphans possible on worker crash/restart — no reaper** |
| 18 | `/app/tmp` orphans (untracked files) | nobody | none | **245 files / 8.7MB accumulated** in shared volume | accumulation without sweep |
| 19 | `statement_engine` block + job result `stats`/profiles inside `user_file_records`/redis | with row/blob | soft-delete/24h | persists in record | metadata forever |

## What the audit trail keeps vs what it should

- **Kept forever (post-sweep)**: file record row (filenames, object keys, user id,
  engine/verdict), `processing_jobs` row (filename, counts, verdicts, timings),
  `job_events` (event metadata incl. errors), `statement_metadata` (masked
  account no., statement dates, aggregates, indicators, free-form `extra`,
  statement header incl. `first_page_text`/`raw_header_text`),
  `raw_transactions` (complete transaction rows as JSONB).
- **Statement content or PII inside**: `raw_transactions` = full statement rows.
  `statement_metadata` header text = first-page text (may contain name/address/
  account fragments). `user_file_records.original_filename` = user-supplied.
  Job events may embed error strings containing bank-specific text.
- **Conclusion**: the 7-day customer promise holds only for the S3 source PDF
  and the generated workbook. All extracted content and statement metadata
  outlive it indefinitely in Postgres; queue dead-letters and Redis index sets
  also never expire.

## Retention guarantees

HOLD: source PDF (S3), generated workbook (temp), analysis records (25h),
job blobs (24h), session tokens (browser).

FAIL: raw transactions (forever), statement metadata incl. header text
(forever), processing_jobs/job_events (forever), RabbitMQ DLQ payloads (forever,
contain `pdf_password`+`api_key`+PII), browser `localStorage` apiKey/userDetails
(forever), file-record metadata (forever, by soft-delete design).

RISK: docker logs carry filenames/object keys/statement stats until driver
rollover; system-temp uploads orphan on crash; `/app/tmp` accumulates untracked
files (245 observed); Redis index sets never expire (ids only).

## Reproduction

1. Upload synthetic PDF → `POST /api/upload/bank-statement-async` (anonymous).
2. `job8` → completed.
3. Inside `onb_backend`: `UPDATE user_file_records SET retention_expires_at='2020-01-01' WHERE job_id=...`
4. `asyncio.run(RetentionService().sweep_once())` → returned `1`.
5. `tools/n8/retention_probe.py` before/after prints the ledger above.

Tool: `tools/n8/retention_probe.py` (runs inside the backend container; prints
counts and key patterns only).
