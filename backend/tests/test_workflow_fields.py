"""Unified-entry backend fields: confirm account_type, process full_name /
per-document account_type + statement_label. Absent fields must produce
exactly today's job payload."""
import json

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.routes import statements_analyze  # noqa: E402
from app.dependencies.auth import get_current_user  # noqa: E402
from app.services import analysis_service as asvc  # noqa: E402
from app.services.analysis_service import MemoryAnalysisStore, analysis_service  # noqa: E402
from tests.statement_engine.test_analysis_service import (  # noqa: E402
    HDFC,
    FakeStorage,
    pdf_bytes,
)

ALICE = {"id": "alice-1", "email": "alice@example.com", "name": "Alice Token"}
BOB = {"id": "bob-2", "email": "bob@example.com", "name": "Bob"}


class Captures:
    def __init__(self):
        self.jobs = []
        self.publishes = []
        self.uploads = []

    def user_info(self):
        return self.jobs[-1].input_data["user_info"] if self.jobs else None


@pytest.fixture()
def env(monkeypatch):
    cap = Captures()

    async def fake_create_job(job):
        cap.jobs.append(job)
        return job

    async def fake_publish(**kw):
        cap.publishes.append(kw)
        return True

    def fake_upsert(**kw):
        cap.uploads.append(kw)

    monkeypatch.setattr(analysis_service, "_store", MemoryAnalysisStore())
    monkeypatch.setattr(analysis_service, "storage", FakeStorage())
    from app.services import event_publisher as ep_mod, file_history_service as fh_mod, redis_job_store as rjs_mod
    monkeypatch.setattr(rjs_mod.redis_job_store, "create_job", fake_create_job)
    monkeypatch.setattr(ep_mod.event_publisher, "publish_file_processing_request", fake_publish)
    monkeypatch.setattr(fh_mod.file_history_service, "upsert_upload", fake_upsert)
    app = FastAPI()
    app.include_router(statements_analyze.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: ALICE
    return app, TestClient(app), cap


def files(*items):
    return [("files", (name, data, "application/pdf")) for name, data in items]


def _analyze(client):
    r = client.post("/api/statements/analyze", files=files(("hdfc.pdf", pdf_bytes(HDFC))))
    assert r.status_code == 200
    body = r.json()
    return body["analysis_id"], body["documents"][0]["document_id"]


def test_absent_fields_give_todays_payload(env):
    app, client, cap = env
    aid, did = _analyze(client)
    r = client.post(f"/api/statements/{aid}/confirm", json={"documents": [{"document_id": did, "action": "CONFIRM"}]})
    assert r.status_code == 200
    r = client.post(f"/api/statements/{aid}/process", json={})
    assert r.status_code == 200 and r.json()["started"], r.json()
    ui = cap.user_info()
    assert ui == {"full_name": "Alice Token", "account_type": "", "bank_name": ui["bank_name"],
                  "batch_id": aid, "statement_label": None}
    job = cap.jobs[-1]
    assert job.input_data["statement_label"] is None
    assert job.input_data["mode"] == "free"
    up = cap.uploads[-1]
    assert up["full_name"] == "Alice Token" and up["account_type"] is None and up["statement_label"] is None


def test_fields_reach_the_pipeline(env):
    app, client, cap = env
    aid, did = _analyze(client)
    r = client.post(f"/api/statements/{aid}/confirm", json={"documents": [
        {"document_id": did, "action": "CONFIRM", "account_type": "business"}]})
    assert r.status_code == 200
    r = client.post(f"/api/statements/{aid}/process", json={
        "full_name": "  Cyrus Mistry  ",
        "documents": [{"document_id": did, "account_type": "salaried", "statement_label": " FY24 main "}]})
    assert r.status_code == 200 and r.json()["started"], r.json()
    ui = cap.user_info()
    assert ui["full_name"] == "Cyrus Mistry"
    assert ui["account_type"] == "salaried"
    assert ui["statement_label"] == "FY24 main"
    assert cap.uploads[-1]["account_type"] == "salaried"
    assert cap.uploads[-1]["statement_label"] == "FY24 main"


def test_confirm_account_type_used_when_process_omits_it(env):
    app, client, cap = env
    aid, did = _analyze(client)
    client.post(f"/api/statements/{aid}/confirm", json={"documents": [
        {"document_id": did, "action": "CONFIRM", "account_type": "auto_detect"}]})
    r = client.post(f"/api/statements/{aid}/process", json={})
    assert r.status_code == 200
    assert cap.user_info()["account_type"] == "auto_detect"


def test_invalid_account_type_rejected(env):
    app, client, cap = env
    aid, did = _analyze(client)
    r = client.post(f"/api/statements/{aid}/confirm", json={"documents": [
        {"document_id": did, "action": "CONFIRM", "account_type": "nri"}]})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "BAD_ACCOUNT_TYPE"
    r = client.post(f"/api/statements/{aid}/process", json={
        "documents": [{"document_id": did, "account_type": "nri"}]})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "BAD_ACCOUNT_TYPE"
    assert not cap.jobs


def test_invalid_full_name_rejected(env):
    app, client, cap = env
    aid, did = _analyze(client)
    client.post(f"/api/statements/{aid}/confirm", json={"documents": [{"document_id": did, "action": "CONFIRM"}]})
    r = client.post(f"/api/statements/{aid}/process", json={"full_name": "x" * 121})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "BAD_FULL_NAME"
    r = client.post(f"/api/statements/{aid}/process", json={"full_name": 42})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "BAD_FULL_NAME"
    assert not cap.jobs


def test_other_owner_cannot_confirm_or_process(env):
    app, client, cap = env
    aid, did = _analyze(client)
    app.dependency_overrides[get_current_user] = lambda: BOB
    r = client.post(f"/api/statements/{aid}/confirm", json={"documents": [{"document_id": did, "action": "CONFIRM"}]})
    assert r.status_code in (403, 404)
    r = client.post(f"/api/statements/{aid}/process", json={"full_name": "Bob"})
    assert r.status_code in (403, 404)
    assert not cap.jobs
