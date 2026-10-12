"""Wave11 T2: statement_engine persisted with the job and returned from history.

Covers the fallback (no-DB) path: mark_completed stores the block, and the
entry payloads for uploads/reports carry it as an additive key. Old records
without the block return None so the UI renders exactly as before.
"""
import os
import sys
from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.file_history_service import FileHistoryService  # noqa: E402

ENGINE_BLOCK = {
    "engine": "legacy",
    "mode": "serve",
    "layout_id": None,
    "verdict": None,
    "needs_review": True,
    "review_codes": ["BANK_MISMATCH"],
    "anchored": False,
    "detected_bank": {"key": "hdfc", "name": "HDFC Bank", "confidence": "HIGH", "source": "detector"},
    "advisory": None,
}


class _OfflineSession:
    """DB session stub: every query/close raises/nops like a dead database."""

    def __init__(self):
        self._err = OperationalError("SELECT 1", {}, Exception("no db"))

    def query(self, *a, **k):
        raise self._err

    def close(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass


def _offline(svc):
    """Force the OperationalError fallback for all SessionLocal() calls."""
    return patch(
        "app.services.file_history_service.SessionLocal",
        side_effect=lambda *a, **k: _OfflineSession(),
    )


@pytest.fixture()
def svc():
    s = FileHistoryService()
    with _offline(s):
        s.upsert_upload(
            job_id="job-eng-1",
            user_id="u1",
            user_email=None,
            user_name=None,
            full_name=None,
            account_type=None,
            bank_name="ICICI Bank",
            batch_id=None,
            statement_label=None,
            mode=None,
            original_filename="statement.pdf",
            upload_object_key=None,
        )
        s.upsert_upload(
            job_id="job-old-1",
            user_id="u1",
            user_email=None,
            user_name=None,
            full_name=None,
            account_type=None,
            bank_name="SBI",
            batch_id=None,
            statement_label=None,
            mode=None,
            original_filename="old.pdf",
            upload_object_key=None,
        )
    return s


def test_mark_completed_persists_block(svc):
    with _offline(svc):
        svc.mark_completed("job-eng-1", {"statement_engine": ENGINE_BLOCK, "stats": {"total_transactions": 5}})
        svc._fallback_records["job-eng-1"]["status"] = "completed"
        out = svc.list_for_user("u1")
    uploads = {u["job_id"]: u for u in out["uploads"]}
    assert uploads["job-eng-1"]["statement_engine"] == ENGINE_BLOCK


def test_report_entry_carries_block(svc):
    with _offline(svc):
        svc.mark_completed("job-eng-1", {"statement_engine": ENGINE_BLOCK, "stats": {}})
        svc._fallback_records["job-eng-1"]["status"] = "completed"
        out = svc.list_for_user("u1")
    reports = [r for r in out["reports"] if r["job_id"] == "job-eng-1"]
    assert reports and reports[0]["statement_engine"] == ENGINE_BLOCK


def test_old_rows_render_null_key(svc):
    """Rows completed without the block return None — additive, UI-safe."""
    with _offline(svc):
        svc.mark_completed("job-old-1", {"stats": {}})
        svc._fallback_records["job-old-1"]["status"] = "completed"
        out = svc.list_for_user("u1")
    uploads = {u["job_id"]: u for u in out["uploads"]}
    assert uploads["job-old-1"]["statement_engine"] is None


def test_block_is_needs_review_shaped(svc):
    with _offline(svc):
        svc.mark_completed("job-eng-1", {"statement_engine": ENGINE_BLOCK, "stats": {}})
        svc._fallback_records["job-eng-1"]["status"] = "completed"
        out = svc.list_for_user("u1")
    b = {u["job_id"]: u for u in out["uploads"]}["job-eng-1"]["statement_engine"]
    assert b["needs_review"] is True and "BANK_MISMATCH" in b["review_codes"]
