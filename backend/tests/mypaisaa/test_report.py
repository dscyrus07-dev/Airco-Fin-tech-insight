"""Report tests: summary rendering and failure report contents."""

from __future__ import annotations

import csv
from pathlib import Path

from scripts.mypaisaa_fetch.models import RunStats
from scripts.mypaisaa_fetch.report import render_summary, write_failure_reports


def test_summary_format():
    stats = RunStats(
        users_received=500,
        users_processed=500,
        users_successful=482,
        users_no_statements=10,
        users_with_errors=18,
        statements_discovered=1284,
        statements_downloaded=1241,
        duplicates_skipped=31,
        download_failures=12,
        password_protected=87,
        password_failures=5,
    )
    text = render_summary(stats)
    assert "Users received:             500" in text
    assert "Users successful:           482" in text
    assert "Statements discovered:      1,284" in text
    assert "Statements downloaded:      1,241" in text
    assert "Duplicates skipped:         31" in text
    assert "Password protected:         87" in text
    assert text.startswith("=====")
    assert text.endswith("=================================================")


def test_failure_report_contents(tmp_path: Path):
    failed_statements = [
        {
            "user_id": "U1",
            "statement_id": "abc",
            "error_message": "provided password did not unlock the PDF",
            "retry_count": 2,
        },
        {"user_id": "U2", "statement_id": None, "error_message": "http 500", "retry_count": 3},
    ]
    failed_users = [{"user_id": "U3", "error_message": "transport error: ConnectError", "retry_count": 2}]
    write_failure_reports(tmp_path, failed_statements, failed_users, "STAMP")

    with (tmp_path / "failed_statements.csv").open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["user_id", "statement_id", "failure_reason", "retry_count"]
    assert rows[1] == ["U1", "abc", "provided password did not unlock the PDF", "2"]
    assert rows[2] == ["U2", "", "http 500", "3"]

    with (tmp_path / "failed_users.csv").open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["user_id", "failure_reason", "retry_count"]
    assert rows[1] == ["U3", "transport error: ConnectError", "2"]


def test_failure_report_no_password_leak(tmp_path: Path):
    # error messages must never contain the actual password value
    failed_statements = [
        {"user_id": "U1", "statement_id": "x", "error_message": "provided password did not unlock the PDF"}
    ]
    write_failure_reports(tmp_path, failed_statements, [], "STAMP")
    content = (tmp_path / "failed_statements.csv").read_text(encoding="utf-8")
    assert "secret123" not in content
