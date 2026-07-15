# Audit System — End-to-End Validation Checklist

## PRE-REQUISITES

1. Start the local stack:
   ```
   docker compose -f docker-compose.yml -f docker-compose.local.yml up -d
   ```
2. Open Supabase SQL Editor: https://supabase.com/dashboard/project/obemdprrqlmqqndutcgf/sql
3. Run `database/audit_validation_queries.sql` — Step 11 first to confirm tables exist and row counts are visible.

---

## STEP 1 — LOGIN TEST

**Action:** Log in once via the frontend.

**Verify in Supabase:**
```sql
-- Should return 1 row with user_id, tenant, ip, browser, login_time
SELECT s.id, u.email, t.tenant_slug, s.ip_address, s.browser, s.os, s.device_type, s.is_active, s.login_time
FROM sessions s
JOIN users u  ON s.user_id  = u.id
JOIN tenants t ON s.tenant_id = t.id
ORDER BY s.created_at DESC LIMIT 1;

-- Should return USER_LOGIN audit log
SELECT event_type, event_name, description, ip_address, status, timestamp
FROM audit_logs WHERE event_name = 'USER_LOGIN'
ORDER BY created_at DESC LIMIT 1;

-- Should show updated login_count + last_login_at
SELECT email, login_count, last_login_at FROM users ORDER BY last_login_at DESC LIMIT 1;
```

**Expected fields:**
- [ ] `user_id` — populated
- [ ] `tenant_id` — populated
- [ ] `ip_address` — populated
- [ ] `browser` — populated
- [ ] `login_time` — populated
- [ ] `is_active = true`
- [ ] `USER_LOGIN` audit log exists

---

## STEP 2 — UPLOAD TEST

**Action:** Upload 1 PDF (any bank).

**Verify in Supabase:**
```sql
-- Processing job should exist
SELECT pj.job_id, u.email, t.tenant_slug, pj.original_filename, pj.bank_name,
       pj.status, pj.file_size_bytes, pj.processing_time_ms, pj.upload_time
FROM processing_jobs pj
JOIN users u ON pj.user_id = u.id JOIN tenants t ON pj.tenant_id = t.id
ORDER BY pj.created_at DESC LIMIT 1;

-- Upload audit log
SELECT event_name, metadata->>'filename', metadata->>'bank_name', metadata->>'job_id', status
FROM audit_logs WHERE event_name = 'PDF_UPLOADED'
ORDER BY created_at DESC LIMIT 1;
```

**Expected fields:**
- [ ] `job_id` — follows pattern `JOB_YYYYMMDD_HHMMSS_XXXXXXXX`
- [ ] `original_filename` — matches uploaded file
- [ ] `bank_name` — correct bank detected
- [ ] `status` — `COMPLETED` or `FAILED`
- [ ] `file_size_bytes` — > 0
- [ ] `user_id` — linked to logged-in user
- [ ] `tenant_id` — linked to tenant

---

## STEP 3 — HYGIENE TEST

**Action:** (automatic after upload)

**Verify in Supabase:**
```sql
SELECT hr.page_count, hr.transaction_count, hr.is_healthy, hr.health_score,
       hr.warnings, hr.issues, hr.check_duration_ms, pj.original_filename
FROM hygiene_reports hr
JOIN processing_jobs pj ON hr.job_id = pj.id
ORDER BY hr.created_at DESC LIMIT 1;
```

**Expected fields:**
- [ ] `page_count` — > 0
- [ ] `transaction_count` — > 0
- [ ] `is_healthy` — true/false
- [ ] `warnings` — JSON array (may be empty)
- [ ] `issues` — JSON array (may be empty)
- [ ] `check_duration_ms` — > 0

---

## STEP 4 — PARSER TEST

**Action:** (automatic after upload)

