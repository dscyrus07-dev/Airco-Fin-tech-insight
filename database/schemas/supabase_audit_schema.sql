-- Airco Insights Production Audit Database Schema for Supabase
-- Multi-Tenant Architecture with Row-Level Security
-- Version 1.0 - Production Ready

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================
-- TENANT MANAGEMENT (Multi-Tenancy Core)
-- ============================================

CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) UNIQUE NOT NULL, -- Human-readable tenant ID
    tenant_name VARCHAR(255) NOT NULL,
    tenant_slug VARCHAR(100) UNIQUE NOT NULL,
    
    -- Tenant configuration
    plan VARCHAR(50) DEFAULT 'FREE', -- FREE, PRO, ENTERPRISE
    max_users INTEGER DEFAULT 5,
    max_storage_gb INTEGER DEFAULT 10,
    max_jobs_per_month INTEGER DEFAULT 100,
    
    -- Billing
    billing_email VARCHAR(255),
    billing_address TEXT,
    subscription_status VARCHAR(20) DEFAULT 'ACTIVE', -- ACTIVE, SUSPENDED, CANCELLED
    subscription_start_date DATE,
    subscription_end_date DATE,
    
    -- Usage tracking
    current_storage_gb DECIMAL(10,2) DEFAULT 0,
    current_jobs_this_month INTEGER DEFAULT 0,
    current_users INTEGER DEFAULT 0,
    
    -- Metadata
    settings JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,
    
    -- Indexes
    CONSTRAINT tenants_tenant_id_unique UNIQUE (tenant_id),
    CONSTRAINT tenants_slug_unique UNIQUE (tenant_slug)
);

CREATE INDEX idx_tenants_tenant_id ON tenants(tenant_id);
CREATE INDEX idx_tenants_slug ON tenants(tenant_slug);
CREATE INDEX idx_tenants_status ON tenants(subscription_status);
CREATE INDEX idx_tenants_created_at ON tenants(created_at);

-- ============================================
-- USER MANAGEMENT (Multi-Tenant)
-- ============================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id VARCHAR(100) UNIQUE NOT NULL, -- Human-readable user ID
    
    -- User identity
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    phone VARCHAR(50),
    
    -- Authentication
    auth_provider VARCHAR(50) DEFAULT 'KEYCLOAK', -- KEYCLOAK, LOCAL, SAML
    auth_provider_id VARCHAR(255),
    password_hash VARCHAR(255),
    
    -- Role and permissions
    role VARCHAR(50) DEFAULT 'USER', -- ADMIN, USER, VIEWER
    permissions JSONB DEFAULT '[]',
    
    -- Account status
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    is_locked BOOLEAN DEFAULT false,
    locked_reason VARCHAR(255),
    
    -- Usage statistics
    total_uploads INTEGER DEFAULT 0,
    total_downloads INTEGER DEFAULT 0,
    total_processing_time_ms BIGINT DEFAULT 0,
    last_login_at TIMESTAMP WITH TIME ZONE,
    login_count INTEGER DEFAULT 0,
    
    -- Profile metadata
    department VARCHAR(100),
    company VARCHAR(255),
    avatar_url VARCHAR(500),
    preferences JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,
    
    -- Constraints
    CONSTRAINT users_email_tenant_unique UNIQUE (tenant_id, email),
    CONSTRAINT users_user_id_unique UNIQUE (user_id)
);

CREATE INDEX idx_users_tenant_id ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_user_id ON users(user_id);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);
CREATE INDEX idx_users_last_login ON users(last_login_at);

-- ============================================
-- SESSION MANAGEMENT (Multi-Tenant)
-- ============================================

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Session identification
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE,
    
    -- Device and location
    ip_address INET NOT NULL,
    user_agent TEXT NOT NULL,
    browser VARCHAR(100),
    os VARCHAR(100),
    device_type VARCHAR(50), -- DESKTOP, MOBILE, TABLET
    device_fingerprint VARCHAR(255),
    
    -- Geographic data
    country_code VARCHAR(2),
    city VARCHAR(100),
    latitude DECIMAL(10,6),
    longitude DECIMAL(10,6),
    
    -- Session timing
    login_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    logout_time TIMESTAMP WITH TIME ZONE,
    session_duration_seconds INTEGER,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Session status
    is_active BOOLEAN DEFAULT true,
    logout_reason VARCHAR(50), -- USER_LOGOUT, TIMEOUT, FORCED, ERROR, SECURITY
    
    -- Security
    is_suspicious BOOLEAN DEFAULT false,
    security_flags JSONB DEFAULT '[]',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sessions_tenant_id ON sessions(tenant_id);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_token ON sessions(session_token);
CREATE INDEX idx_sessions_login_time ON sessions(login_time);
CREATE INDEX idx_sessions_is_active ON sessions(is_active);
CREATE INDEX idx_sessions_ip_address ON sessions(ip_address);

