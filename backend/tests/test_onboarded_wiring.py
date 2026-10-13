"""Onboard-wave wiring tests: every newly registered v2-only bank must round-trip
through /banks -> OVERRIDE -> process submit, gated by the serve allowlist.
No real PDFs, no network; synthetic text files only."""
import os
import sys

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api.routes import statements_analyze  # noqa: E402
from app.dependencies.auth import get_current_user  # noqa: E402
from app.services.analysis_service import (  # noqa: E402
    MemoryAnalysisStore,
    _registry_cfg_for,
    _v2_servable,
    analysis_service,
)
from app.services.pipeline_orchestrator import _get_bank_processor, _normalize_bank_name  # noqa: E402
from app.services.statement_engine import serve as v2serve  # noqa: E402
from tests.statement_engine.test_analysis_service import FakeStorage, pdf_bytes  # noqa: E402

ALICE = {"id": "alice-1", "email": "alice@example.com", "name": "Alice"}

# bank_id (registry/detector id) -> spec key; all v2-only onboarded banks.
ONBOARDED = {
    "standard_chartered": "scb",
    "dbs": "dbs",
    "ujjivan_sfb": "ujjivan_sfb",
    "au_sfb": "au_sfb",
    "dcb": "dcb",
    "federal": "federal",
    "idbi": "idbi",
    "yes": "yes",
    "pnb": "pnb",
    "kvb": "kvb",
    "iob": "iob",
    "central_bank": "central_bank",
    "equitas_sfb": "equitas_sfb",
    "bank_of_maharashtra": "bank_of_maharashtra",
    "bandhan": "bandhan",
    "hsbc": "hsbc",
    "south_indian": "south_indian",
    "csb": "csb",
    "uco": "uco",
    "airtel_pb": "airtel_pb",
    "ippb": "ippb",
    "dhanlaxmi": "dhanlaxmi",
    "apgv": "apgv",
}

GENERIC = "Statement of account\nTxn Date  Particulars  Debit  Credit  Balance\n01-04-2023  UPI X  100.00  0.00  900.00\n"


@pytest.fixture()
def env(monkeypatch):
    started = []

    async def fake_submit(rec, doc, user, **kw):
        started.append((doc["effective_bank"]["id"], doc["effective_bank"]["name"]))
        return "job-1"

    monkeypatch.setattr(analysis_service, "_store", MemoryAnalysisStore())
    monkeypatch.setattr(analysis_service, "storage", FakeStorage())
    monkeypatch.setattr(analysis_service, "_submit_job", fake_submit)
    app = FastAPI()
    app.include_router(statements_analyze.router, prefix="/api")
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: ALICE
    return client, started


def _serve_env(monkeypatch):
    monkeypatch.setenv("STATEMENT_ENGINE_V2_MODE", "serve")
    monkeypatch.setenv(
        "STATEMENT_ENGINE_V2_SERVE_BANKS", ",".join(sorted(set(ONBOARDED.values())))
    )


@pytest.mark.parametrize("bank_id,spec_key", sorted(ONBOARDED.items()))
def test_onboarded_bank_name_round_trips_to_spec(bank_id, spec_key, monkeypatch):
    _serve_env(monkeypatch)
    cfg = _registry_cfg_for(bank_id)
    assert cfg is not None, f"{bank_id}: no registry bank config"
    bank_key = _normalize_bank_name(cfg.display_name)
    resolved = v2serve.spec_key_for(bank_key)
    assert resolved == spec_key, (
        f"{bank_id}: {cfg.display_name!r} -> {bank_key!r} -> spec {resolved!r} "
        f"(expected {spec_key!r})"
    )
    assert v2serve.serving_enabled_for(bank_key), f"{bank_id}: serving_enabled_for False"
    assert _get_bank_processor(bank_key) is None, f"{bank_id}: unexpected legacy processor"


@pytest.mark.parametrize("bank_id", sorted(ONBOARDED))
def test_onboarded_bank_not_servable_by_default(bank_id):
    # shipped defaults: mode not 'serve' / empty allowlist -> never servable
    assert _v2_servable(bank_id) is False


