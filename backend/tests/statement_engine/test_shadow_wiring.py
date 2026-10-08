"""Shadow-mode wiring: flag gating, never-touches-legacy, PII-free record shape."""
import os
import time

import pytest

from app.services.statement_engine import shadow


class _FakeLegacyResult:
    status = "success"
    transactions = [{"date": "2023-04-01", "description": "SHOP", "debit": 100.0, "balance": 900.0}]
    verification = {"checks": [{"name": "opening_closing_check",
                                "detail": {"opening": 1000.0, "closing": 900.0}}]}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(shadow.MODE_ENV, raising=False)


def test_flag_off_does_nothing_and_touches_nothing(monkeypatch):
    calls = []
    monkeypatch.setenv(shadow.MODE_ENV, "off")
    out = shadow.run_v2_shadow("no/such/file.pdf", "alpha", _FakeLegacyResult(), sink=calls.append)
    assert out is None and calls == []


def test_flag_unset_defaults_to_off(monkeypatch):
    calls = []
    out = shadow.run_v2_shadow("no/such/file.pdf", "alpha", _FakeLegacyResult(), sink=calls.append)
    assert out is None and calls == []


def test_serve_mode_raises_clearly(monkeypatch):
    monkeypatch.setenv(shadow.MODE_ENV, "serve")
    with pytest.raises(RuntimeError, match="not enabled"):
        shadow.run_v2_shadow("no/such/file.pdf", "alpha", _FakeLegacyResult())


def test_shadow_swallows_v2_exceptions_and_records_them(monkeypatch):
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    monkeypatch.setattr(shadow, "_v2_route", lambda p: (_ for _ in ()).throw(ValueError("boom")))
    monkeypatch.setattr(shadow, "_sha8", lambda p: "deadbeef")
    calls = []
    assert shadow.run_v2_shadow("x.pdf", "alpha", _FakeLegacyResult(), sink=calls.append) is None
    assert len(calls) == 1 and calls[0]["shadow_error"] == "ValueError"


def test_shadow_timeout_is_recorded_not_raised(monkeypatch):
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")

    def _slow(p):
        time.sleep(0.3)
        raise AssertionError("should have timed out")

    monkeypatch.setattr(shadow, "_v2_route", _slow)
    monkeypatch.setattr(shadow, "_sha8", lambda p: "deadbeef")
    monkeypatch.setattr(shadow, "SHADOW_TIMEOUT_S", 0.05)
    calls = []
    shadow.run_v2_shadow("x.pdf", "alpha", _FakeLegacyResult(), sink=calls.append)
    assert calls[0]["shadow_error"] == "TimeoutError"


def test_shadow_record_schema_has_no_pii_fields(monkeypatch, tmp_path):
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    allowed = {"sha8", "bank_key", "v2_status", "layout_id", "fallback_reason",
               "v2_verdict", "v2_ms", "agree", "overall", "shadow_error"}

    class _R:
        status = "fallback"
        layout_id = None
        fallback_reason = "no_layout"
        result = None

    monkeypatch.setattr(shadow, "_v2_route", lambda p: _R())
    calls = []
    shadow.run_v2_shadow(str(pdf), "alpha", _FakeLegacyResult(), sink=calls.append)
    assert len(calls) == 1
    assert set(calls[0]) <= allowed
    assert calls[0]["sha8"] and calls[0]["v2_status"] == "fallback"
