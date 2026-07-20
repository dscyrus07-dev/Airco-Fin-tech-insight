import uuid

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Date,
    Numeric,
    DateTime,
    Index,
    JSON,
    func,
    TypeDecorator,
    CHAR,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from .session import Base


class GUID(TypeDecorator):
    """Platform-independent UUID type (Postgres UUID, else CHAR(36))."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value) if not isinstance(value, uuid.UUID) else str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(Integer, primary_key=True, index=True)
    normalized_name = Column(String(255), unique=True, nullable=False)
    category = Column(String(100), nullable=False)
    confidence = Column(Float, default=0.95)
    created_at = Column(DateTime, server_default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_name = Column(String(255))
    bank_name = Column(String(100))
    account_type = Column(String(50))
    date = Column(Date)
    description = Column(String)
    debit = Column(Numeric(15, 2))
    credit = Column(Numeric(15, 2))
    balance = Column(Numeric(15, 2))
    category = Column(String(100))
    confidence = Column(Float)
    is_recurring = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class UserFileRecord(Base):
    __tablename__ = "user_file_records"
    __table_args__ = (
        Index("ix_user_file_records_user_created_at", "user_id", "created_at"),
        Index("ix_user_file_records_user_status", "user_id", "status"),
        Index("ix_user_file_records_retention_expires_at", "retention_expires_at"),
        Index("ix_user_file_records_deletion_status", "deletion_status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(String(255), index=True, nullable=False)
    api_key_id = Column(String(255), nullable=True, index=True)
    user_email = Column(String(255), nullable=True)
    user_name = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    account_type = Column(String(50), nullable=True)
    bank_name = Column(String(100), nullable=True)
    batch_id = Column(String(64), nullable=True, index=True)
    statement_label = Column(String(255), nullable=True)
    mode = Column(String(50), nullable=True)
    original_filename = Column(String(255), nullable=False)
    upload_object_key = Column(String(512), nullable=True)
    report_object_key = Column(String(512), nullable=True)
    report_filename = Column(String(255), nullable=True)
    retention_expires_at = Column(DateTime, nullable=True)
    deletion_requested_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    deletion_reason = Column(String(255), nullable=True)
    deletion_status = Column(String(50), nullable=False, default="active")
    backup_purge_due_at = Column(DateTime, nullable=True)
    backup_purge_status = Column(String(50), nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    total_transactions = Column(Integer, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime, nullable=True)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    owner_email = Column(String(255), nullable=True)
    owner_name = Column(String(255), nullable=True)
    tenant_id = Column(String(100), nullable=False, default="default")
    name = Column(String(255), nullable=False)
    key_prefix = Column(String(20), nullable=False, index=True)
    key_hash = Column(String(64), nullable=False, unique=True)
    scopes = Column(JSON, default=list)
    environment = Column(String(10), nullable=False, default="live")
    rate_limit_per_minute = Column(Integer, default=60)
    daily_quota = Column(Integer, nullable=True)
    usage_count = Column(Integer, default=0)
    processed_pdf_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, index=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    revoked_at = Column(DateTime, nullable=True)

