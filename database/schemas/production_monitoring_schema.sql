-- =============================================================================
-- AIRCO INSIGHTS — PRODUCTION MONITORING SCHEMA (STEP 5)
-- Run once in Supabase SQL Editor
-- Adds: system_health_logs, api_request_logs, error_logs
-- =============================================================================


-- =============================================================================
-- TABLE: system_health_logs
-- Tracks system resource usage every minute
-- =============================================================================

CREATE TABLE IF NOT EXISTS system_health_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Service identification
    host VARCHAR(100) NOT NULL,
    environment VARCHAR(20) DEFAULT 'PRODUCTION',  -- PRODUCTION, STAGING, LOCAL

    -- CPU / Memory / Disk
    cpu_percent       DECIMAL(5, 2),
    memory_percent    DECIMAL(5, 2),
    memory_used_mb    INTEGER,
    memory_total_mb   INTEGER,
    disk_percent      DECIMAL(5, 2),
    disk_used_gb      DECIMAL(10, 2),
    disk_total_gb     DECIMAL(10, 2),

    -- Service health (true = healthy)
    redis_healthy     BOOLEAN,
    rabbitmq_healthy  BOOLEAN,
    minio_healthy     BOOLEAN,
    supabase_healthy  BOOLEAN,
    keycloak_healthy  BOOLEAN,

    -- Service latencies (ms)
    redis_latency_ms     INTEGER,
    rabbitmq_latency_ms  INTEGER,
    minio_latency_ms     INTEGER,
    supabase_latency_ms  INTEGER,
    keycloak_latency_ms  INTEGER,

    -- Queue depths
    rabbitmq_ready_messages   INTEGER,
    rabbitmq_unacked_messages INTEGER,

    -- Active sessions / jobs
    active_sessions   INTEGER,
    active_jobs       INTEGER,

    -- Overall status
    status        VARCHAR(20) DEFAULT 'HEALTHY',  -- HEALTHY, DEGRADED, CRITICAL
    alerts        JSONB DEFAULT '[]',

    -- Timestamp
    recorded_at   TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at    TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_system_health_recorded_at ON system_health_logs(recorded_at DESC);
CREATE INDEX idx_system_health_status      ON system_health_logs(status);
CREATE INDEX idx_system_health_host        ON system_health_logs(host);


-- =============================================================================
-- TABLE: api_request_logs
-- Tracks every API request
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_request_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Request identity
    request_id    VARCHAR(255),
    correlation_id VARCHAR(255),

    -- Route
    method        VARCHAR(10)  NOT NULL,
    path          VARCHAR(500) NOT NULL,
    status_code   INTEGER      NOT NULL,

    -- Timing
    duration_ms   INTEGER,
    request_at    TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- User context
    tenant_id     UUID REFERENCES tenants(id) ON DELETE SET NULL,
    user_id       UUID REFERENCES users(id)   ON DELETE SET NULL,
    session_id    UUID REFERENCES sessions(id) ON DELETE SET NULL,
    ip_address    INET,
    user_agent    TEXT,

    -- Request details
    request_size_bytes  INTEGER,
    response_size_bytes INTEGER,
    query_params  JSONB DEFAULT '{}',

    -- Error
    error_message TEXT,
    error_code    VARCHAR(50),

    created_at    TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_api_requests_path         ON api_request_logs(path);
CREATE INDEX idx_api_requests_status_code  ON api_request_logs(status_code);
CREATE INDEX idx_api_requests_user_id      ON api_request_logs(user_id);
CREATE INDEX idx_api_requests_tenant_id    ON api_request_logs(tenant_id);
CREATE INDEX idx_api_requests_request_at   ON api_request_logs(request_at DESC);
CREATE INDEX idx_api_requests_duration     ON api_request_logs(duration_ms);
CREATE INDEX idx_api_requests_correlation  ON api_request_logs(correlation_id);


-- =============================================================================
-- TABLE: error_logs
-- Structured error and exception tracking
-- =============================================================================

