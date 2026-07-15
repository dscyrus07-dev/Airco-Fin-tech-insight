-- =============================================================================
-- AIRCO INSIGHTS — AUDIT SYSTEM VALIDATION QUERIES
-- Use these queries in Supabase SQL Editor to verify every write path
-- =============================================================================


-- =============================================================================
-- STEP 1: LOGIN VALIDATION
-- Run after one login. Should return 1 row.
-- =============================================================================

-- 1a. Check session was created
SELECT
    s.id           AS session_id,
    u.email        AS user_email,
    u.user_id      AS user_keycloak_id,
    t.tenant_slug  AS tenant,
    s.ip_address,
    s.browser,
    s.os,
    s.device_type,
    s.is_active,
    s.login_time
FROM sessions s
JOIN users u  ON s.user_id  = u.id
JOIN tenants t ON s.tenant_id = t.id
ORDER BY s.created_at DESC
LIMIT 1;

-- 1b. Check login audit log was created
SELECT
    al.event_type,
    al.event_name,
    al.description,
    al.ip_address,
    al.status,
    al.severity,
    al.timestamp
FROM audit_logs al
WHERE al.event_name = 'USER_LOGIN'
ORDER BY al.created_at DESC
LIMIT 1;

-- 1c. Check user login stats were updated
SELECT
    u.email,
    u.login_count,
    u.last_login_at
FROM users u
ORDER BY u.last_login_at DESC
LIMIT 1;


-- =============================================================================
-- STEP 2: UPLOAD / PROCESSING JOB VALIDATION
-- Run after uploading 1 PDF. Should return 1 row with all fields populated.
-- =============================================================================

-- 2a. Check processing job was created
SELECT
    pj.job_id,
    u.email               AS user_email,
    t.tenant_slug         AS tenant,
    pj.original_filename,
    pj.file_size_bytes,
    pj.file_hash,
    pj.bank_name,
    pj.status,
    pj.processing_mode,
    pj.transaction_count,
    pj.processing_time_ms,
    pj.upload_time
FROM processing_jobs pj
JOIN users u   ON pj.user_id   = u.id
JOIN tenants t ON pj.tenant_id = t.id
ORDER BY pj.created_at DESC
LIMIT 1;

-- 2b. Check upload event was created in audit_logs
SELECT
    al.event_type,
    al.event_name,
    al.metadata->>'filename'  AS filename,
    al.metadata->>'bank_name' AS bank,
    al.metadata->>'job_id'    AS job_id,
    al.status,
    al.timestamp
FROM audit_logs al
WHERE al.event_name = 'PDF_UPLOADED'
ORDER BY al.created_at DESC
LIMIT 1;


-- =============================================================================
-- STEP 3: HYGIENE REPORT VALIDATION
-- Run after uploading a PDF. Should return 1 row.
-- =============================================================================

SELECT
    hr.id,
    pj.job_id,
    pj.original_filename,
    hr.format_id,
    hr.page_count,
    hr.transaction_count,
    hr.is_healthy,
    hr.health_score,
    hr.warnings,
    hr.issues,
    hr.check_duration_ms,
    hr.check_time
FROM hygiene_reports hr
JOIN processing_jobs pj ON hr.job_id = pj.id
ORDER BY hr.created_at DESC
LIMIT 1;


-- =============================================================================
-- STEP 4: PARSER METRICS VALIDATION
-- Run after a PDF is processed. Should return 1 row per parser attempt.
-- =============================================================================

SELECT
    pm.id,
    pj.job_id,
    pj.original_filename,
    pm.parser_type,
    pm.parser_name,
    pm.bank_name,
    pm.execution_time_ms,
    pm.transactions_extracted,
    pm.confidence_score,
    pm.fallback_level,
    pm.status,
    pm.error_message
FROM parser_metrics pm
JOIN processing_jobs pj ON pm.job_id = pj.id
ORDER BY pm.created_at DESC
LIMIT 5;


