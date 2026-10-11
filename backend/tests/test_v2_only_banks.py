"""Wave 11B (E2): v2-only bank plumbing — spec-key alias round-trip through
select -> confirm -> process submit for banks with no legacy processor.
No PDFs, no network: exercises the pure resolution helpers and the confirm/
submit gates with env-driven allowlisting."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.analysis_service import _registry_cfg_for, _v2_servable
from app.services.pipeline_orchestrator import _get_bank_processor, _normalize_bank_name
from app.services.statement_engine import serve as v2serve

# spec keys eligible per comparison/phase8c (see docs/slice3/V2_ENABLEMENT.md)
ELIGIBLE = ["hdfc", "axis", "idfc", "paytm", "indusind", "citibank", "city_union"]
V2_ONLY = ["indusind", "citibank", "city_union"]


@pytest.fixture(autouse=True)
def _serve_env(monkeypatch):
    monkeypatch.setenv("STATEMENT_ENGINE_V2_MODE", "serve")
    monkeypatch.setenv("STATEMENT_ENGINE_V2_SERVE_BANKS", ",".join(ELIGIBLE))
    yield


def _round_trip(bank_id: str) -> dict:
    """select(bank_id) -> confirm effective bank -> submit bank_name -> bank_key -> spec."""
    cfg = _registry_cfg_for(bank_id)
    assert cfg is not None, f"{bank_id}: /banks id does not resolve to a registry bank"
    bank_name = cfg.display_name
    bank_key = _normalize_bank_name(bank_name)
    return {
        "cfg_id": cfg.id,
        "bank_name": bank_name,
        "bank_key": bank_key,
        "spec_key": v2serve.spec_key_for(bank_key),
        "servable": _v2_servable(bank_id),
        "serve": v2serve.serving_enabled_for(bank_key),
        "processor": _get_bank_processor(bank_key),
    }


@pytest.mark.parametrize("bank_id", ELIGIBLE)
def test_eligible_bank_name_round_trips_to_spec(bank_id):
    r = _round_trip(bank_id)
    assert r["servable"], f"{bank_id}: not v2-servable under the allowlist"
    assert r["serve"], f"{bank_id}: serving_enabled_for returned False"
    assert r["spec_key"] == bank_id, (
        f"{bank_id}: name {r['bank_name']!r} normalised to {r['bank_key']!r} "
        f"-> spec {r['spec_key']!r} (alias bug)"
    )


@pytest.mark.parametrize("bank_id", V2_ONLY)
def test_v2_only_bank_has_no_legacy_processor(bank_id):
    r = _round_trip(bank_id)
    assert r["processor"] is None, f"{bank_id}: unexpectedly has a legacy processor"


def test_spec_key_id_resolves_when_different_from_detector_id():
    # /banks emits spec keys for v2-only banks; 'bob' is the spec key for the
    # 'bank_of_baroda' detector config. Both must resolve.
    cfg = _registry_cfg_for("bank_of_baroda")
    assert cfg is not None and cfg.id == "bank_of_baroda"
    via_spec = _registry_cfg_for("bob")
    assert via_spec is not None and via_spec.id == "bank_of_baroda"


def test_empty_allowlist_disables_v2_only_banks(monkeypatch):
    monkeypatch.setenv("STATEMENT_ENGINE_V2_SERVE_BANKS", "")
    for bid in V2_ONLY:
        assert _v2_servable(bid) is False
        assert _normalize_bank_name(_registry_cfg_for(bid).display_name) == bid
        assert v2serve.serving_enabled_for(bid) is False


def test_allowlist_env_is_per_call_not_baked(monkeypatch):
    assert _v2_servable("indusind") is True
    monkeypatch.setenv("STATEMENT_ENGINE_V2_SERVE_BANKS", "hdfc")
    assert _v2_servable("indusind") is False
    assert _v2_servable("hdfc") is True


def test_unknown_bank_still_not_servable():
    assert _v2_servable(None) is False
    assert _registry_cfg_for("not_a_bank") is None