**Verify in Supabase:**
```sql
SELECT pm.parser_type, pm.parser_name, pm.bank_name, pm.execution_time_ms,
       pm.transactions_extracted, pm.confidence_score, pm.fallback_level, pm.status
FROM parser_metrics pm
JOIN processing_jobs pj ON pm.job_id = pj.id
ORDER BY pm.created_at DESC LIMIT 5;
```

**Expected fields:**
- [ ] `parser_type` — `RULE_BASED` / `AI` / `HYBRID`
- [ ] `bank_name` — correct bank
- [ ] `execution_time_ms` — > 0
- [ ] `transactions_extracted` — > 0
- [ ] `confidence_score` — 0–100
- [ ] `fallback_level` — 0 for L1 success

---

## STEP 5 — EXCEL GENERATION TEST

**Action:** (automatic after successful parse)

**Verify in Supabase:**
```sql
SELECT rgl.excel_filename, rgl.sheet_count, rgl.template_used,
       rgl.generation_time_ms, rgl.data_quality_score, rgl.status
FROM report_generation_logs rgl
JOIN processing_jobs pj ON rgl.job_id = pj.id
ORDER BY rgl.created_at DESC LIMIT 1;
```

**Expected fields:**
- [ ] `excel_filename` — `.xlsx` file
- [ ] `sheet_count` — > 0 (e.g. 6 for HDFC, 11 for SBI)
- [ ] `generation_time_ms` — > 0
- [ ] `template_used` — bank name
- [ ] `status` — `COMPLETED`

---

## STEP 6 — DOWNLOAD TEST

**Action:** Download the generated Excel report.

**Verify in Supabase:**
```sql
SELECT dl.filename, dl.file_size_bytes, dl.download_number,
       dl.ip_address, dl.browser, u.email, pj.job_id
FROM download_logs dl
JOIN processing_jobs pj ON dl.job_id = pj.id
JOIN users u ON dl.user_id = u.id
ORDER BY dl.created_at DESC LIMIT 1;
```

**Expected fields:**
- [ ] `filename` — matches downloaded file
- [ ] `file_size_bytes` — > 0
- [ ] `download_number` — 1 (first download)
- [ ] `ip_address` — populated
- [ ] `user_id` — linked to logged-in user

---

## STEP 7 — JOB TIMELINE TEST

**Action:** Copy `job_id` from Step 2 result, then run:

```sql
SELECT je.event_type, je.event_name, je.status, je.duration_ms, je.timestamp
FROM job_events je
JOIN processing_jobs pj ON je.job_id = pj.id
WHERE pj.job_id = '<YOUR_JOB_ID>'
ORDER BY je.timestamp ASC;
```

**Expected sequence (happy path):**
- [ ] `FILE_UPLOADED`
- [ ] `HYGIENE_CHECK_STARTED`
- [ ] `HYGIENE_CHECK_COMPLETE`
- [ ] `PARSER_L1_STARTED`
- [ ] `PARSER_L1_SUCCESS`
- [ ] `EXCEL_GENERATION_STARTED`
- [ ] `EXCEL_GENERATION_COMPLETE`
- [ ] `PROCESSING_COMPLETED`

---

## STEP 8 — FULL AUDIT VIEW

```sql
SELECT * FROM v_job_complete_audit ORDER BY created_at DESC LIMIT 5;
```

- [ ] Returns one row per job with all pipeline columns populated

---

## STEP 9 — AUDIT OVERHEAD CHECK

```sql
SELECT pj.job_id, pj.file_size_bytes, pj.processing_time_ms AS total_ms,
       hr.check_duration_ms AS hygiene_ms, pm.execution_time_ms AS parser_ms,
       rgl.generation_time_ms AS excel_ms,
       pj.processing_time_ms - COALESCE(pm.execution_time_ms,0)
         - COALESCE(rgl.generation_time_ms,0)
         - COALESCE(hr.check_duration_ms,0) AS audit_overhead_ms
FROM processing_jobs pj
LEFT JOIN hygiene_reports hr ON hr.job_id = pj.id
LEFT JOIN parser_metrics pm  ON pm.job_id = pj.id AND pm.status = 'SUCCESS'
LEFT JOIN report_generation_logs rgl ON rgl.job_id = pj.id
WHERE pj.status = 'COMPLETED'
ORDER BY pj.created_at DESC LIMIT 5;
```

