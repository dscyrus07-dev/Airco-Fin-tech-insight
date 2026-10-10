"""API contract tests for the statement_engine block (Wave 8).

FastAPI TestClient with the auth dependency overridden; routers mounted alone.
Covers: banks endpoint additive fields (contract §7), mode-off additive key,
kill switch, and the block passthrough in build_frontend_processing_result.
"""
import os
from types import SimpleNamespace

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.routes import statements_analyze  # noqa: E402
from app.dependencies.auth import get_current_user  # noqa: E402
from app.services.statement_engine import serve, shadow  # noqa: E402

USER = {"id": "u-1", "email": "t@example.com", "name": "Test"}


@pytest.fixture()
def env(monkeypatch):
    monkeypatch.delenv(shadow.MODE_ENV, raising=False)
    monkeypatch.delenv(serve.SERVE_BANKS_ENV, raising=False)
    app = FastAPI()
    app.include_router(statements_analyze.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: USER
    return app, TestClient(app)


# --------------------------------------------------------------------------- #
# banks endpoint (contract §7)                                                 #
# --------------------------------------------------------------------------- #

def test_banks_additive_fields_off(env):
    _, client = env
    body = client.get("/api/statements/banks").json()
    ids = [b["id"] for b in body["banks"]]
    assert "hdfc" in ids and "sbi" in ids
    for b in body["banks"]:
        assert set(b) >= {"id", "name", "pipeline_name", "engines", "v2_served"}
        assert b["engines"] == ["legacy"] or "v2" in b["engines"]
        assert b["v2_served"] is False
    hdfc = next(b for b in body["banks"] if b["id"] == "hdfc")
    assert hdfc["engines"] == ["legacy", "v2"]


def test_banks_v2_served_only_allowlisted(env, monkeypatch):
    monkeypatch.setenv(shadow.MODE_ENV, "serve")
    monkeypatch.setenv(serve.SERVE_BANKS_ENV, "federal")
    _, client = env
    body = client.get("/api/statements/banks").json()
    served = {b["id"]: b["v2_served"] for b in body["banks"]}
    assert served.get("federal") is True
    assert served.get("hdfc") is False
    # federal has no legacy pipeline bank -> appears as a v2-only entry
    fed = next(b for b in body["banks"] if b["id"] == "federal")
    assert fed["engines"] == ["v2"] and fed["pipeline_name"] is None


def test_banks_v2_only_hidden_when_not_served(env, monkeypatch):
    monkeypatch.setenv(shadow.MODE_ENV, "serve")
    monkeypatch.setenv(serve.SERVE_BANKS_ENV, "hdfc")
    _, client = env
    ids = [b["id"] for b in client.get("/api/statements/banks").json()["banks"]]
    assert "federal" not in ids  # v2-only bank, not allowlisted -> not listed
    assert "hdfc" in ids


def test_banks_kill_switch(env, monkeypatch):
    monkeypatch.setenv(serve.SERVE_BANKS_ENV, "hdfc")
    monkeypatch.setenv(shadow.MODE_ENV, "serve")
    _, client = env
    b1 = {b["id"]: b["v2_served"] for b in client.get("/api/statements/banks").json()["banks"]}
    assert b1.get("hdfc") is True
    monkeypatch.setenv(shadow.MODE_ENV, "off")
    b2 = {b["id"]: b["v2_served"] for b in client.get("/api/statements/banks").json()["banks"]}
    assert b2.get("hdfc") is False


# --------------------------------------------------------------------------- #
# block passthrough                                                            #
# --------------------------------------------------------------------------- #

def test_frontend_result_builder_passthrough():
    from app.services.frontend_result_builder import build_frontend_processing_result
    block = {"engine": "v2", "mode": "serve", "verdict": "VERIFIED"}
    out = build_frontend_processing_result({"status": "success", "statement_engine": block}, mode="free")
    assert out["statement_engine"] == block
    out2 = build_frontend_processing_result({"status": "success"}, mode="free")
    assert "statement_engine" in out2 and out2["statement_engine"] is None


def test_old_style_consumer_unaffected(env):
    # a consumer reading only the previous keys sees no change
    _, client = env
    body = client.get("/api/statements/banks").json()
    for b in body["banks"]:
        legacy_shape = {"id": b["id"], "name": b["name"], "pipeline_name": b["pipeline_name"]}
        assert legacy_shape["id"] and legacy_shape["name"]


# --------------------------------------------------------------------------- #
# OpenAPI/schema (additive key documented via response shape)                  #
# --------------------------------------------------------------------------- #

def test_block_shape_matches_contract():
    block = serve.minimal_block("off")
    assert set(block) == {"engine", "mode", "layout_id", "verdict", "needs_review",
                          "review_codes", "anchored", "detected_bank", "advisory"}
    assert block["engine"] == "legacy" and block["mode"] == "off"
