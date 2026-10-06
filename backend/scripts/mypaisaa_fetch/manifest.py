"""Persistent SQLite manifest: restartable run state for users + statements.

Schema (all timestamps UTC ISO-8601):

users       user_id, api_status, statements_found, error_message,
            retry_count, attempts, created_at, updated_at
statements  user_id, statement_id, source_url, dedup_key, filename,
            local_path, statement_date, pulled_at, password_available,
            password, download_status, file_size, sha256, error_message,
            retry_count, created_at, updated_at
runs        started_at, finished_at, input_file, total_users

The database file lives inside the (gitignored) output directory. Statement
passwords are stored locally in this DB only so protected PDFs can be
processed; the file must never be committed or shared.
"""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id          TEXT PRIMARY KEY,
    api_status       TEXT NOT NULL DEFAULT 'pending',
    statements_found INTEGER NOT NULL DEFAULT 0,
    error_message    TEXT,
    retry_count      INTEGER NOT NULL DEFAULT 0,
    attempts         INTEGER NOT NULL DEFAULT 0,
    goalids          TEXT,
    ps_date          TEXT,
    ps_month         TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS statements (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           TEXT NOT NULL,
    statement_id      TEXT,
    source_url        TEXT,
    dedup_key         TEXT NOT NULL,
    statement_index   INTEGER,
    filename          TEXT,
    original_filename TEXT,
    local_path        TEXT,
    statement_date    TEXT,
    pulled_at         TEXT,
    bank_name         TEXT,
    account_type      TEXT,
    file_type         TEXT,
    password_available INTEGER NOT NULL DEFAULT 0,
    password_verified INTEGER,
    password          TEXT,
    download_status   TEXT NOT NULL DEFAULT 'pending',
    file_size         INTEGER,
    sha256            TEXT,
    error_message     TEXT,
    retry_count       INTEGER NOT NULL DEFAULT 0,
    api_fetched_at    TEXT,
    downloaded_at     TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    UNIQUE (user_id, dedup_key)
);