CREATE TABLE IF NOT EXISTS error_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Error identity
    error_code        VARCHAR(100),
    error_type        VARCHAR(100) NOT NULL,  -- ValueError, HTTPException, TimeoutError, etc.
    error_message     TEXT         NOT NULL,
    traceback         TEXT,

    -- Where it happened
    service           VARCHAR(100),           -- upload, download, parser, excel, auth
    module            VARCHAR(255),
    function_name     VARCHAR(255),
    line_number       INTEGER,

    -- Context
    tenant_id         UUID REFERENCES tenants(id)          ON DELETE SET NULL,
    user_id           UUID REFERENCES users(id)             ON DELETE SET NULL,
    session_id        UUID REFERENCES sessions(id)          ON DELETE SET NULL,
    job_id            VARCHAR(100),
    request_id        VARCHAR(255),
    correlation_id    VARCHAR(255),

    -- Request context
    endpoint          VARCHAR(500),
    method            VARCHAR(10),
    ip_address        INET,

    -- Severity
    severity          VARCHAR(20) DEFAULT 'ERROR',  -- WARNING, ERROR, CRITICAL
    is_resolved       BOOLEAN DEFAULT false,
    resolution_notes  TEXT,
    resolved_at       TIMESTAMP WITH TIME ZONE,

    -- Metadata
    metadata          JSONB DEFAULT '{}',

    -- Timestamps
    occurred_at       TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_error_logs_error_type     ON error_logs(error_type);
CREATE INDEX idx_error_logs_service        ON error_logs(service);
CREATE INDEX idx_error_logs_severity       ON error_logs(severity);
CREATE INDEX idx_error_logs_is_resolved    ON error_logs(is_resolved);
CREATE INDEX idx_error_logs_occurred_at    ON error_logs(occurred_at DESC);
CREATE INDEX idx_error_logs_job_id         ON error_logs(job_id);
CREATE INDEX idx_error_logs_tenant_id      ON error_logs(tenant_id);
CREATE INDEX idx_error_logs_correlation    ON error_logs(correlation_id);


-- =============================================================================
-- VIEWS for monitoring dashboards
-- =============================================================================

-- Latest system health snapshot
CREATE OR REPLACE VIEW v_system_health_latest AS
SELECT DISTINCT ON (host)
    host,
    environment,
    cpu_percent,
    memory_percent,
    disk_percent,
    redis_healthy,
    rabbitmq_healthy,
    minio_healthy,
    supabase_healthy,
    keycloak_healthy,
    supabase_latency_ms,
    active_sessions,
    active_jobs,
    status,
    alerts,
    recorded_at
FROM system_health_logs
ORDER BY host, recorded_at DESC;


-- API request latency by endpoint (last 24h)
CREATE OR REPLACE VIEW v_api_latency_summary AS
SELECT
    path,
    method,
    COUNT(*)                                AS total_requests,
    COUNT(CASE WHEN status_code < 400 THEN 1 END) AS success_count,
    COUNT(CASE WHEN status_code >= 400 THEN 1 END) AS error_count,
    ROUND(AVG(duration_ms), 0)              AS avg_latency_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_latency_ms,
    MAX(duration_ms)                        AS max_latency_ms
FROM api_request_logs
WHERE request_at >= NOW() - INTERVAL '24 hours'
GROUP BY path, method
ORDER BY total_requests DESC;


-- Unresolved errors in last 7 days
CREATE OR REPLACE VIEW v_open_errors AS
SELECT
    el.id,
    el.error_type,
    el.error_message,
    el.service,
    el.severity,
    el.job_id,
    u.email     AS user_email,
    t.tenant_slug AS tenant,
    el.endpoint,
    el.occurred_at
FROM error_logs el
LEFT JOIN users   u ON el.user_id   = u.id
LEFT JOIN tenants t ON el.tenant_id = t.id
WHERE el.is_resolved = false
  AND el.occurred_at >= NOW() - INTERVAL '7 days'
ORDER BY el.occurred_at DESC;