@pytest.mark.parametrize("bank_id,spec_key", sorted(ONBOARDED.items()))
def test_onboarded_bank_api_flow(env, monkeypatch, bank_id, spec_key):
    """/banks lists the bank only when allowlisted; OVERRIDE works then and only then;
    process submits a job carrying the registry display name."""
    client, started = env

    def override(bank_key):
        r = client.post("/api/statements/analyze", files=[("files", ("a.pdf", pdf_bytes(GENERIC), "application/pdf"))])
        assert r.status_code == 200, r.text
        aid, doc = r.json()["analysis_id"], r.json()["documents"][0]
        c = client.post(
            f"/api/statements/{aid}/confirm",
            json={"documents": [{"document_id": doc["document_id"], "action": "OVERRIDE", "bank_id": bank_key}]},
        )
        assert c.status_code == 200, c.text
        return aid, c.json()["results"][0]

    # not allowlisted: not listed, override rejected, nothing processable
    monkeypatch.delenv("STATEMENT_ENGINE_V2_MODE", raising=False)
    monkeypatch.delenv("STATEMENT_ENGINE_V2_SERVE_BANKS", raising=False)
    ids = {b["id"] for b in client.get("/api/statements/banks").json()["banks"]}
    assert spec_key not in ids and bank_id not in ids
    aid, res = override(spec_key)
    assert res["ok"] is False and res["code"] == "BANK_NOT_SUPPORTED"
    p = client.post(f"/api/statements/{aid}/process").json()
    assert p["started"] == []

    # allowlisted + serve: listed v2-only, override accepted, job carries display name
    _serve_env(monkeypatch)
    banks = {b["id"]: b for b in client.get("/api/statements/banks").json()["banks"]}
    b = banks.get(spec_key)
    assert b is not None, f"{spec_key}: not in /banks under serve+allowlist"
    assert b["v2_served"] is True and b["engines"] == ["v2"] and b["pipeline_name"] is None
    aid, res = override(spec_key)
    assert res["ok"] is True, res
    p = client.post(f"/api/statements/{aid}/process").json()
    assert len(p["started"]) == 1
    eff_id, eff_name = started[-1]
    assert eff_id == bank_id
    assert isinstance(eff_name, str) and eff_name == _registry_cfg_for(bank_id).display_name


@pytest.mark.parametrize(
    "text,bank_id",
    [
        ("STANDARD CHARTERED BANK\nIFSC Code: SCBL0036001\n" + GENERIC, "standard_chartered"),
        ("DBS BANK LTD\nIFSC Code: DBSS0000001\n" + GENERIC, "dbs"),
        ("FEDERAL BANK\nIFSC Code: FDRL0000001\n" + GENERIC, "federal"),
        ("BANDHAN BANK\nIFSC Code: BDBL0000001\n" + GENERIC, "bandhan"),
        ("UCO BANK\nIFSC Code: UCBA0000001\n" + GENERIC, "uco"),
        ("CSB BANK LIMITED\nIFSC Code: CSBK0000001\n" + GENERIC, "csb"),
    ],
)
def test_onboarded_bank_analyze_detects(env, monkeypatch, text, bank_id):
    _serve_env(monkeypatch)
    client, _ = env
    r = client.post(
        "/api/statements/analyze", files=[("files", ("a.pdf", pdf_bytes(text), "application/pdf"))]
    )
    assert r.status_code == 200, r.text
    d = r.json()["documents"][0]
    if bank_id is None:
        # foreign-only evidence: must not resolve to an onboarded bank
        assert not d["bank"] or d["bank"]["id"] != "apgv"
        return
    assert d["bank"] is not None and d["bank"]["id"] == bank_id, (
        f"{bank_id}: detection failed -> {d['bank'] or d.get('suggestion')}"
    )
    assert d["bank"]["supported"] is True


def test_all_onboarded_listed_together_under_serve(env, monkeypatch):
    _serve_env(monkeypatch)
    client, _ = env
    banks = client.get("/api/statements/banks").json()["banks"]
    ids = {b["id"] for b in banks}
    assert set(ONBOARDED.values()) <= ids
    legacy = {b["id"] for b in banks if "legacy" in b.get("engines", [])}
    assert len(legacy) == 13  # the existing pipeline banks, unchanged
