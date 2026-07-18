"""
Supabase Audit Models - Multi-Tenant Audit System
Production-grade audit logging with tenant isolation
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, Date, Numeric, DateTime, Text, JSON, ForeignKey, Index, func, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from .session import Base
import uuid


# ============================================
# TENANT MANAGEMENT
# ============================================

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(100), unique=True, nullable=False, index=True)
    tenant_name = Column(String(255), nullable=False)
    tenant_slug = Column(String(100), unique=True, nullable=False, index=True)
    
    # Tenant configuration
    plan = Column(String(50), default='FREE')
    max_users = Column(Integer, default=5)
    max_storage_gb = Column(Integer, default=10)
    max_jobs_per_month = Column(Integer, default=100)
    
    # Billing
    billing_email = Column(String(255))
    billing_address = Column(Text)
    subscription_status = Column(String(20), default='ACTIVE', index=True)
    subscription_start_date = Column(Date)
    subscription_end_date = Column(Date)
    
    # Usage tracking
    current_storage_gb = Column(Float, default=0)
    current_jobs_this_month = Column(Integer, default=0)
    current_users = Column(Integer, default=0)
    
    # Metadata
    settings = Column(JSONB, default={})
    extra_data = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


# ============================================
# USER MANAGEMENT
# ============================================

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String(100), unique=True, nullable=False, index=True)
    
    # User identity
    email = Column(String(255), nullable=False)
    full_name = Column(String(255))
    phone = Column(String(50))
    
    # Authentication
    auth_provider = Column(String(50), default='KEYCLOAK')
    auth_provider_id = Column(String(255))
    password_hash = Column(String(255))
    
    # Role and permissions
    role = Column(String(50), default='USER', index=True)
    permissions = Column(JSONB, default=[])
    
    # Account status
    is_active = Column(Boolean, default=True, index=True)
    is_verified = Column(Boolean, default=False)
    is_locked = Column(Boolean, default=False)
    locked_reason = Column(String(255))
    
    # Usage statistics
    total_uploads = Column(Integer, default=0)
    total_downloads = Column(Integer, default=0)
    total_processing_time_ms = Column(BigInteger, default=0)
    last_login_at = Column(DateTime(timezone=True), index=True)
    login_count = Column(Integer, default=0)
    
    # Profile metadata
    department = Column(String(100))
    company = Column(String(255))
    avatar_url = Column(String(500))
    preferences = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))
    
    # Relationships
    tenant = relationship("Tenant", backref="users")


# ============================================
# SESSION MANAGEMENT
# ============================================

class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Session identification
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token = Column(String(255), unique=True)
    
    # Device and location
    ip_address = Column(INET, nullable=False, index=True)
    user_agent = Column(Text, nullable=False)
    browser = Column(String(100))
    os = Column(String(100))
    device_type = Column(String(50))
    device_fingerprint = Column(String(255))
    
    # Geographic data
    country_code = Column(String(2))
    city = Column(String(100))
    latitude = Column(Numeric(10, 6))
    longitude = Column(Numeric(10, 6))
    
    # Session timing
    login_time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    logout_time = Column(DateTime(timezone=True))
    session_duration_seconds = Column(Integer)
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
    
    # Session status
    is_active = Column(Boolean, default=True, index=True)
    logout_reason = Column(String(50))
    
    # Security
    is_suspicious = Column(Boolean, default=False)
    security_flags = Column(JSONB, default=[])
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    tenant = relationship("Tenant", backref="sessions")
    user = relationship("User", backref="sessions")


# ============================================
# AUDIT LOGS
# ============================================

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey('sessions.id', ondelete='SET NULL'), index=True)
    
    # Event details
    event_type = Column(String(50), nullable=False, index=True)
    event_name = Column(String(100), nullable=False)
    event_category = Column(String(50))
    description = Column(Text)
    
    # Timing
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Request context
    ip_address = Column(INET)
    user_agent = Column(Text)
    request_id = Column(String(255))
    request_method = Column(String(10))
    request_path = Column(String(500))
    
    # Event-specific data
    extra_data = Column(JSONB, default={})
    old_values = Column(JSONB)
    new_values = Column(JSONB)
    
    # Status
    status = Column(String(20), default='SUCCESS', index=True)
    error_code = Column(String(50))
    error_message = Column(Text)
    
    # Severity for alerts
    severity = Column(String(20), default='INFO', index=True)
    
    # Compliance
    compliance_tags = Column(JSONB, default=[])
    retention_days = Column(Integer, default=365)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    tenant = relationship("Tenant", backref="audit_logs")
    user = relationship("User", backref="audit_logs")
    session = relationship("Session", backref="audit_logs")


# ============================================
# BATCH MANAGEMENT
# ============================================

class Batch(Base):
    __tablename__ = "batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Batch identification
    batch_id = Column(String(100), unique=True, nullable=False, index=True)
    batch_name = Column(String(255))
    batch_description = Column(Text)
    
    # Batch details
    total_files = Column(Integer, default=0)
    completed_files = Column(Integer, default=0)
    failed_files = Column(Integer, default=0)
    
    # Processing configuration
    processing_mode = Column(String(20), default='FREE')
    priority = Column(Integer, default=5, index=True)
    
    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    estimated_completion_at = Column(DateTime(timezone=True))
    
    # Status
    status = Column(String(20), default='CREATED', index=True)
    error_message = Column(Text)
    
    # Metadata
    extra_data = Column(JSONB, default={})
    
    # Timestamps
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    tenant = relationship("Tenant", backref="batches")
    user = relationship("User", backref="batches")


# ============================================
# PROCESSING JOBS
# ============================================

class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey('sessions.id', ondelete='SET NULL'), index=True)
    batch_id = Column(UUID(as_uuid=True), ForeignKey('batches.id', ondelete='SET NULL'), index=True)
    
    # Job identification
    job_id = Column(String(100), unique=True, nullable=False, index=True)
    
    # File information
    original_filename = Column(String(255), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)
    file_size_bytes = Column(BigInteger, nullable=False)
    mime_type = Column(String(100))
    file_extension = Column(String(10))
    
    # Storage
    upload_object_key = Column(String(512))
    report_object_key = Column(String(512))
    storage_location = Column(String(100))
    
    # Processing details
    bank_name = Column(String(100), index=True)
    format_id = Column(String(50))
    processing_mode = Column(String(20), nullable=False, index=True)
    account_type = Column(String(50))
    statement_label = Column(String(255))
    
    # Statement information
    statement_start_date = Column(Date)
    statement_end_date = Column(Date)
    page_count = Column(Integer, default=0)
    transaction_count = Column(Integer, default=0)
    
    # Parser information
    parser_used = Column(String(50))
    parser_version = Column(String(20))
    fallback_used = Column(Boolean, default=False)
    fallback_level = Column(Integer, default=0)
    confidence_score = Column(Numeric(5, 2))
    
    # Quality metrics
    data_quality_score = Column(Numeric(5, 2))
    validation_errors = Column(JSONB, default=[])
    warnings = Column(JSONB, default=[])
    
    # Timing
    upload_time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    processing_start_time = Column(DateTime(timezone=True))
    processing_end_time = Column(DateTime(timezone=True))
    processing_time_ms = Column(Integer)
    queue_wait_time_ms = Column(Integer)
    
    # Status
    status = Column(String(20), default='QUEUED', index=True)
    error_message = Column(Text)
    error_code = Column(String(50))
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Cost tracking
    processing_cost_usd = Column(Numeric(10, 4), default=0)
    api_calls_count = Column(Integer, default=0)
    
    # Metadata
    extra_data = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    tenant = relationship("Tenant", backref="processing_jobs")
    user = relationship("User", backref="processing_jobs")
    session = relationship("Session", backref="processing_jobs")
    batch = relationship("Batch", backref="processing_jobs")


# ============================================
# JOB EVENTS TIMELINE
# ============================================

class JobEvent(Base):
    __tablename__ = "job_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('processing_jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Event details
    event_type = Column(String(50), nullable=False, index=True)
    event_name = Column(String(100), nullable=False)
    event_category = Column(String(50))
    description = Column(Text)
    
    # Timing
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Event-specific data
    extra_data = Column(JSONB, default={})
    old_values = Column(JSONB)
    new_values = Column(JSONB)
    
    # Status
    status = Column(String(20), default='SUCCESS', index=True)
    error_message = Column(Text)
    
    # Performance
    duration_ms = Column(Integer)
    memory_usage_mb = Column(Numeric(10, 2))
    cpu_usage_percent = Column(Numeric(5, 2))
    
    # Correlation
    correlation_id = Column(String(255), index=True)
    parent_event_id = Column(UUID(as_uuid=True), ForeignKey('job_events.id', ondelete='SET NULL'))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    tenant = relationship("Tenant", backref="job_events")
    job = relationship("ProcessingJob", backref="job_events")
    parent_event = relationship("JobEvent", remote_side=[id], backref="child_events")


# ============================================
# HYGIENE REPORTS
# ============================================

class HygieneReport(Base):
    __tablename__ = "hygiene_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('processing_jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # File identification
    file_name = Column(String(512))
    bank_name = Column(String(100), index=True)
    user_id = Column(String(255), index=True)
    goal_id = Column(String(255))

    # Hygiene check results
    format_id = Column(String(50), index=True)
    page_count = Column(Integer, default=0)
    transaction_count = Column(Integer, default=0)
    
    # Date range
    start_date = Column(Date)
    end_date = Column(Date)
    
    # Validation results
    is_healthy = Column(Boolean, default=False, index=True)
    health_score = Column(Numeric(5, 2))
    warnings = Column(JSONB, default=[])
    issues = Column(JSONB, default=[])
    
    # Specific checks
    has_valid_structure = Column(Boolean, default=True)
    has_valid_dates = Column(Boolean, default=True)
    has_valid_transactions = Column(Boolean, default=True)
    has_encrypted_content = Column(Boolean, default=False)
    has_corrupted_pages = Column(Boolean, default=False)
    
    # Additional metadata
    extra_data = Column(JSONB, default={})
    
    # Timing
    check_time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    check_duration_ms = Column(Integer)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    tenant = relationship("Tenant", backref="hygiene_reports")
    job = relationship("ProcessingJob", backref="hygiene_reports")


# ============================================
# REPORT GENERATION LOGS
# ============================================

class ReportGenerationLog(Base):
    __tablename__ = "report_generation_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('processing_jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Excel file details
    excel_filename = Column(String(255), nullable=False)
    excel_file_path = Column(String(500))
    excel_file_size_bytes = Column(BigInteger)
    sheet_count = Column(Integer, default=0)
    
    # Generation details
    template_used = Column(String(100), index=True)
    template_version = Column(String(20))
    generation_mode = Column(String(20))
    
    # Sheet details
    sheet_details = Column(JSONB, default=[])
    
    # Quality metrics
    data_quality_score = Column(Numeric(5, 2))
    validation_errors = Column(JSONB, default=[])
    warnings = Column(JSONB, default=[])
    
    # Timing
    generation_start_time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    generation_end_time = Column(DateTime(timezone=True))
    generation_time_ms = Column(Integer)
    
    # Status
    status = Column(String(20), default='STARTED', index=True)
    error_message = Column(Text)
    error_code = Column(String(50))
    
    # Cost tracking
    generation_cost_usd = Column(Numeric(10, 4), default=0)
    
    # Metadata
    extra_data = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    tenant = relationship("Tenant", backref="report_generation_logs")
    job = relationship("ProcessingJob", backref="report_generation_logs")


# ============================================
# DOWNLOAD LOGS
# ============================================

class DownloadLog(Base):
    __tablename__ = "download_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('processing_jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey('sessions.id', ondelete='SET NULL'), index=True)
    
    # Download details
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500))
    file_size_bytes = Column(BigInteger)
    file_type = Column(String(50))
    
    # Request context
    ip_address = Column(INET, nullable=False, index=True)
    user_agent = Column(Text)
    browser = Column(String(100))
    os = Column(String(100))
    
    # Geographic data
    country_code = Column(String(2))
    city = Column(String(100))
    
    # Timing
    download_time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Download statistics
    download_number = Column(Integer, nullable=False)
    bytes_transferred = Column(BigInteger)
    transfer_time_ms = Column(Integer)
    transfer_speed_mbps = Column(Numeric(10, 2))
    
    # Status
    status = Column(String(20), default='SUCCESS', index=True)
    error_message = Column(Text)
    error_code = Column(String(50))
    
    # Security
    is_suspicious = Column(Boolean, default=False)
    security_flags = Column(JSONB, default=[])
    
    # Metadata
    extra_data = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    tenant = relationship("Tenant", backref="download_logs")
    job = relationship("ProcessingJob", backref="download_logs")
    user = relationship("User", backref="download_logs")
    session = relationship("Session", backref="download_logs")


# ============================================
# PARSER METRICS
# ============================================

class ParserMetric(Base):
    __tablename__ = "parser_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('processing_jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Parser details
    parser_type = Column(String(50), nullable=False, index=True)
    parser_name = Column(String(100), nullable=False)
    parser_version = Column(String(20))
    bank_name = Column(String(100), index=True)
    
    # Performance metrics
    execution_time_ms = Column(Integer)
    memory_usage_mb = Column(Numeric(10, 2))
    cpu_usage_percent = Column(Numeric(5, 2))
    
    # Results
    transactions_extracted = Column(Integer, default=0)
    confidence_score = Column(Numeric(5, 2))
    
    # Quality metrics
    data_quality_score = Column(Numeric(5, 2))
    validation_errors = Column(JSONB, default=[])
    warnings = Column(JSONB, default=[])
    
    # Fallback details
    fallback_level = Column(Integer, default=0)
    fallback_reason = Column(String(255))
    
    # Status
    status = Column(String(20), default='SUCCESS', index=True)
    error_message = Column(Text)
    error_code = Column(String(50))
    
    # Timing
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Metadata
    extra_data = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    tenant = relationship("Tenant", backref="parser_metrics")
    job = relationship("ProcessingJob", backref="parser_metrics")


# ============================================
# STATEMENT METADATA  (one row per processed statement)
# ============================================

class StatementMetadata(Base):
    __tablename__ = "statement_metadata"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    job_id = Column(String(64), nullable=False, unique=True, index=True)

    # Header (chitid = job_id surrogate for external API consumers)
    chitid = Column(String(100), index=True)
    filename = Column(String(500))
    bankname = Column(String(100), index=True)
    accountno = Column(String(50), index=True)  # masked
    formatidentify = Column(String(100), index=True)
    startdate = Column(Date)
    enddate = Column(Date)
    nooftransactions = Column(Integer, default=0)

    # Salary
    havesalary = Column(Boolean, default=False, index=True)
    noofsalarycredit = Column(Integer, default=0)
    amtofsalarycredit = Column(Numeric(18, 2), default=0)

    # Loan repayment (debit side)
    hasloanrepayment = Column(Boolean, default=False, index=True)
    noofloanrepayments = Column(Integer, default=0)
    amtofloanrepayments = Column(Numeric(18, 2), default=0)

    # Loan credit (disbursement)
    loancredit = Column(Boolean, default=False, index=True)
    noofloancredits = Column(Integer, default=0)
    amtofloancredits = Column(Numeric(18, 2), default=0)

    # Credit aggregates
    noofcredits = Column(Integer, default=0)
    amtofcredits = Column(Numeric(18, 2), default=0)
    noofcashdeposits = Column(Integer, default=0)
    amtofcashdeposits = Column(Numeric(18, 2), default=0)
    noofupicredits = Column(Integer, default=0)
    amtofupicredits = Column(Numeric(18, 2), default=0)
    noofneft_imps_credits = Column(Integer, default=0)
    amtofneft_imps_credits = Column(Numeric(18, 2), default=0)
    noofnetbanking_credits = Column(Integer, default=0)
    amtofnetbanking_credits = Column(Numeric(18, 2), default=0)

    # Debit aggregates
    noofdebits = Column(Integer, default=0)
    amtofdebits = Column(Numeric(18, 2), default=0)
    noofcashwithdrawals = Column(Integer, default=0)
    amtofcashwithdrawals = Column(Numeric(18, 2), default=0)
    noofupidebits = Column(Integer, default=0)
    amtofupidebits = Column(Numeric(18, 2), default=0)
    noofneft_imps_debits = Column(Integer, default=0)
    amtofneft_imps_debits = Column(Numeric(18, 2), default=0)
    noofnetbanking_debits = Column(Integer, default=0)
    amtofnetbanking_debits = Column(Numeric(18, 2), default=0)

    # Free-form extras (e.g. salary recurrence stats)
    extra = Column(JSONB, default={})

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tenant = relationship("Tenant", backref="statement_metadata")
    user = relationship("User", backref="statement_metadata")


# ============================================
# UNSUPPORTED FORMAT QUEUE
# ============================================

class UnsupportedFormatQueue(Base):
    __tablename__ = "unsupported_format_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('processing_jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Queue details
    queue_status = Column(String(20), default='QUEUED', index=True)
    priority = Column(Integer, default=5, index=True)
    
    # Analysis details
    issue_type = Column(String(100), index=True)
    issue_description = Column(Text)
    issue_severity = Column(String(20), default='MEDIUM')
    suggested_action = Column(Text)
    
    # Resolution details
    resolved_by = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    resolution_time = Column(DateTime(timezone=True))
    resolution_notes = Column(Text)
    resolution_method = Column(String(100))
    
    # Escalation
    escalated = Column(Boolean, default=False)
    escalated_to = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    escalated_at = Column(DateTime(timezone=True))
    escalation_reason = Column(Text)
    
    # Timing
    queued_time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    first_review_time = Column(DateTime(timezone=True))
    
    # SLA tracking
    sla_due_at = Column(DateTime(timezone=True))
    sla_met = Column(Boolean)
    
    # Metadata
    extra_data = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    tenant = relationship("Tenant", backref="unsupported_format_queue")
    job = relationship("ProcessingJob", backref="unsupported_format_queue")
    resolver = relationship("User", foreign_keys=[resolved_by], backref="resolved_issues")
    escalator = relationship("User", foreign_keys=[escalated_to], backref="escalated_issues")


# ============================================
# SYSTEM HEALTH LOGS
# ============================================

class SystemHealthLog(Base):
    __tablename__ = "system_health_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    host = Column(String(100), nullable=False)
    environment = Column(String(20), default='PRODUCTION')

    cpu_percent = Column(Numeric(5, 2))
    memory_percent = Column(Numeric(5, 2))
    memory_used_mb = Column(Integer)
    memory_total_mb = Column(Integer)
    disk_percent = Column(Numeric(5, 2))
    disk_used_gb = Column(Numeric(10, 2))
    disk_total_gb = Column(Numeric(10, 2))

    redis_healthy = Column(Boolean)
    rabbitmq_healthy = Column(Boolean)
    minio_healthy = Column(Boolean)
    supabase_healthy = Column(Boolean)
    keycloak_healthy = Column(Boolean)

    redis_latency_ms = Column(Integer)
    rabbitmq_latency_ms = Column(Integer)
    minio_latency_ms = Column(Integer)
    supabase_latency_ms = Column(Integer)
    keycloak_latency_ms = Column(Integer)

    rabbitmq_ready_messages = Column(Integer)
    rabbitmq_unacked_messages = Column(Integer)

    active_sessions = Column(Integer)
    active_jobs = Column(Integer)

    status = Column(String(20), default='HEALTHY', index=True)
    alerts = Column(JSONB, default=[])

    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================
# API REQUEST LOGS
# ============================================

class ApiRequestLog(Base):
    __tablename__ = "api_request_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    request_id = Column(String(255), index=True)
    correlation_id = Column(String(255), index=True)

    method = Column(String(10), nullable=False)
    path = Column(String(500), nullable=False, index=True)
    status_code = Column(Integer, nullable=False, index=True)

    duration_ms = Column(Integer)
    request_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='SET NULL'), index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey('sessions.id', ondelete='SET NULL'), index=True)
    ip_address = Column(INET)
    user_agent = Column(Text)

    request_size_bytes = Column(Integer)
    response_size_bytes = Column(Integer)
    query_params = Column(JSONB, default={})

    api_key_id = Column(String(255), nullable=True, index=True)
    auth_type = Column(String(20), nullable=True)

    error_message = Column(Text)
    error_code = Column(String(50))

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================
# ERROR LOGS
# ============================================

class ErrorLog(Base):
    __tablename__ = "error_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    error_code = Column(String(100))
    error_type = Column(String(100), nullable=False)
    error_message = Column(Text, nullable=False)
    traceback = Column(Text)

    service = Column(String(100), index=True)
    module = Column(String(255))
    function_name = Column(String(255))
    line_number = Column(Integer)

    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='SET NULL'), index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey('sessions.id', ondelete='SET NULL'), index=True)
    job_id = Column(String(100), index=True)
    request_id = Column(String(255))
    correlation_id = Column(String(255), index=True)

    endpoint = Column(String(500))
    method = Column(String(10))
    ip_address = Column(INET)

    severity = Column(String(20), default='ERROR', index=True)
    is_resolved = Column(Boolean, default=False, index=True)
    resolution_notes = Column(Text)
    resolved_at = Column(DateTime(timezone=True))

    extra_data = Column(JSONB, default={})

    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================
# RAW TRANSACTIONS
# ============================================

class RawTransaction(Base):
    __tablename__ = "raw_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey('processing_jobs.id', ondelete='CASCADE'), nullable=False, index=True)

    raw_json = Column(JSONB, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