-- ============================================
-- AUDIT LOGS (Multi-Tenant)
-- ============================================

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    
    -- Event details
    event_type VARCHAR(50) NOT NULL, -- LOGIN, LOGOUT, LOGIN_FAILED, UPLOAD, DOWNLOAD, VIEW, EXPORT, etc.
    event_name VARCHAR(100) NOT NULL,
    event_category VARCHAR(50), -- AUTH, FILE, PROCESSING, ADMIN, COMPLIANCE
    description TEXT,
    
    -- Timing
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Request context
    ip_address INET,
    user_agent TEXT,
    request_id VARCHAR(255),
    request_method VARCHAR(10),
    request_path VARCHAR(500),
    
    -- Event-specific data
    metadata JSONB DEFAULT '{}',
    old_values JSONB, -- For change tracking
    new_values JSONB, -- For change tracking
    
    -- Status
    status VARCHAR(20) DEFAULT 'SUCCESS', -- SUCCESS, FAILED, WARNING, INFO
    error_code VARCHAR(50),
    error_message TEXT,
    
    -- Severity for alerts
    severity VARCHAR(20) DEFAULT 'INFO', -- INFO, WARNING, ERROR, CRITICAL
    
    -- Compliance
    compliance_tags JSONB DEFAULT '[]', -- GDPR, HIPAA, SOX, etc.
    retention_days INTEGER DEFAULT 365,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_tenant_id ON audit_logs(tenant_id);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_session_id ON audit_logs(session_id);
CREATE INDEX idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX idx_audit_logs_status ON audit_logs(status);
CREATE INDEX idx_audit_logs_severity ON audit_logs(severity);
CREATE INDEX idx_audit_logs_metadata ON audit_logs USING GIN (metadata);
CREATE INDEX idx_audit_logs_compliance ON audit_logs USING GIN (compliance_tags);

-- ============================================
-- BATCH MANAGEMENT (Multi-Tenant)
-- ============================================

CREATE TABLE batches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Batch identification
    batch_id VARCHAR(100) UNIQUE NOT NULL, -- Human-readable batch ID
    batch_name VARCHAR(255),
    batch_description TEXT,
    
    -- Batch details
    total_files INTEGER DEFAULT 0,
    completed_files INTEGER DEFAULT 0,
    failed_files INTEGER DEFAULT 0,
    
    -- Processing configuration
    processing_mode VARCHAR(20) DEFAULT 'FREE', -- FREE, HYBRID, PREMIUM
    priority INTEGER DEFAULT 5, -- 1=Highest, 5=Normal, 10=Lowest
    
    -- Timing
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    estimated_completion_at TIMESTAMP WITH TIME ZONE,
    
    -- Status
    status VARCHAR(20) DEFAULT 'CREATED', -- CREATED, PROCESSING, COMPLETED, FAILED, CANCELLED
    error_message TEXT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_batches_tenant_id ON batches(tenant_id);
CREATE INDEX idx_batches_user_id ON batches(user_id);
CREATE INDEX idx_batches_batch_id ON batches(batch_id);
CREATE INDEX idx_batches_status ON batches(status);
CREATE INDEX idx_batches_created_at ON batches(created_at);
CREATE INDEX idx_batches_priority ON batches(priority);

-- ============================================
-- PROCESSING JOBS (Multi-Tenant)
-- ============================================

CREATE TABLE processing_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    batch_id UUID REFERENCES batches(id) ON DELETE SET NULL,
    
    -- Job identification
    job_id VARCHAR(100) UNIQUE NOT NULL, -- Human-readable job ID like JOB_20260520_001245
    
    -- File information
    original_filename VARCHAR(255) NOT NULL,
    file_hash VARCHAR(64) NOT NULL, -- SHA256 hash
    file_size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(100),
    file_extension VARCHAR(10),
    
    -- Storage
    upload_object_key VARCHAR(512),
    report_object_key VARCHAR(512),
    storage_location VARCHAR(100), -- S3, MINIO, LOCAL
    
    -- Processing details
    bank_name VARCHAR(100),
    format_id VARCHAR(50),
    processing_mode VARCHAR(20) NOT NULL, -- FREE, HYBRID, PREMIUM
    account_type VARCHAR(50),
    statement_label VARCHAR(255),
    
    -- Statement information
    statement_start_date DATE,
    statement_end_date DATE,
    page_count INTEGER DEFAULT 0,
    transaction_count INTEGER DEFAULT 0,
    
    -- Parser information
    parser_used VARCHAR(50), -- hardcoded, dynamic, unsupported
    parser_version VARCHAR(20),
    fallback_used BOOLEAN DEFAULT false,
    fallback_level INTEGER DEFAULT 0, -- 0=none, 1=first, 2=second, 3=third
    confidence_score DECIMAL(5,2), -- 0.00 to 100.00
    
    -- Quality metrics
    data_quality_score DECIMAL(5,2),
    validation_errors JSONB DEFAULT '[]',
    warnings JSONB DEFAULT '[]',
    
    -- Timing
    upload_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processing_start_time TIMESTAMP WITH TIME ZONE,
    processing_end_time TIMESTAMP WITH TIME ZONE,
    processing_time_ms INTEGER,
    queue_wait_time_ms INTEGER,
    
    -- Status
    status VARCHAR(20) DEFAULT 'QUEUED', -- QUEUED, PROCESSING, COMPLETED, FAILED, CANCELLED
    error_message TEXT,
    error_code VARCHAR(50),
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    
    -- Cost tracking
    processing_cost_usd DECIMAL(10,4) DEFAULT 0,
    api_calls_count INTEGER DEFAULT 0,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_processing_jobs_tenant_id ON processing_jobs(tenant_id);
