"""Final run reports: console summary, summary files and failure reports.

Reports generated after every run (inside the gitignored output directory):
- summary_<stamp>.txt   human-readable summary
- summary.json          machine-readable summary
- users_report.csv      one row per user (input metadata + api status)
- statements_report.csv one row per statement (no passwords)
- failed_users.csv      users whose API call failed
- failed_statements.csv statements that failed to download/verify
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import RunStats


def render_summary(stats: RunStats) -> str:
    def n(value: int) -> str:
        return f"{value:,}"

    return (
        "=================================================\n"
        "MYPAISAA BANK STATEMENT FETCH SUMMARY\n"
        "=================================================\n"
        "\n"
        f"Users received:             {n(stats.users_received)}\n"
        f"Users processed:            {n(stats.users_processed)}\n"
        f"Users skipped (done):       {n(stats.users_skipped)}\n"
        f"Users successful:           {n(stats.users_successful)}\n"
        f"Users with no statements:   {n(stats.users_no_statements)}\n"
        f"Users with errors:          {n(stats.users_with_errors)}\n"
        "\n"
        f"Statements discovered:      {n(stats.statements_discovered)}\n"
        f"Statements downloaded:      {n(stats.statements_downloaded)}\n"
        f"Duplicates skipped:         {n(stats.duplicates_skipped)}\n"
        f"Download failures:          {n(stats.download_failures)}\n"
        f"Invalid downloads:          {n(stats.invalid_downloads)}\n"
        f"Statements without URL:     {n(stats.no_url_statements)}\n"
        "\n"
        f"Password protected:         {n(stats.password_protected)}\n"
        f"Password failures:          {n(stats.password_failures)}\n"
        "================================================="
    )


def write_summary_file(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def write_summary_json(path: Path, stats: RunStats, stamp: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": stamp,
        "users": {
            "received": stats.users_received,
            "processed": stats.users_processed,
            "skipped_completed": stats.users_skipped,
            "successful": stats.users_successful,
            "no_statements": stats.users_no_statements,
            "with_errors": stats.users_with_errors,
        },
        "statements": {
            "discovered": stats.statements_discovered,
            "downloaded": stats.statements_downloaded,
            "duplicates_skipped": stats.duplicates_skipped,
            "download_failures": stats.download_failures,
            "invalid_downloads": stats.invalid_downloads,
            "without_url": stats.no_url_statements,
            "password_protected": stats.password_protected,
            "password_failures": stats.password_failures,
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_users_report(manifest, path: Path):
    """One row per user: input metadata + API/processing status."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = manifest._conn
    cur = conn.execute("SELECT * FROM users ORDER BY user_id")
    columns = [d[0] for d in cur.description]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for row in cur.fetchall():
            writer.writerow([row[col] for col in columns])


def write_failure_reports(
    output_dir: Path,
    failed_statements: list[dict],
    failed_users: list[dict],
    stamp: str,
):
    """CSV with one row per failed statement / failed user.

    Columns: user_id, statement_id, failure_reason, retry_count
    Passwords are never included.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    statements_path = output_dir / f"failed_statements_{stamp}.csv"
    with statements_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["user_id", "statement_id", "failure_reason", "retry_count"])
        for row in failed_statements:
            writer.writerow(
                [
                    row.get("user_id", ""),
                    row.get("statement_id") or "",
                    row.get("error_message") or row.get("download_status", ""),
                    row.get("retry_count", 0),
                ]
            )
    # Stable name pointing at the latest run's failures.
    (output_dir / "failed_statements.csv").write_text(
        statements_path.read_text(encoding="utf-8"), encoding="utf-8"
    )

    users_path = output_dir / f"failed_users_{stamp}.csv"
    with users_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["user_id", "failure_reason", "retry_count"])
        for row in failed_users:
            writer.writerow(
                [
                    row.get("user_id", ""),
                    row.get("error_message") or "api_error",
                    row.get("retry_count", 0),
                ]
            )
    (output_dir / "failed_users.csv").write_text(
        users_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
