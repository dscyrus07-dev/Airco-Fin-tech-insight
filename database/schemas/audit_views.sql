-- =============================================================================
-- AIRCO INSIGHTS — AUDIT VALIDATION VIEWS
-- Run once in Supabase SQL Editor to create persistent views
-- =============================================================================


-- =============================================================================
-- VIEW 1: v_job_complete_audit
-- One row per job — full pipeline summary
-- =============================================================================

CREATE OR REPLACE VIEW v_job_complete_audit AS
SELECT
    pj.job_id,
    pj.id                       AS internal_job_id,
    u.email                     AS user_email,
    u.user_id                   AS user_keycloak_id,
    t.tenant_slug               AS tenant,
    pj.original_filename,
    pj.bank_name,
    pj.status,
    pj.processing_mode,
    pj.file_size_bytes,
    pj.processing_time_ms,

    -- Hygiene
    hr.page_count,
    hr.transaction_count,
    hr.is_healthy,
    hr.health_score,
    hr.warnings                 AS hygiene_warnings,
    hr.issues                   AS hygiene_issues,
    hr.check_duration_ms        AS hygiene_check_ms,

    -- Parser
    pm.parser_type,
    pm.parser_name,
    pm.fallback_level,
    pm.confidence_score,
    pm.execution_time_ms        AS parser_exec_ms,

    -- Excel generation
    rgl.excel_filename,
    rgl.sheet_count,
    rgl.template_used,
    rgl.generation_time_ms,
    rgl.data_quality_score,

    -- Downloads
    dl.times_downloaded,
    dl.last_download_time,

    pj.upload_time,
    pj.created_at
FROM processing_jobs pj
JOIN users u   ON pj.user_id   = u.id
JOIN tenants t ON pj.tenant_id = t.id
LEFT JOIN hygiene_reports hr ON hr.job_id = pj.id
LEFT JOIN LATERAL (
    SELECT *
    FROM parser_metrics
    WHERE job_id = pj.id
    ORDER BY fallback_level ASC, created_at ASC
    LIMIT 1
) pm ON true
LEFT JOIN report_generation_logs rgl ON rgl.job_id = pj.id
LEFT JOIN (
    SELECT
        job_id,
        COUNT(*)            AS times_downloaded,
        MAX(download_time)  AS last_download_time
    FROM download_logs
    GROUP BY job_id
) dl ON dl.job_id = pj.id;


-- =============================================================================
-- VIEW 2: v_job_timeline
-- Full event timeline per job — ordered chronologically
-- Usage: SELECT * FROM v_job_timeline WHERE job_id = 'JOB_XXXXXXXX';
-- =============================================================================

CREATE OR REPLACE VIEW v_job_timeline AS
SELECT
    pj.job_id,
    pj.original_filename,
    pj.bank_name,
    pj.status               AS job_status,
    je.event_type,
    je.event_name,
    je.event_category,
    je.description,
    je.status               AS event_status,
    je.duration_ms,
    je.metadata,
    je.error_message,
    je.timestamp
FROM job_events je
JOIN processing_jobs pj ON je.job_id = pj.id
ORDER BY je.timestamp ASC;


-- =============================================================================
-- VIEW 3: v_session_activity
-- Active and recent sessions with user context
-- =============================================================================

CREATE OR REPLACE VIEW v_session_activity AS
SELECT
    s.id            AS session_id,
    u.email         AS user_email,
    u.user_id       AS user_keycloak_id,
    t.tenant_slug   AS tenant,
    s.ip_address,
    s.browser,
    s.os,
    s.device_type,
    s.is_active,
    s.login_time,
    s.logout_time,
    s.session_duration_seconds,
    s.logout_reason
FROM sessions s
JOIN users u   ON s.user_id   = u.id
JOIN tenants t ON s.tenant_id = t.id
ORDER BY s.login_time DESC;


-- =============================================================================
-- VIEW 4: v_audit_trail
-- Full audit log with user context (most recent first)
-- =============================================================================

CREATE OR REPLACE VIEW v_audit_trail AS
SELECT
    al.id           AS log_id,
    al.event_type,
    al.event_name,
    al.event_category,
    al.description,
    u.email         AS user_email,
    t.tenant_slug   AS tenant,
    al.ip_address,
    al.status,
    al.severity,
    al.metadata,
    al.error_message,
    al.timestamp