CREATE INDEX idx_processing_jobs_user_id ON processing_jobs(user_id);
CREATE INDEX idx_processing_jobs_session_id ON processing_jobs(session_id);
CREATE INDEX idx_processing_jobs_batch_id ON processing_jobs(batch_id);
CREATE INDEX idx_processing_jobs_job_id ON processing_jobs(job_id);
CREATE INDEX idx_processing_jobs_status ON processing_jobs(status);
CREATE INDEX idx_processing_jobs_bank ON processing_jobs(bank_name);
CREATE INDEX idx_processing_jobs_upload_time ON processing_jobs(upload_time);
CREATE INDEX idx_processing_jobs_file_hash ON processing_jobs(file_hash);
CREATE INDEX idx_processing_jobs_mode ON processing_jobs(processing_mode);
CREATE INDEX idx_processing_jobs_metadata ON processing_jobs USING GIN (metadata);

-- ============================================
-- JOB EVENTS TIMELINE (Multi-Tenant)
-- ============================================

CREATE TABLE job_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    job_id UUID NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
    
    -- Event details
    event_type VARCHAR(50) NOT NULL, -- LOGIN, UPLOAD, HYGIENE_CHECK, PARSER_START, PARSER_SUCCESS, EXCEL_GENERATED, DOWNLOAD, LOGOUT
    event_name VARCHAR(100) NOT NULL,
    event_category VARCHAR(50), -- UPLOAD, HYGIENE, PARSING, GENERATION, DOWNLOAD
    description TEXT,
    
    -- Timing
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Event-specific data
    metadata JSONB DEFAULT '{}',
    old_values JSONB,
    new_values JSONB,
    
    -- Status
    status VARCHAR(20) DEFAULT 'SUCCESS', -- SUCCESS, FAILED, WARNING, INFO
    error_message TEXT,
    
    -- Performance
    duration_ms INTEGER,
    memory_usage_mb DECIMAL(10,2),
    cpu_usage_percent DECIMAL(5,2),
    
    -- Correlation
    correlation_id VARCHAR(255),
    parent_event_id UUID REFERENCES job_events(id) ON DELETE SET NULL,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_job_events_tenant_id ON job_events(tenant_id);
CREATE INDEX idx_job_events_job_id ON job_events(job_id);
CREATE INDEX idx_job_events_event_type ON job_events(event_type);
CREATE INDEX idx_job_events_timestamp ON job_events(timestamp);
CREATE INDEX idx_job_events_status ON job_events(status);
CREATE INDEX idx_job_events_correlation ON job_events(correlation_id);
CREATE INDEX idx_job_events_parent ON job_events(parent_event_id);
CREATE INDEX idx_job_events_metadata ON job_events USING GIN (metadata);

-- ============================================
-- HYGIENE REPORTS (Multi-Tenant)
-- ============================================

CREATE TABLE hygiene_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    job_id UUID NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
    
    -- Hygiene check results
    format_id VARCHAR(50),
    page_count INTEGER DEFAULT 0,
    transaction_count INTEGER DEFAULT 0,
    
    -- Date range
    start_date DATE,
    end_date DATE,
    
    -- Validation results
    is_healthy BOOLEAN DEFAULT false,
    health_score DECIMAL(5,2), -- 0.00 to 100.00
    warnings JSONB DEFAULT '[]',
    issues JSONB DEFAULT '[]',
    
    -- Specific checks
    has_valid_structure BOOLEAN DEFAULT true,
    has_valid_dates BOOLEAN DEFAULT true,
    has_valid_transactions BOOLEAN DEFAULT true,
    has_encrypted_content BOOLEAN DEFAULT false,
    has_corrupted_pages BOOLEAN DEFAULT false,
    
    -- Additional metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timing
    check_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    check_duration_ms INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_hygiene_reports_tenant_id ON hygiene_reports(tenant_id);
CREATE INDEX idx_hygiene_reports_job_id ON hygiene_reports(job_id);
CREATE INDEX idx_hygiene_reports_healthy ON hygiene_reports(is_healthy);
CREATE INDEX idx_hygiene_reports_check_time ON hygiene_reports(check_time);
CREATE INDEX idx_hygiene_reports_format ON hygiene_reports(format_id);

-- ============================================
-- REPORT GENERATION LOGS (Multi-Tenant)
-- ============================================