-- =============================================================================
-- STEP 5: EXCEL GENERATION VALIDATION
-- Run after successful processing. Should return 1 row.
-- =============================================================================

SELECT
    rgl.id,
    pj.job_id,
    pj.original_filename,
    rgl.excel_filename,
    rgl.sheet_count,
    rgl.template_used,
    rgl.generation_time_ms,
    rgl.excel_file_size_bytes,
    rgl.data_quality_score,
    rgl.status,
    rgl.generation_start_time
FROM report_generation_logs rgl
JOIN processing_jobs pj ON rgl.job_id = pj.id
ORDER BY rgl.created_at DESC
LIMIT 1;


-- =============================================================================
-- STEP 6: DOWNLOAD LOG VALIDATION
-- Run after downloading a report. Should return 1 row.
-- =============================================================================

SELECT
    dl.id,
    pj.job_id,
    u.email          AS user_email,
    dl.filename,
    dl.file_size_bytes,
    dl.download_number,
    dl.ip_address,
    dl.browser,
    dl.os,
    dl.download_time
FROM download_logs dl
JOIN processing_jobs pj ON dl.job_id = pj.id
JOIN users u             ON dl.user_id = u.id
ORDER BY dl.created_at DESC
LIMIT 1;


-- =============================================================================
-- STEP 7: JOB EVENTS TIMELINE VALIDATION
-- Run with a real job_id. Should show full pipeline timeline.
-- Replace 'JOB_XXXXXXXX_XXXXXX_XXXXXXXX' with an actual job_id
-- =============================================================================

SELECT
    je.event_type,
    je.event_name,
    je.event_category,
    je.description,
    je.status,
    je.duration_ms,
    je.metadata,
    je.timestamp
FROM job_events je
JOIN processing_jobs pj ON je.job_id = pj.id
WHERE pj.job_id = 'REPLACE_WITH_ACTUAL_JOB_ID'
ORDER BY je.timestamp ASC;

-- 7b. Get latest job_id first, then use it above
SELECT
    pj.job_id,
    pj.original_filename,
    pj.status,
    pj.upload_time
FROM processing_jobs pj
ORDER BY pj.created_at DESC
LIMIT 5;


-- =============================================================================
-- STEP 8: COMPLETE ONE-ROW-PER-JOB AUDIT VIEW (STEP 2 in validation plan)
-- =============================================================================

SELECT
    pj.job_id,
    u.email              AS user_email,
    t.tenant_slug        AS tenant,
    pj.original_filename,
    pj.bank_name,
    pj.status,
    pj.processing_time_ms,
    hr.page_count,
    hr.transaction_count,
    hr.is_healthy,
    pm.parser_type,
    pm.fallback_level,
    pm.confidence_score,
    rgl.excel_filename,
    rgl.sheet_count,
    rgl.generation_time_ms,
    dl.download_number   AS times_downloaded,
    pj.upload_time
FROM processing_jobs pj
JOIN users u                            ON pj.user_id = u.id
JOIN tenants t                          ON pj.tenant_id = t.id
LEFT JOIN hygiene_reports hr            ON hr.job_id = pj.id
LEFT JOIN parser_metrics pm             ON pm.job_id = pj.id AND pm.fallback_level = (
    SELECT MIN(fallback_level) FROM parser_metrics WHERE job_id = pj.id AND status = 'SUCCESS'
)
LEFT JOIN report_generation_logs rgl   ON rgl.job_id = pj.id
LEFT JOIN (
    SELECT job_id, MAX(download_number) AS download_number
    FROM download_logs GROUP BY job_id
) dl                                   ON dl.job_id = pj.id
ORDER BY pj.created_at DESC
LIMIT 20;


-- =============================================================================
-- STEP 9: MASTER TIMELINE FOR ONE JOB (STEP 3 in validation plan)
-- Replace 'REPLACE_WITH_ACTUAL_JOB_ID' with real job_id
-- =============================================================================