CREATE INDEX IF NOT EXISTS ix_statements_user ON statements (user_id);
CREATE INDEX IF NOT EXISTS ix_statements_status ON statements (download_status);
CREATE INDEX IF NOT EXISTS ix_statements_hash ON statements (user_id, sha256);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    input_file  TEXT,
    total_users INTEGER NOT NULL DEFAULT 0
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Manifest:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self):
        """Add columns introduced after a DB was created (older runs)."""
        for table, column, decl in [
            ("users", "ps_date", "TEXT"),
            ("users", "ps_month", "TEXT"),
            ("users", "goalids", "TEXT"),
            ("statements", "original_filename", "TEXT"),
            ("statements", "bank_name", "TEXT"),
            ("statements", "account_type", "TEXT"),
            ("statements", "statement_index", "INTEGER"),
            ("statements", "file_type", "TEXT"),
            ("statements", "password_verified", "INTEGER"),
            ("statements", "api_fetched_at", "TEXT"),
            ("statements", "downloaded_at", "TEXT"),
        ]:
            cols = {row[1] for row in self._conn.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        self._conn.commit()

    def close(self):
        self._conn.close()

    # -- runs ---------------------------------------------------------------
    def start_run(self, input_file: str, total_users: int) -> int:
        cur = self._conn.execute(
            "INSERT INTO runs (started_at, input_file, total_users) VALUES (?, ?, ?)",
            (_now(), input_file, total_users),
        )
        self._conn.commit()
        return cur.lastrowid

    def finish_run(self, run_id: int):
        self._conn.execute(
            "UPDATE runs SET finished_at = ? WHERE id = ?", (_now(), run_id)
        )
        self._conn.commit()

    # -- users --------------------------------------------------------------
    def upsert_user(self, user_id: str, **fields):
        existing = self.get_user(user_id)
        now = _now()
        if existing is None:
            row = {
                "user_id": user_id,
                "api_status": "pending",
                "statements_found": 0,
                "retry_count": 0,
                "attempts": 0,
                "created_at": now,
                "updated_at": now,
                **fields,
            }
            cols = ", ".join(row)
            marks = ", ".join("?" for _ in row)
            self._conn.execute(f"INSERT INTO users ({cols}) VALUES ({marks})", list(row.values()))
        else:
            updates = {**fields, "updated_at": now}
            sets = ", ".join(f"{key} = ?" for key in updates)
            self._conn.execute(
                f"UPDATE users SET {sets} WHERE user_id = ?",
                [*updates.values(), user_id],
            )
        self._conn.commit()

    def get_user(self, user_id: str) -> dict | None:
        cur = self._conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def user_ids_with_status(self, statuses: set[str]) -> set[str]:
        marks = ", ".join("?" for _ in statuses)
        cur = self._conn.execute(
            f"SELECT user_id FROM users WHERE api_status IN ({marks})", list(statuses)
        )
        return {row["user_id"] for row in cur.fetchall()}

    def all_user_ids(self) -> set[str]:
        cur = self._conn.execute("SELECT user_id FROM users")
        return {row["user_id"] for row in cur.fetchall()}

    # -- statements ---------------------------------------------------------
    def upsert_statement(self, user_id: str, dedup_key: str, **fields) -> int:
        """Insert or update a statement row; returns its row id."""
        now = _now()
        cur = self._conn.execute(
            "SELECT id FROM statements WHERE user_id = ? AND dedup_key = ?",
            (user_id, dedup_key),
        )
        existing = cur.fetchone()
        if existing is None:
            row = {
                "user_id": user_id,
                "statement_id": None,
                "source_url": None,
                "dedup_key": dedup_key,
                "statement_index": None,
                "filename": None,
                "original_filename": None,
                "local_path": None,
                "statement_date": None,
                "pulled_at": None,
                "bank_name": None,
                "account_type": None,
                "file_type": None,
                "password_available": 0,
                "password_verified": None,
                "password": None,
                "download_status": "pending",
                "file_size": None,
                "sha256": None,
                "error_message": None,
                "retry_count": 0,
                "api_fetched_at": None,
                "downloaded_at": None,
                "created_at": now,
                "updated_at": now,
                **fields,
            }
            cols = ", ".join(row)
            marks = ", ".join("?" for _ in row)
            cur = self._conn.execute(
                f"INSERT INTO statements ({cols}) VALUES ({marks})", list(row.values())
            )
            row_id = cur.lastrowid
        else:
            row_id = existing["id"]
            updates = {**fields, "updated_at": now}
            sets = ", ".join(f"{key} = ?" for key in updates)
            self._conn.execute(
                f"UPDATE statements SET {sets} WHERE id = ?", [*updates.values(), row_id]
            )
        self._conn.commit()
        return row_id

    def update_statement(self, row_id: int, **fields):
        updates = {**fields, "updated_at": _now()}
        sets = ", ".join(f"{key} = ?" for key in updates)
        self._conn.execute(
            f"UPDATE statements SET {sets} WHERE id = ?", [*updates.values(), row_id]
        )
        self._conn.commit()

    def get_statement(self, user_id: str, dedup_key: str) -> dict | None:
        cur = self._conn.execute(
            "SELECT * FROM statements WHERE user_id = ? AND dedup_key = ?",
            (user_id, dedup_key),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def statements_for_user(self, user_id: str) -> list[dict]:
        cur = self._conn.execute(
            "SELECT * FROM statements WHERE user_id = ? ORDER BY id", (user_id,)
        )
        return [dict(row) for row in cur.fetchall()]

    def find_hash_owner(self, user_id: str, sha256: str) -> dict | None:
        cur = self._conn.execute(
            "SELECT * FROM statements WHERE user_id = ? AND sha256 = ? LIMIT 1",
            (user_id, sha256),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def statements_with_status(self, statuses: set[str]) -> list[dict]:
        marks = ", ".join("?" for _ in statuses)
        cur = self._conn.execute(
            f"SELECT * FROM statements WHERE download_status IN ({marks}) ORDER BY user_id, id",
            list(statuses),
        )
        return [dict(row) for row in cur.fetchall()]

    # -- reporting ----------------------------------------------------------
    def export_csv(self, path: Path, include_password: bool = False):
        """Export the statements table as CSV.

        Passwords are excluded by default: CSV reports must not expose them.
        """
        cur = self._conn.execute("SELECT * FROM statements ORDER BY user_id, id")
        columns = [description[0] for description in cur.description]
        if not include_password:
            columns = [c for c in columns if c != "password"]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(columns)
            for row in cur.fetchall():
                writer.writerow([row[col] for col in columns])