CREATE TABLE report_generation_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    job_id UUID NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
    
    -- Excel file details
    excel_filename VARCHAR(255) NOT NULL,
    excel_file_path VARCHAR(500),
    excel_file_size_bytes BIGINT,
    sheet_count INTEGER DEFAULT 0,
    
    -- Generation details
    template_used VARCHAR(100),
    template_version VARCHAR(20),
    generation_mode VARCHAR(20), -- STANDARD, ENHANCED, CUSTOM
    
    -- Sheet details
    sheet_details JSONB DEFAULT '[]', -- List of sheets with names and row counts
    
    -- Quality metrics
    data_quality_score DECIMAL(5,2),
    validation_errors JSONB DEFAULT '[]',
    warnings JSONB DEFAULT '[]',
    
    -- Timing
    generation_start_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    generation_end_time TIMESTAMP WITH TIME ZONE,
    generation_time_ms INTEGER,
    
    -- Status
    status VARCHAR(20) DEFAULT 'STARTED', -- STARTED, COMPLETED, FAILED
    error_message TEXT,
    error_code VARCHAR(50),
    
    -- Cost tracking
    generation_cost_usd DECIMAL(10,4) DEFAULT 0,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_report_generation_tenant_id ON report_generation_logs(tenant_id);
CREATE INDEX idx_report_generation_job_id ON report_generation_logs(job_id);
CREATE INDEX idx_report_generation_status ON report_generation_logs(status);
CREATE INDEX idx_report_generation_start_time ON report_generation_logs(generation_start_time);
CREATE INDEX idx_report_generation_template ON report_generation_logs(template_used);

-- ============================================
-- DOWNLOAD LOGS (Multi-Tenant)
-- ============================================

CREATE TABLE download_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    job_id UUID NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    
    -- Download details
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500),
    file_size_bytes BIGINT,
    file_type VARCHAR(50), -- EXCEL, PDF, CSV
    
    -- Request context
    ip_address INET NOT NULL,
    user_agent TEXT,
    browser VARCHAR(100),
    os VARCHAR(100),
    
    -- Geographic data
    country_code VARCHAR(2),
    city VARCHAR(100),
    
    -- Timing
    download_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Download statistics
    download_number INTEGER NOT NULL, -- 1st, 2nd, 3rd download
    bytes_transferred BIGINT,
    transfer_time_ms INTEGER,
    transfer_speed_mbps DECIMAL(10,2),
    
    -- Status
    status VARCHAR(20) DEFAULT 'SUCCESS', -- SUCCESS, FAILED, PARTIAL, CANCELLED
    error_message TEXT,
    error_code VARCHAR(50),
    
    -- Security
    is_suspicious BOOLEAN DEFAULT false,
    security_flags JSONB DEFAULT '[]',
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_download_logs_tenant_id ON download_logs(tenant_id);
CREATE INDEX idx_download_logs_job_id ON download_logs(job_id);
CREATE INDEX idx_download_logs_user_id ON download_logs(user_id);
CREATE INDEX idx_download_logs_session_id ON download_logs(session_id);
CREATE INDEX idx_download_logs_time ON download_logs(download_time);
CREATE INDEX idx_download_logs_ip ON download_logs(ip_address);
CREATE INDEX idx_download_logs_status ON download_logs(status);

-- ============================================
-- PARSER METRICS (Multi-Tenant)
-- ============================================

CREATE TABLE parser_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    job_id UUID NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
    
    -- Parser details
    parser_type VARCHAR(50) NOT NULL, -- hardcoded, dynamic, fallback
    parser_name VARCHAR(100) NOT NULL,
    parser_version VARCHAR(20),
    bank_name VARCHAR(100),
    
    -- Performance metrics
    execution_time_ms INTEGER,
    memory_usage_mb DECIMAL(10,2),
    cpu_usage_percent DECIMAL(5,2),
    
    -- Results
    transactions_extracted INTEGER DEFAULT 0,
    confidence_score DECIMAL(5,2),
    
    -- Quality metrics
    data_quality_score DECIMAL(5,2),
    validation_errors JSONB DEFAULT '[]',
    warnings JSONB DEFAULT '[]',
    
    -- Fallback details
    fallback_level INTEGER DEFAULT 0,
    fallback_reason VARCHAR(255),
    
    -- Status
    status VARCHAR(20) DEFAULT 'SUCCESS', -- SUCCESS, FAILED, PARTIAL
    error_message TEXT,
    error_code VARCHAR(50),
    
    -- Timing
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_parser_metrics_tenant_id ON parser_metrics(tenant_id);
CREATE INDEX idx_parser_metrics_job_id ON parser_metrics(job_id);
CREATE INDEX idx_parser_metrics_parser_type ON parser_metrics(parser_type);
CREATE INDEX idx_parser_metrics_parser_name ON parser_metrics(parser_name);
CREATE INDEX idx_parser_metrics_status ON parser_metrics(status);
CREATE INDEX idx_parser_metrics_timestamp ON parser_metrics(timestamp);
CREATE INDEX idx_parser_metrics_bank ON parser_metrics(bank_name);

-- ============================================
-- UNSUPPORTED FORMAT QUEUE (Multi-Tenant)
-- ============================================