SELECT
    je.event_type     AS stage,
    je.event_name     AS event,
    je.status,
    je.duration_ms,
    je.timestamp
FROM job_events je
JOIN processing_jobs pj ON je.job_id = pj.id
WHERE pj.job_id = 'REPLACE_WITH_ACTUAL_JOB_ID'
ORDER BY je.timestamp ASC;


-- =============================================================================
-- STEP 10: AUDIT OVERHEAD MEASUREMENT (STEP 4 in validation plan)
-- Compare processing_time_ms vs audit write overhead
-- =============================================================================

SELECT
    pj.job_id,
    pj.file_size_bytes,
    pj.processing_time_ms                             AS total_processing_ms,
    hr.check_duration_ms                              AS hygiene_ms,
    pm.execution_time_ms                              AS parser_ms,
    rgl.generation_time_ms                            AS excel_gen_ms,
    pj.processing_time_ms - COALESCE(pm.execution_time_ms, 0)
        - COALESCE(rgl.generation_time_ms, 0)
        - COALESCE(hr.check_duration_ms, 0)           AS audit_overhead_ms
FROM processing_jobs pj
LEFT JOIN hygiene_reports hr           ON hr.job_id = pj.id
LEFT JOIN parser_metrics pm            ON pm.job_id = pj.id AND pm.status = 'SUCCESS'
LEFT JOIN report_generation_logs rgl   ON rgl.job_id = pj.id
WHERE pj.status = 'COMPLETED'
ORDER BY pj.created_at DESC
LIMIT 10;


-- =============================================================================
-- STEP 11: FULL SYSTEM HEALTH SUMMARY
-- Overall audit system health check
-- =============================================================================

SELECT
    'tenants'               AS table_name, COUNT(*) AS row_count FROM tenants
UNION ALL SELECT 'users',                  COUNT(*) FROM users
UNION ALL SELECT 'sessions',               COUNT(*) FROM sessions
UNION ALL SELECT 'audit_logs',             COUNT(*) FROM audit_logs
UNION ALL SELECT 'processing_jobs',        COUNT(*) FROM processing_jobs
UNION ALL SELECT 'job_events',             COUNT(*) FROM job_events
UNION ALL SELECT 'hygiene_reports',        COUNT(*) FROM hygiene_reports
UNION ALL SELECT 'parser_metrics',         COUNT(*) FROM parser_metrics
UNION ALL SELECT 'report_generation_logs', COUNT(*) FROM report_generation_logs
UNION ALL SELECT 'download_logs',          COUNT(*) FROM download_logs
UNION ALL SELECT 'unsupported_format_queue', COUNT(*) FROM unsupported_format_queue;


-- =============================================================================
-- STEP 12: RECENT FAILURES — Quick triage for any broken pipeline
-- =============================================================================

-- Failed processing jobs
SELECT
    pj.job_id,
    pj.original_filename,
    pj.bank_name,
    pj.error_code,
    pj.error_message,
    pj.upload_time
FROM processing_jobs pj
WHERE pj.status = 'FAILED'
ORDER BY pj.created_at DESC
LIMIT 10;

-- Failed parser attempts (fallback chain)
SELECT
    pj.job_id,
    pj.original_filename,
    pm.parser_type,
    pm.fallback_level,
    pm.error_code,
    pm.error_message,
    pm.created_at
FROM parser_metrics pm
JOIN processing_jobs pj ON pm.job_id = pj.id
WHERE pm.status = 'FAILED'
ORDER BY pm.created_at DESC
LIMIT 10;

-- Unsupported format queue
SELECT
    ufq.id,
    pj.job_id,
    pj.original_filename,
    ufq.issue_type,
    ufq.issue_description,
    ufq.issue_severity,
    ufq.queue_status,
    ufq.queued_time
FROM unsupported_format_queue ufq
JOIN processing_jobs pj ON ufq.job_id = pj.id
ORDER BY ufq.created_at DESC
LIMIT 10;