FROM audit_logs al
JOIN tenants t ON al.tenant_id = t.id
LEFT JOIN users u ON al.user_id = u.id
ORDER BY al.timestamp DESC;


-- =============================================================================
-- VIEW 5: v_parser_performance
-- Parser performance stats per bank
-- =============================================================================

CREATE OR REPLACE VIEW v_parser_performance AS
SELECT
    pm.bank_name,
    pm.parser_type,
    COUNT(*)                                    AS total_attempts,
    COUNT(CASE WHEN pm.status = 'SUCCESS' THEN 1 END) AS successes,
    COUNT(CASE WHEN pm.status = 'FAILED'  THEN 1 END) AS failures,
    ROUND(
        COUNT(CASE WHEN pm.status = 'SUCCESS' THEN 1 END)::DECIMAL
        / NULLIF(COUNT(*), 0) * 100, 2
    )                                           AS success_rate_pct,
    ROUND(AVG(pm.execution_time_ms), 0)         AS avg_execution_ms,
    ROUND(AVG(pm.confidence_score), 2)          AS avg_confidence,
    ROUND(AVG(pm.transactions_extracted), 0)    AS avg_transactions,
    AVG(pm.fallback_level)                      AS avg_fallback_level
FROM parser_metrics pm
GROUP BY pm.bank_name, pm.parser_type
ORDER BY total_attempts DESC;


-- =============================================================================
-- VIEW 6: v_daily_stats
-- Daily processing summary per tenant
-- =============================================================================

CREATE OR REPLACE VIEW v_daily_stats AS
SELECT
    t.tenant_slug               AS tenant,
    DATE(pj.upload_time)        AS processing_date,
    COUNT(*)                    AS total_jobs,
    COUNT(CASE WHEN pj.status = 'COMPLETED' THEN 1 END)  AS completed,
    COUNT(CASE WHEN pj.status = 'FAILED'    THEN 1 END)  AS failed,
    SUM(pj.transaction_count)   AS total_transactions,
    ROUND(AVG(pj.processing_time_ms), 0) AS avg_processing_ms,
    COUNT(DISTINCT pj.user_id)  AS unique_users
FROM processing_jobs pj
JOIN tenants t ON pj.tenant_id = t.id
GROUP BY t.tenant_slug, DATE(pj.upload_time)
ORDER BY processing_date DESC, tenant;


-- =============================================================================
-- VIEW 7: v_download_activity
-- Download activity with job context
-- =============================================================================

CREATE OR REPLACE VIEW v_download_activity AS
SELECT
    dl.id           AS download_id,
    pj.job_id,
    pj.original_filename,
    pj.bank_name,
    u.email         AS downloaded_by,
    t.tenant_slug   AS tenant,
    dl.filename     AS downloaded_filename,
    dl.file_size_bytes,
    dl.download_number,
    dl.ip_address,
    dl.browser,
    dl.os,
    dl.download_time
FROM download_logs dl
JOIN processing_jobs pj ON dl.job_id = pj.id
JOIN users u             ON dl.user_id = u.id
JOIN tenants t           ON dl.tenant_id = t.id
ORDER BY dl.download_time DESC;


-- =============================================================================
-- VIEW 8: v_unsupported_queue
-- Unsupported format queue with context
-- =============================================================================

CREATE OR REPLACE VIEW v_unsupported_queue AS
SELECT
    ufq.id          AS queue_id,
    pj.job_id,
    pj.original_filename,
    u.email         AS user_email,
    t.tenant_slug   AS tenant,
    ufq.issue_type,
    ufq.issue_description,
    ufq.issue_severity,
    ufq.queue_status,
    ufq.suggested_action,
    ufq.queued_time,
    ufq.sla_due_at
FROM unsupported_format_queue ufq
JOIN processing_jobs pj ON ufq.job_id = pj.id
JOIN users u             ON pj.user_id = u.id
JOIN tenants t           ON ufq.tenant_id = t.id
ORDER BY ufq.queued_time DESC;