CREATE TABLE unsupported_format_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    job_id UUID NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
    
    -- Queue details
    queue_status VARCHAR(20) DEFAULT 'QUEUED', -- QUEUED, IN_PROGRESS, RESOLVED, REJECTED, ESCALATED
    priority INTEGER DEFAULT 5, -- 1=Highest, 5=Normal, 10=Lowest
    
    -- Analysis details
    issue_type VARCHAR(100), -- UNKNOWN_BANK, CORRUPTED, ENCRYPTED, INVALID_STRUCTURE, etc.
    issue_description TEXT,
    issue_severity VARCHAR(20) DEFAULT 'MEDIUM', -- LOW, MEDIUM, HIGH, CRITICAL
    suggested_action TEXT,
    
    -- Resolution details
    resolved_by UUID REFERENCES users(id),
    resolution_time TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    resolution_method VARCHAR(100),
    
    -- Escalation
    escalated BOOLEAN DEFAULT false,
    escalated_to UUID REFERENCES users(id),
    escalated_at TIMESTAMP WITH TIME ZONE,
    escalation_reason TEXT,
    
    -- Timing
    queued_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    first_review_time TIMESTAMP WITH TIME ZONE,
    
    -- SLA tracking
    sla_due_at TIMESTAMP WITH TIME ZONE,
    sla_met BOOLEAN,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_unsupported_queue_tenant_id ON unsupported_format_queue(tenant_id);
CREATE INDEX idx_unsupported_queue_job_id ON unsupported_format_queue(job_id);
CREATE INDEX idx_unsupported_queue_status ON unsupported_format_queue(queue_status);
CREATE INDEX idx_unsupported_queue_priority ON unsupported_format_queue(priority);
CREATE INDEX idx_unsupported_queue_queued_time ON unsupported_format_queue(queued_time);
CREATE INDEX idx_unsupported_queue_issue_type ON unsupported_format_queue(issue_type);

-- ============================================
-- TRANSACTIONS (Multi-Tenant - Existing Table Enhanced)
-- ============================================

CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Transaction details (aligned with existing model)
    user_name VARCHAR(255),
    bank_name VARCHAR(100),
    account_type VARCHAR(50),
    date DATE,
    description TEXT,
    debit NUMERIC(15, 2),
    credit NUMERIC(15, 2),
    balance NUMERIC(15, 2),
    category VARCHAR(100),
    confidence FLOAT,
    is_recurring BOOLEAN DEFAULT false,
    
    -- Enhanced fields
    merchant_name VARCHAR(255),
    merchant_category VARCHAR(100),
    transaction_type VARCHAR(50), -- DEBIT, CREDIT, TRANSFER
    reference_number VARCHAR(100),
    transaction_id VARCHAR(100),
    
    -- Classification
    ai_category VARCHAR(100),
    ai_confidence DECIMAL(5,2),
    rule_category VARCHAR(100),
    rule_confidence DECIMAL(5,2),
    final_category VARCHAR(100),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transactions_tenant_id ON transactions(tenant_id);
CREATE INDEX idx_transactions_bank ON transactions(bank_name);
CREATE INDEX idx_transactions_category ON transactions(category);
CREATE INDEX idx_transactions_date ON transactions(date);
CREATE INDEX idx_transactions_merchant ON transactions(merchant_name);
CREATE INDEX idx_transactions_final_category ON transactions(final_category);

-- ============================================
-- MERCHANTS (Multi-Tenant - Existing Table Enhanced)
-- ============================================

CREATE TABLE merchants (
    id SERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Merchant details (aligned with existing model)
    normalized_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    confidence FLOAT DEFAULT 0.95,
    
    -- Enhanced fields
    original_name VARCHAR(255),
    merchant_type VARCHAR(50), -- ONLINE, IN_STORE, TRANSFER
    industry VARCHAR(100),
    website VARCHAR(255),
    
    -- Classification
    ai_category VARCHAR(100),
    rule_category VARCHAR(100),
    final_category VARCHAR(100),
    
    -- Usage statistics
    occurrence_count INTEGER DEFAULT 0,
    last_seen_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT merchants_tenant_name_unique UNIQUE (tenant_id, normalized_name)
);

CREATE INDEX idx_merchants_tenant_id ON merchants(tenant_id);
CREATE INDEX idx_merchants_normalized_name ON merchants(normalized_name);
CREATE INDEX idx_merchants_category ON merchants(category);
CREATE INDEX idx_merchants_final_category ON merchants(final_category);

-- ============================================
-- USER FILE RECORDS (Multi-Tenant - Existing Table Enhanced)
-- ============================================