- [ ] `audit_overhead_ms` < 100ms per job

---

## STEP 10 — FAILURE SCENARIOS

### Failed PDF Test
- Upload a corrupt or unsupported PDF.
```sql
SELECT job_id, original_filename, status, error_code, error_message
FROM processing_jobs ORDER BY created_at DESC LIMIT 3;
```
- [ ] `status = 'FAILED'`
- [ ] `error_code` populated
- [ ] `error_message` populated

### Unsupported Format Test
```sql
SELECT ufq.issue_type, ufq.issue_description, ufq.queue_status, pj.original_filename
FROM unsupported_format_queue ufq
JOIN processing_jobs pj ON ufq.job_id = pj.id
ORDER BY ufq.created_at DESC LIMIT 3;
```
- [ ] Queue entry created for unsupported bank/format

---

## STEP 11 — PRODUCTION MONITORING TABLES

Run after applying `database/production_monitoring_schema.sql` to Supabase:

```sql
-- After backend restarts, system_health_logs should get rows within 60 seconds
SELECT host, cpu_percent, memory_percent, redis_healthy, rabbitmq_healthy,
       supabase_healthy, active_sessions, status, recorded_at
FROM system_health_logs ORDER BY recorded_at DESC LIMIT 5;

-- Every API call should log here
SELECT method, path, status_code, duration_ms, request_at
FROM api_request_logs ORDER BY request_at DESC LIMIT 10;

-- Any unhandled exceptions
SELECT error_type, service, job_id, severity, occurred_at
FROM error_logs ORDER BY occurred_at DESC LIMIT 10;
```

---

## SYSTEM TABLE ROW COUNT SUMMARY

Run this after all 6 tests above to confirm all tables are writing:

```sql
SELECT 'tenants' AS t, COUNT(*) FROM tenants
UNION ALL SELECT 'users',                COUNT(*) FROM users
UNION ALL SELECT 'sessions',             COUNT(*) FROM sessions
UNION ALL SELECT 'audit_logs',           COUNT(*) FROM audit_logs
UNION ALL SELECT 'processing_jobs',      COUNT(*) FROM processing_jobs
UNION ALL SELECT 'job_events',           COUNT(*) FROM job_events
UNION ALL SELECT 'hygiene_reports',      COUNT(*) FROM hygiene_reports
UNION ALL SELECT 'parser_metrics',       COUNT(*) FROM parser_metrics
UNION ALL SELECT 'report_generation_logs', COUNT(*) FROM report_generation_logs
UNION ALL SELECT 'download_logs',        COUNT(*) FROM download_logs
UNION ALL SELECT 'unsupported_format_queue', COUNT(*) FROM unsupported_format_queue
UNION ALL SELECT 'system_health_logs',   COUNT(*) FROM system_health_logs
UNION ALL SELECT 'api_request_logs',     COUNT(*) FROM api_request_logs
UNION ALL SELECT 'error_logs',           COUNT(*) FROM error_logs;
```

**All tables must have > 0 rows after testing. Any table with 0 rows means that write path is broken.**

---

## FREEZE GATE — Do NOT proceed to more features until:

- [ ] 100 PDFs tested across all 13 banks
- [ ] 20 unique users tested
- [ ] Multi-tenant isolation verified (2+ tenants)
- [ ] All 14 audit tables have rows
- [ ] Audit overhead < 100ms confirmed
- [ ] Download logs verified
- [ ] Failure scenarios verified (FAILED + unsupported queue)
- [ ] `v_job_complete_audit` returns clean one-row-per-job data
- [ ] `v_job_timeline` returns full pipeline sequence per job
