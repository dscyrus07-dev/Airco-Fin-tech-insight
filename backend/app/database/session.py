import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, declarative_base

from ..utils.logging import get_logger

logger = get_logger(__name__)
RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "7"))

raw_database_url = os.getenv("DATABASE_URL", "").strip()
if not raw_database_url:
    raise RuntimeError("DATABASE_URL environment variable is not set")
DATABASE_URL = raw_database_url

engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def _ensure_user_file_record_batch_columns() -> None:
    inspector = inspect(engine)
    if 'user_file_records' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('user_file_records')}

    statements = []
    if 'batch_id' not in columns:
        statements.append(
            "ALTER TABLE user_file_records ADD COLUMN batch_id VARCHAR(64)"
        )
    if 'statement_label' not in columns:
        statements.append(
            "ALTER TABLE user_file_records ADD COLUMN statement_label VARCHAR(255)"
        )
    if 'retention_expires_at' not in columns:
        statements.append(
            "ALTER TABLE user_file_records ADD COLUMN retention_expires_at TIMESTAMP"
        )
    if 'deletion_requested_at' not in columns:
        statements.append(
            "ALTER TABLE user_file_records ADD COLUMN deletion_requested_at TIMESTAMP"
        )
    if 'deleted_at' not in columns:
        statements.append(
            "ALTER TABLE user_file_records ADD COLUMN deleted_at TIMESTAMP"
        )
    if 'deletion_reason' not in columns:
        statements.append(
            "ALTER TABLE user_file_records ADD COLUMN deletion_reason VARCHAR(255)"
        )
    if 'deletion_status' not in columns:
        statements.append(
            "ALTER TABLE user_file_records ADD COLUMN deletion_status VARCHAR(50) DEFAULT 'active'"
        )
    if 'backup_purge_due_at' not in columns:
        statements.append(
            "ALTER TABLE user_file_records ADD COLUMN backup_purge_due_at TIMESTAMP"
        )
    if 'backup_purge_status' not in columns:
        statements.append(
            "ALTER TABLE user_file_records ADD COLUMN backup_purge_status VARCHAR(50)"
        )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def initialize_database() -> None:
    if DATABASE_URL.startswith("postgresql"):
        # Coordinate schema creation across multiple workers so Postgres DDL does not race.
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT pg_advisory_lock(hashtext('airco_schema_init'))"))
                try:
                    Base.metadata.create_all(bind=connection)
                    connection.execute(
                        text("ALTER TABLE user_file_records ADD COLUMN IF NOT EXISTS batch_id VARCHAR(64)")
                    )
                    connection.execute(
                        text("ALTER TABLE user_file_records ADD COLUMN IF NOT EXISTS statement_label VARCHAR(255)")
                    )
                    connection.execute(
                        text("ALTER TABLE user_file_records ADD COLUMN IF NOT EXISTS retention_expires_at TIMESTAMP")
                    )
                    connection.execute(
                        text("ALTER TABLE user_file_records ADD COLUMN IF NOT EXISTS deletion_requested_at TIMESTAMP")
                    )
                    connection.execute(
                        text("ALTER TABLE user_file_records ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP")
                    )
                    connection.execute(
                        text("ALTER TABLE user_file_records ADD COLUMN IF NOT EXISTS deletion_reason VARCHAR(255)")
                    )
                    connection.execute(
                        text("ALTER TABLE user_file_records ADD COLUMN IF NOT EXISTS deletion_status VARCHAR(50) DEFAULT 'active'")
                    )
                    connection.execute(
                        text("ALTER TABLE user_file_records ADD COLUMN IF NOT EXISTS backup_purge_due_at TIMESTAMP")
                    )
                    connection.execute(
                        text("ALTER TABLE user_file_records ADD COLUMN IF NOT EXISTS backup_purge_status VARCHAR(50)")
                    )
                    connection.execute(
                        text(
                            "UPDATE user_file_records "
                            f"SET retention_expires_at = created_at + INTERVAL '{RETENTION_DAYS} days' "
                            "WHERE retention_expires_at IS NULL AND created_at IS NOT NULL"
                        )
                    )
                    connection.execute(
                        text(
                            "UPDATE user_file_records "
                            "SET deletion_status = 'active' "
                            "WHERE deletion_status IS NULL"
                        )
                    )
                    connection.execute(
                        text(
                            "UPDATE user_file_records "
                            "SET backup_purge_due_at = retention_expires_at "
                            "WHERE backup_purge_due_at IS NULL AND retention_expires_at IS NOT NULL"
                        )
                    )
                    connection.execute(
                        text(
                            "UPDATE user_file_records "
                            "SET backup_purge_status = 'pending' "
                            "WHERE backup_purge_status IS NULL AND deleted_at IS NULL"
                        )
                    )
                    connection.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_user_file_records_user_created_at "
                            "ON user_file_records (user_id, created_at)"
                        )
                    )
                    connection.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_user_file_records_user_status "
                            "ON user_file_records (user_id, status)"
                        )
                    )
                    connection.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_user_file_records_user_batch_created_at "
                            "ON user_file_records (user_id, batch_id, created_at)"
                        )
                    )
                    connection.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_user_file_records_retention_expires_at "
                            "ON user_file_records (retention_expires_at)"
                        )
                    )
                    connection.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_user_file_records_deletion_status "
                            "ON user_file_records (deletion_status)"
                        )
                    )
                    connection.execute(
                        text(
                            "ALTER TABLE api_request_logs "
                            "ADD COLUMN IF NOT EXISTS api_key_id VARCHAR(255)"
                        )
                    )
                    connection.execute(
                        text(
                            "ALTER TABLE api_request_logs "
                            "ADD COLUMN IF NOT EXISTS auth_type VARCHAR(20)"
                        )
                    )
                    connection.execute(
                        text(
                            "ALTER TABLE api_keys "
                            "ADD COLUMN IF NOT EXISTS processed_pdf_count INTEGER DEFAULT 0"
                        )
                    )
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
                finally:
                    try:
                        connection.execute(text("SELECT pg_advisory_unlock(hashtext('airco_schema_init'))"))
                        connection.commit()
                    except Exception:
                        connection.rollback()
        except OperationalError as exc:
            logger.warning("Database unavailable; skipping schema initialization", error=str(exc))
            return
        except Exception:
            raise
        return

    Base.metadata.create_all(bind=engine)
    _ensure_user_file_record_batch_columns()
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE user_file_records "
                f"SET retention_expires_at = datetime(created_at, '+{RETENTION_DAYS} days') "
                "WHERE retention_expires_at IS NULL AND created_at IS NOT NULL"
            )
        )
        connection.execute(
            text(
                "UPDATE user_file_records "
                "SET deletion_status = 'active' "
                "WHERE deletion_status IS NULL"
            )
        )
        connection.execute(
            text(
                "UPDATE user_file_records "
                "SET backup_purge_due_at = retention_expires_at "
                "WHERE backup_purge_due_at IS NULL AND retention_expires_at IS NOT NULL"
            )
        )
        connection.execute(
            text(
                "UPDATE user_file_records "
                "SET backup_purge_status = 'pending' "
                "WHERE backup_purge_status IS NULL AND deleted_at IS NULL"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_user_file_records_user_created_at "
                "ON user_file_records (user_id, created_at)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_user_file_records_user_status "
                "ON user_file_records (user_id, status)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_user_file_records_user_batch_created_at "
                "ON user_file_records (user_id, batch_id, created_at)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_user_file_records_retention_expires_at "
                "ON user_file_records (retention_expires_at)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_user_file_records_deletion_status "
                "ON user_file_records (deletion_status)"
            )
        )
    


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