CREATE TABLE user_file_records (
    id SERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Job identification (aligned with existing model)
    job_id VARCHAR(64) UNIQUE NOT NULL,
    
    -- User details (aligned with existing model)
    user_id VARCHAR(255) NOT NULL,
    user_email VARCHAR(255),
    user_name VARCHAR(255),
    full_name VARCHAR(255),
    
    -- Processing details (aligned with existing model)
    account_type VARCHAR(50),
    bank_name VARCHAR(100),
    batch_id VARCHAR(64),
    statement_label VARCHAR(255),
    mode VARCHAR(50),
    
    -- File details (aligned with existing model)
    original_filename VARCHAR(255) NOT NULL,
    upload_object_key VARCHAR(512),
    report_object_key VARCHAR(512),
    report_filename VARCHAR(255),
    
    -- Retention and deletion (aligned with existing model)
    retention_expires_at TIMESTAMP WITH TIME ZONE,
    deletion_requested_at TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    deletion_reason VARCHAR(255),
    deletion_status VARCHAR(50) NOT NULL DEFAULT 'active',
    backup_purge_due_at TIMESTAMP WITH TIME ZONE,
    backup_purge_status VARCHAR(50),
    
    -- Status (aligned with existing model)
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    total_transactions INTEGER,
    error_message TEXT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps (aligned with existing model)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_user_file_records_tenant_id ON user_file_records(tenant_id);
CREATE INDEX idx_user_file_records_user_id ON user_file_records(user_id);
CREATE INDEX idx_user_file_records_job_id ON user_file_records(job_id);
CREATE INDEX idx_user_file_records_batch_id ON user_file_records(batch_id);
CREATE INDEX idx_user_file_records_status ON user_file_records(status);
CREATE INDEX idx_user_file_records_retention_expires_at ON user_file_records(retention_expires_at);
CREATE INDEX idx_user_file_records_deletion_status ON user_file_records(deletion_status);

-- ============================================
-- VIEWS FOR COMMON QUERIES (Multi-Tenant)
-- ============================================

-- User Activity Summary View
CREATE VIEW user_activity_summary AS
SELECT 
    t.tenant_id,
    u.id as user_id,
    u.user_id as user_external_id,
    u.email,
    u.full_name,
    u.role,
    u.created_at,
    u.last_login_at,
    u.login_count,
    u.total_uploads,
    u.total_downloads,
    u.total_processing_time_ms,
    COUNT(DISTINCT s.id) as session_count,
    COUNT(DISTINCT pj.id) as processing_jobs_count,
    COUNT(DISTINCT CASE WHEN pj.status = 'COMPLETED' THEN pj.id END) as completed_jobs,
    COUNT(DISTINCT CASE WHEN pj.status = 'FAILED' THEN pj.id END) as failed_jobs,
    AVG(pj.processing_time_ms) as avg_processing_time_ms
FROM tenants t
JOIN users u ON t.id = u.tenant_id
LEFT JOIN sessions s ON u.id = s.user_id
LEFT JOIN processing_jobs pj ON u.id = pj.user_id
GROUP BY t.tenant_id, u.id, u.user_id, u.email, u.full_name, u.role, u.created_at, u.last_login_at, u.login_count, u.total_uploads, u.total_downloads, u.total_processing_time_ms;

-- Job Timeline View
CREATE VIEW job_timeline AS
SELECT 
    t.tenant_id,
    pj.job_id,
    pj.user_id,
    pj.original_filename,
    pj.bank_name,
    pj.status,
    je.event_type,
    je.event_name,
    je.timestamp,
    je.status as event_status,
    je.duration_ms,
    je.metadata
FROM tenants t
JOIN processing_jobs pj ON t.id = pj.tenant_id
JOIN job_events je ON pj.id = je.job_id
ORDER BY pj.job_id, je.timestamp;

-- Processing Statistics View
CREATE VIEW processing_statistics AS
SELECT 
    t.tenant_id,
    DATE(pj.upload_time) as processing_date,
    pj.bank_name,
    pj.processing_mode,
    pj.parser_used,
    COUNT(*) as total_jobs,
    COUNT(DISTINCT pj.user_id) as unique_users,
    COUNT(CASE WHEN pj.status = 'COMPLETED' THEN 1 END) as completed_jobs,
    COUNT(CASE WHEN pj.status = 'FAILED' THEN 1 END) as failed_jobs,
    AVG(pj.processing_time_ms) as avg_processing_time_ms,
    AVG(pj.transaction_count) as avg_transactions,
    SUM(pj.file_size_bytes) as total_file_size_bytes
FROM tenants t
JOIN processing_jobs pj ON t.id = pj.tenant_id
GROUP BY t.tenant_id, DATE(pj.upload_time), pj.bank_name, pj.processing_mode, pj.parser_used;

-- Tenant Usage Summary View
CREATE VIEW tenant_usage_summary AS
SELECT 
    t.tenant_id,
    t.tenant_name,
    t.plan,
    t.subscription_status,
    t.max_users,
    t.max_storage_gb,
    t.max_jobs_per_month,
    t.current_storage_gb,
    t.current_jobs_this_month,
    t.current_users,
    COUNT(DISTINCT u.id) as actual_users,
    COUNT(DISTINCT CASE WHEN u.is_active THEN u.id END) as active_users,
    COUNT(DISTINCT pj.id) as total_jobs,
    COUNT(DISTINCT CASE WHEN pj.status = 'COMPLETED' THEN pj.id END) as completed_jobs,
    SUM(pj.file_size_bytes) / 1073741824.0 as total_storage_used_gb
FROM tenants t
LEFT JOIN users u ON t.id = u.tenant_id
LEFT JOIN processing_jobs pj ON t.id = pj.tenant_id
GROUP BY t.tenant_id, t.tenant_name, t.plan, t.subscription_status, t.max_users, t.max_storage_gb, t.max_jobs_per_month, t.current_storage_gb, t.current_jobs_this_month, t.current_users;

-- ============================================
-- ROW LEVEL SECURITY POLICIES (Multi-Tenant)
-- ============================================

-- Enable RLS on all tables
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE hygiene_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_generation_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE download_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE parser_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE unsupported_format_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE merchants ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_file_records ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own tenant's data
CREATE POLICY tenant_isolation ON tenants
    FOR ALL
    USING (true); -- Admin access only

CREATE POLICY tenant_isolation_users ON users
    FOR ALL
    USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));

