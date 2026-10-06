"""Data models for the MyPaisaa statement fetch pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InputUser:
    user_id: str
    source_row: int
    extra: dict = field(default_factory=dict)  # e.g. ps_date / ps_month from input


@dataclass
class InputValidation:
    users: list[InputUser] = field(default_factory=list)
    total_rows: int = 0
    blank_rows: int = 0
    duplicates: list[str] = field(default_factory=list)
    invalid: list[tuple[int, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.users)


@dataclass
class StatementRecord:
    """One statement entry discovered in an API response."""

    user_id: str
    statement_id: str | None = None
    source_url: str | None = None
    password: str | None = None
    filename_hint: str | None = None
    pulled_at: str | None = None
    statement_date: str | None = None
    bank_name: str | None = None
    account_type: str | None = None
    raw_index: int = 0

    @property
    def dedup_key(self) -> str:
        # Presigned URLs carry per-request signature params (ts, X-Amz-Date);
        # the path alone identifies the document stably across API calls.
        if self.source_url:
            return self.source_url.split("?", 1)[0]
        return f"{self.statement_id}|{self.filename_hint}"


# Statement-level statuses
ST_DOWNLOADED = "downloaded"
ST_DUPLICATE = "duplicate"
ST_PASSWORD_REQUIRED = "password_required"
ST_PASSWORD_INVALID = "password_invalid"
ST_DOWNLOAD_FAILED = "download_failed"
ST_DOWNLOAD_INVALID = "download_invalid"
ST_INVALID_URL = "invalid_url"
ST_NO_URL = "no_url"
ST_PENDING = "pending"

# Terminal statuses that do not need another attempt on a normal resume run.
TERMINAL_OK = {ST_DOWNLOADED, ST_DUPLICATE}
# Failed statuses that --retry-failed will reprocess.
RETRYABLE = {
    ST_PASSWORD_REQUIRED,
    ST_PASSWORD_INVALID,
    ST_DOWNLOAD_FAILED,
    ST_DOWNLOAD_INVALID,
    ST_INVALID_URL,
    ST_NO_URL,
    ST_PENDING,
}

# User-level statuses
US_SUCCESS = "success"
US_NO_STATEMENTS = "no_statements"
US_ERROR = "error"
US_PENDING = "pending"


@dataclass
class StatementOutcome:
    statement_id: str | None
    source_url: str | None
    filename: str | None
    status: str
    error: str | None = None
    retry_count: int = 0
    password_available: bool = False
    sha256: str | None = None
    file_type: str | None = None
    statement_index: int | None = None


@dataclass
class UserOutcome:
    user_id: str
    status: str
    statements_found: int = 0
    outcomes: list[StatementOutcome] = field(default_factory=list)
    error: str | None = None
    retry_count: int = 0
    skipped: bool = False


@dataclass
class RunStats:
    users_received: int = 0
    users_processed: int = 0
    users_skipped: int = 0
    users_successful: int = 0
    users_no_statements: int = 0
    users_with_errors: int = 0
    statements_discovered: int = 0
    statements_downloaded: int = 0
    duplicates_skipped: int = 0
    download_failures: int = 0
    invalid_downloads: int = 0
    no_url_statements: int = 0
    password_protected: int = 0
    password_failures: int = 0
    skipped_completed: int = 0
