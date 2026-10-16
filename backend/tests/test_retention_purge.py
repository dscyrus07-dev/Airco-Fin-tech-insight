import os
import time
from datetime import datetime, timedelta, timezone

import pytest

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


def test_purge_database_on_throwaway_pg(monkeypatch):
    """Real purge against a scratch Postgres (RETENTION_TEST_DATABASE_URL).
    Simplified tables carry only the columns the purge touches; FK children ->
    processing_jobs proves deletion order end-to-end."""
    url = os.getenv("RETENTION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RETENTION_TEST_DATABASE_URL not set")

    from sqlalchemy import (Column, DateTime, ForeignKey, Integer, MetaData,
                            String, Table, create_engine, func, select, text)
    from sqlalchemy.orm import sessionmaker

    eng = create_engine(url)
    md = MetaData()
    ts = Column("created_at", DateTime(timezone=True))
    jobs = Table("processing_jobs", md, Column("id", String(40), primary_key=True), ts)
    children = {}
    for name in ("raw_transactions", "job_events", "report_generation_logs",
                 "download_logs", "statement_metadata"):
        children[name] = Table(
            name, md,
            Column("id", Integer, primary_key=True),
            Column("job_id", String(40), ForeignKey("processing_jobs.id")),
            Column("created_at", DateTime(timezone=True)),
        )
    api_logs = Table("api_request_logs", md, Column("id", Integer, primary_key=True),
                     Column("request_at", DateTime(timezone=True)))
    err_logs = Table("error_logs", md, Column("id", Integer, primary_key=True),
                     Column("occurred_at", DateTime(timezone=True)))
    md.drop_all(eng)
    md.create_all(eng)

    now = datetime.now(timezone.utc)
    ages = {"old": 30, "d8": 8, "edge": 6.96, "new": 1}  # 6.96d == 6d23h
    with eng.begin() as conn:
        for tag, days in ages.items():
            at = now - timedelta(days=days)
            conn.execute(jobs.insert().values(id=f"job_{tag}", created_at=at))
            for t in children.values():
                conn.execute(t.insert().values(job_id=f"job_{tag}", created_at=at))
            conn.execute(api_logs.insert().values(request_at=at))
            conn.execute(err_logs.insert().values(occurred_at=at))

    monkeypatch.setattr(rp, "SessionLocal", sessionmaker(bind=eng))

    def rows(t, col="created_at"):
        with eng.connect() as c:
            return c.execute(select(func.count()).select_from(t)).scalar()

    table_for = dict(children)
    table_for.update({"processing_jobs": jobs, "api_request_logs": api_logs,
                      "error_logs": err_logs})
    col_for = {"api_request_logs": "request_at", "error_logs": "occurred_at"}

    # dry run: returns would-delete counts, deletes nothing
    counts = rp.purge_database(retention_days=7, dry_run=True)
    for name in ("raw_transactions", "job_events", "report_generation_logs",
                     "download_logs", "statement_metadata", "processing_jobs",
                     "api_request_logs", "error_logs"):
        assert counts[name] == 2, (name, counts)
        assert rows(table_for[name], col_for.get(name, "created_at")) == 4

    # failing table does not stop the rest
    with eng.begin() as conn:
        conn.execute(text("DROP TABLE download_logs"))
    counts = rp.purge_database(retention_days=7, dry_run=False)
    assert counts["download_logs"] == -1
    assert counts["processing_jobs"] == 2
    assert counts["raw_transactions"] == 2
    with eng.connect() as c:
        assert c.execute(select(func.count()).select_from(jobs)).scalar() == 2
        kept = {r[0] for r in c.execute(select(jobs.c.id))}
        assert kept == {"job_edge", "job_new"}
        assert c.execute(select(func.count()).select_from(children["raw_transactions"])).scalar() == 2
        assert c.execute(select(func.count()).select_from(api_logs)).scalar() == 2
        assert c.execute(select(func.count()).select_from(err_logs)).scalar() == 2
    md.drop_all(eng)
