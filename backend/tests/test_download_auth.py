import time

import pytest
from fastapi import HTTPException

from app.api.routes import jobs as jobs_routes
from app.models.job import Job, JobType
from app.services import download_tokens as dt


def _job(owner="user-a"):
    return Job(id="JOB123", type=JobType.PDF_PROCESSING, correlation_id="c", user_id=owner)


def test_token_roundtrip_and_scope():
    tok = dt.issue_download_token("JOB123")
    assert dt.verify_download_token(tok, "JOB123")
    assert not dt.verify_download_token(tok, "JOB124")
    assert not dt.verify_download_token(None, "JOB123")
    assert not dt.verify_download_token("garbage", "JOB123")


def test_token_expiry_and_tamper():
    expired = dt.issue_download_token("JOB123", ttl_seconds=-5)
    assert not dt.verify_download_token(expired, "JOB123")
    good = dt.issue_download_token("JOB123")
    head, exp, sig = good.rsplit(".", 2)
    assert not dt.verify_download_token(f"{head}.{int(exp) + 9999}.{sig}", "JOB123")
    assert not dt.verify_download_token(f"{head}.{exp}.{'0' * len(sig)}", "JOB123")


def test_job_access_rules():
    job = _job()
    with pytest.raises(HTTPException) as e:
        jobs_routes._ensure_job_access(job, None, None)
    assert e.value.status_code == 401
    with pytest.raises(HTTPException) as e:
        jobs_routes._ensure_job_access(job, None, "nope")
    assert e.value.status_code == 401
    assert jobs_routes._ensure_job_access(job, {"id": "user-a", "roles": []}) is True
    with pytest.raises(HTTPException) as e:
        jobs_routes._ensure_job_access(job, {"id": "user-b", "roles": []})
    assert e.value.status_code == 403
    assert jobs_routes._ensure_job_access(job, {"id": "x", "roles": ["admin"]}) is True
    assert jobs_routes._ensure_job_access(job, None, dt.issue_download_token("JOB123")) is False
    with pytest.raises(HTTPException):
        jobs_routes._ensure_job_access(job, None, dt.issue_download_token("OTHER"))


def test_forwarded_headers_ignored_by_default(monkeypatch):
    from types import SimpleNamespace
    from app.dependencies.auth import forwarded_header

    req = SimpleNamespace(headers={"X-Airco-User-Id": "victim"})
    monkeypatch.delenv("TRUST_FORWARDED_USER_HEADERS", raising=False)
    assert forwarded_header(req, "X-Airco-User-Id") is None
    monkeypatch.setenv("TRUST_FORWARDED_USER_HEADERS", "true")
    assert forwarded_header(req, "X-Airco-User-Id") == "victim"


def test_file_download_gate(monkeypatch):
    from app.api.routes import download as dl

    with pytest.raises(HTTPException) as e:
        dl._authorise_file_download("JOB9", None, None)
    assert e.value.status_code == 401
    dl._authorise_file_download("JOB9", None, dt.issue_download_token("JOB9"))
    with pytest.raises(HTTPException) as e:
        dl._authorise_file_download("", {"id": "u", "roles": []}, None)
    assert e.value.status_code == 403
    dl._authorise_file_download("", {"id": "a", "roles": ["admin"]}, None)