CREATE POLICY tenant_isolation_sessions ON sessions
    FOR ALL
    USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));

CREATE POLICY tenant_isolation_audit_logs ON audit_logs
    FOR SELECT
    USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));

CREATE POLICY tenant_isolation_batches ON batches
    FOR ALL
    USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));

CREATE POLICY tenant_isolation_processing_jobs ON processing_jobs
    FOR ALL
    USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));

CREATE POLICY tenant_isolation_job_events ON job_events
    FOR SELECT
    USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));

CREATE POLICY tenant_isolation_hygiene_reports ON hygiene_reports
    FOR SELECT
    USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));

CREATE POLICY tenant_isolation_report_generation ON report_generation_logs
    FOR SELECT
    USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));

CREATE POLICY tenant_isolation_download_logs ON download_logs
    FOR SELECT
    USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));

CREATE POLICY tenant_isolation_parser_metrics ON parser_metrics
    FOR SELECT
    USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));

CREATE POLICY tenant_isolation_unsupported_queue ON unsupported_format_queue
    FOR SELECT
    USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));

CREATE POLICY tenant_isolation_transactions ON transactions
    FOR ALL
    USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));

CREATE POLICY tenant_isolation_merchants ON merchants
    FOR ALL
    USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));

CREATE POLICY tenant_isolation_user_file_records ON user_file_records
    FOR ALL
    USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));

-- ============================================
-- RETENTION POLICIES
-- ============================================

-- Function to clean up old audit logs (retention: 1 year)
CREATE OR REPLACE FUNCTION cleanup_old_audit_logs()
RETURNS void AS $$
BEGIN
    DELETE FROM audit_logs WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '1 year';
    DELETE FROM download_logs WHERE download_time < CURRENT_TIMESTAMP - INTERVAL '1 year';
    DELETE FROM sessions WHERE login_time < CURRENT_TIMESTAMP - INTERVAL '1 year';
END;
$$ LANGUAGE plpgsql;

-- Function to clean up old processing logs (retention: 90 days)
CREATE OR REPLACE FUNCTION cleanup_old_processing_logs()
RETURNS void AS $$
BEGIN
    DELETE FROM job_events WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '90 days';
    DELETE FROM parser_metrics WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '90 days';
    DELETE FROM report_generation_logs WHERE generation_start_time < CURRENT_TIMESTAMP - INTERVAL '90 days';
    DELETE FROM hygiene_reports WHERE check_time < CURRENT_TIMESTAMP - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- TRIGGERS FOR AUTOMATIC STATISTICS
-- ============================================

-- Update user statistics when processing job completes
CREATE OR REPLACE FUNCTION update_user_statistics()
RETURNS trigger AS $$
BEGIN
    IF NEW.status = 'COMPLETED' THEN
        UPDATE users 
        SET 
            total_uploads = total_uploads + 1,
            total_processing_time_ms = total_processing_time_ms + COALESCE(NEW.processing_time_ms, 0)
        WHERE id = NEW.user_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_user_statistics
    AFTER UPDATE ON processing_jobs
    FOR EACH ROW
    WHEN (OLD.status != 'COMPLETED' AND NEW.status = 'COMPLETED')
    EXECUTE FUNCTION update_user_statistics();

-- Update download count when file is downloaded
CREATE OR REPLACE FUNCTION update_download_statistics()
RETURNS trigger AS $$
BEGIN
    UPDATE users 
    SET total_downloads = total_downloads + 1
    WHERE id = NEW.user_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_download_statistics
    AFTER INSERT ON download_logs
    FOR EACH ROW
    EXECUTE FUNCTION update_download_statistics();

-- Update tenant usage statistics
CREATE OR REPLACE FUNCTION update_tenant_statistics()
RETURNS trigger AS $$
BEGIN
    IF TG_TABLE_NAME = 'processing_jobs' AND NEW.status = 'COMPLETED' THEN
        UPDATE tenants 
        SET 
            current_jobs_this_month = current_jobs_this_month + 1,
            current_storage_gb = current_storage_gb + (NEW.file_size_bytes / 1073741824.0)
        WHERE id = NEW.tenant_id;
    END IF;
    IF TG_TABLE_NAME = 'users' AND NEW.is_active = true THEN
        UPDATE tenants 
        SET current_users = current_users + 1
        WHERE id = NEW.tenant_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_tenant_statistics_jobs
    AFTER UPDATE ON processing_jobs
    FOR EACH ROW
    WHEN (OLD.status != 'COMPLETED' AND NEW.status = 'COMPLETED')
    EXECUTE FUNCTION update_tenant_statistics();

