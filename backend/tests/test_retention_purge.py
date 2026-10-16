import os
import time

from app.services import retention_purge as rp


def test_purge_temp_dir_removes_only_old_files(tmp_path, monkeypatch):
    monkeypatch.setattr(rp.settings, "TEMP_DIR", str(tmp_path))
    old = tmp_path / "old.xlsx"
    new = tmp_path / "new.xlsx"
    old.write_bytes(b"x")
    new.write_bytes(b"x")
    past = time.time() - 48 * 3600
    os.utime(old, (past, past))
    assert rp.purge_temp_dir(max_age_hours=24) == 1
    assert not old.exists() and new.exists()


def test_purge_order_children_before_jobs():
    names = [m.__tablename__ for m, _ in rp._PURGE_ORDER]
    assert names.index("raw_transactions") < names.index("processing_jobs")
    assert names.index("job_events") < names.index("processing_jobs")
    assert "api_request_logs" in names and "statement_metadata" in names
