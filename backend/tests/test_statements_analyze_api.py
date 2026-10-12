"""Slice 2C API tests (FastAPI TestClient, router mounted alone: no DB / Redis / S3 / RabbitMQ)."""
import json

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.routes import statements_analyze  # noqa: E402
from app.dependencies.auth import get_current_user  # noqa: E402
from app.services.analysis_service import MemoryAnalysisStore, analysis_service  # noqa: E402
from tests.statement_engine.test_analysis_service import (  # noqa: E402
    HDFC,
    KOTAK,
    PAYSLIP,
    FakeStorage,
    _image_only_pdf,
    pdf_bytes,
)

ALICE = {"id": "alice-1", "email": "alice@example.com", "name": "Alice"}
BOB = {"id": "bob-2", "email": "bob@example.com", "name": "Bob"}


@pytest.fixture()
def env(monkeypatch):
    started = []

    async def fake_submit(rec, doc, user, **kw):
        started.append(doc["effective_bank"]["id"])
        return "job-1"

    monkeypatch.setattr(analysis_service, "_store", MemoryAnalysisStore())
    monkeypatch.setattr(analysis_service, "storage", FakeStorage())
    monkeypatch.setattr(analysis_service, "_submit_job", fake_submit)
    app = FastAPI()
    app.include_router(statements_analyze.router, prefix="/api")
    client = TestClient(app)
    return app, client, started


def as_user(app, user):
    app.dependency_overrides[get_current_user] = lambda: user


def files(*items):
    return [("files", (name, data, "application/pdf")) for name, data in items]


def test_unauthenticated_requests_are_rejected(env):
    app, client, _ = env
    assert client.post("/api/statements/analyze", files=files(("a.pdf", pdf_bytes(HDFC)))).status_code == 401
    assert client.get("/api/statements/abc").status_code == 401
    assert client.post("/api/statements/abc/confirm", json={"documents": []}).status_code == 401
    assert client.post("/api/statements/abc/process").status_code == 401
    assert client.get("/api/statements/banks").status_code == 401


def test_single_upload(env):
    app, client, _ = env
    as_user(app, ALICE)
    r = client.post("/api/statements/analyze", files=files(("hdfc.pdf", pdf_bytes(HDFC))))
    assert r.status_code == 200
    body = r.json()
    d = body["documents"][0]
    assert d["bank"]["id"] == "hdfc" and d["state"] == "DETECTED" and d["evidence"] and d["layout"]["id"] != ""
    assert "storage_key" not in json.dumps(body)


def test_multiple_upload_with_one_bad_file_still_succeeds(env):
    app, client, _ = env
    as_user(app, ALICE)
    r = client.post("/api/statements/analyze", files=files(
        ("a.pdf", pdf_bytes(HDFC)), ("b.pdf", pdf_bytes(KOTAK)), ("scan.pdf", _image_only_pdf()),
        ("bad.pdf", b"garbage"), ("slip.pdf", pdf_bytes(PAYSLIP))))
    assert r.status_code == 200
    states = {d["filename"]: d["state"] for d in r.json()["documents"]}
    assert states["a.pdf"] == "DETECTED" and states["b.pdf"] == "DETECTED"
    assert states["scan.pdf"] == "UNSUPPORTED" and states["bad.pdf"] == "ERROR"


def test_no_files_and_bad_passwords_json(env):
    app, client, _ = env
    as_user(app, ALICE)
    assert client.post("/api/statements/analyze").status_code == 422
    r = client.post("/api/statements/analyze", files=files(("a.pdf", pdf_bytes(HDFC))), data={"passwords": "{not json"})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "BAD_PASSWORDS"


def test_locked_pdf_unlock_flow(env):
    app, client, _ = env
    as_user(app, ALICE)
    r = client.post("/api/statements/analyze", files=files(("l.pdf", pdf_bytes(KOTAK, password="pw-xyz"))))
    d = r.json()["documents"][0]
    assert d["requires_password"] is True
    aid, did = r.json()["analysis_id"], d["document_id"]
    bad = client.post(f"/api/statements/{aid}/documents/{did}/unlock", json={"password": "nope"}).json()
    assert bad["unlocked"] is False
    good = client.post(f"/api/statements/{aid}/documents/{did}/unlock", json={"password": "pw-xyz"}).json()
    assert good["unlocked"] is True and good["document"]["bank"]["id"] == "kotak"
    assert client.post(f"/api/statements/{aid}/documents/{did}/unlock", json={}).status_code == 400


def test_confirm_override_and_process(env):
    app, client, started = env
    as_user(app, ALICE)
    r = client.post("/api/statements/analyze", files=files(("a.pdf", pdf_bytes(HDFC)), ("slip.pdf", pdf_bytes(PAYSLIP))))
    aid = r.json()["analysis_id"]
    a = next(d for d in r.json()["documents"] if d["filename"] == "a.pdf")
    slip = next(d for d in r.json()["documents"] if d["filename"] == "slip.pdf")
    # nothing runs before confirmation
    p0 = client.post(f"/api/statements/{aid}/process").json()
    assert p0["started"] == [] and started == []
    c = client.post(f"/api/statements/{aid}/confirm", json={"documents": [
        {"document_id": a["document_id"], "action": "CONFIRM"},
        {"document_id": slip["document_id"], "action": "OVERRIDE", "bank_id": "sbi"}]}).json()
    assert all(x["ok"] for x in c["results"])
    p = client.post(f"/api/statements/{aid}/process").json()
    assert len(p["started"]) == 2 and sorted(started) == ["hdfc", "sbi"]
    assert client.post(f"/api/statements/{aid}/confirm", json={"documents": "x"}).status_code == 400


def test_override_with_unsupported_bank_is_rejected(env):
    app, client, _ = env
    as_user(app, ALICE)
    r = client.post("/api/statements/analyze", files=files(("slip.pdf", pdf_bytes(PAYSLIP))))
    aid, d = r.json()["analysis_id"], r.json()["documents"][0]
    c = client.post(f"/api/statements/{aid}/confirm", json={"documents": [{"document_id": d["document_id"], "action": "OVERRIDE", "bank_id": "yes"}]}).json()
    assert c["results"][0]["ok"] is False and c["results"][0]["code"] == "BANK_NOT_SUPPORTED"


def test_cross_user_access_is_a_404(env):
    app, client, started = env
    as_user(app, ALICE)
    r = client.post("/api/statements/analyze", files=files(("a.pdf", pdf_bytes(HDFC))))
    aid, d = r.json()["analysis_id"], r.json()["documents"][0]
    as_user(app, BOB)
    assert client.get(f"/api/statements/{aid}").status_code == 404
    assert client.post(f"/api/statements/{aid}/confirm", json={"documents": [{"document_id": d["document_id"], "action": "CONFIRM"}]}).status_code == 404
    assert client.post(f"/api/statements/{aid}/process").status_code == 404
    assert client.post(f"/api/statements/{aid}/documents/{d['document_id']}/unlock", json={"password": "x"}).status_code == 404
    assert started == []
    as_user(app, ALICE)
    assert client.get(f"/api/statements/{aid}").status_code == 200


def test_banks_list_only_contains_processable_banks(env):
    app, client, _ = env
    as_user(app, ALICE)
    ids = {b["id"] for b in client.get("/api/statements/banks").json()["banks"]}
    assert "hdfc" in ids and "yes" not in ids and len(ids) == 13