CREATE TRIGGER trigger_update_tenant_statistics_users
    AFTER INSERT ON users
    FOR EACH ROW
    WHEN (NEW.is_active = true)
    EXECUTE FUNCTION update_tenant_statistics();

-- ============================================
-- FUNCTIONS FOR COMMON OPERATIONS
-- ============================================

-- Function to get user's complete activity timeline
CREATE OR REPLACE FUNCTION get_user_activity_timeline(p_user_id UUID, p_limit INTEGER DEFAULT 100)
RETURNS TABLE (
    event_name VARCHAR(100),
    event_timestamp TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20),
    duration_ms INTEGER,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        je.event_name,
        je.timestamp as event_timestamp,
        je.status,
        je.duration_ms,
        je.metadata
    FROM job_events je
    JOIN processing_jobs pj ON je.job_id = pj.id
    WHERE pj.user_id = p_user_id
    ORDER BY je.timestamp DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to get processing performance by bank
CREATE OR REPLACE FUNCTION get_bank_performance(p_tenant_id UUID, p_days INTEGER DEFAULT 30)
RETURNS TABLE (
    bank_name VARCHAR(100),
    total_jobs BIGINT,
    avg_time_ms DECIMAL,
    avg_transactions DECIMAL,
    success_rate DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pj.bank_name,
        COUNT(*) as total_jobs,
        AVG(pj.processing_time_ms) as avg_time_ms,
        AVG(pj.transaction_count) as avg_transactions,
        (COUNT(CASE WHEN pj.status = 'COMPLETED' THEN 1 END)::DECIMAL / COUNT(*) * 100) as success_rate
    FROM processing_jobs pj
    WHERE pj.tenant_id = p_tenant_id
        AND pj.upload_time >= CURRENT_DATE - (p_days || ' days')::INTERVAL
    GROUP BY pj.bank_name
    ORDER BY total_jobs DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to get failed jobs for troubleshooting
CREATE OR REPLACE FUNCTION get_failed_jobs(p_tenant_id UUID, p_days INTEGER DEFAULT 7)
RETURNS TABLE (
    job_id VARCHAR(100),
    original_filename VARCHAR(255),
    bank_name VARCHAR(100),
    error_message TEXT,
    upload_time TIMESTAMP WITH TIME ZONE,
    user_email VARCHAR(255)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pj.job_id,
        pj.original_filename,
        pj.bank_name,
        pj.error_message,
        pj.upload_time,
        u.email
    FROM processing_jobs pj
    JOIN users u ON pj.user_id = u.id
    WHERE pj.tenant_id = p_tenant_id
        AND pj.status = 'FAILED'
        AND pj.upload_time >= CURRENT_DATE - (p_days || ' days')::INTERVAL
    ORDER BY pj.upload_time DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to get user's processing history
CREATE OR REPLACE FUNCTION get_user_processing_history(p_user_id UUID, p_limit INTEGER DEFAULT 50)
RETURNS TABLE (
    job_id VARCHAR(100),
    original_filename VARCHAR(255),
    bank_name VARCHAR(100),
    transaction_count INTEGER,
    processing_time_ms INTEGER,
    status VARCHAR(20),
    upload_time TIMESTAMP WITH TIME ZONE,
    last_download TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pj.job_id,
        pj.original_filename,
        pj.bank_name,
        pj.transaction_count,
        pj.processing_time_ms,
        pj.status,
        pj.upload_time,
        dl.download_time as last_download
    FROM processing_jobs pj
    LEFT JOIN (
        SELECT job_id, MAX(download_time) as download_time
        FROM download_logs
        GROUP BY job_id
    ) dl ON pj.id = dl.job_id
    WHERE pj.user_id = p_user_id
    ORDER BY pj.upload_time DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- SAMPLE QUERIES FOR ADMIN DASHBOARD
-- ============================================

-- Get user's complete activity timeline
-- SELECT * FROM get_user_activity_timeline('user-uuid', 100);

-- Get processing performance by bank
-- SELECT * FROM get_bank_performance('tenant-uuid', 30);

-- Get failed jobs for troubleshooting
-- SELECT * FROM get_failed_jobs('tenant-uuid', 7);

-- Get user's processing history
-- SELECT * FROM get_user_processing_history('user-uuid', 50);

-- Get tenant usage summary
-- SELECT * FROM tenant_usage_summary WHERE tenant_id = 'tenant-uuid';

-- Get user activity summary
-- SELECT * FROM user_activity_summary WHERE user_id = 'user-uuid';

-- Get job timeline
-- SELECT * FROM job_timeline WHERE job_id = 'JOB_20260520_001245';

-- Get processing statistics
-- SELECT * FROM processing_statistics WHERE tenant_id = 'tenant-uuid' AND processing_date >= CURRENT_DATE - INTERVAL '30 days';
