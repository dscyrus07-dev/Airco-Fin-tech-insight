"""Wave11 T1: legacy wrong-bank guard.

_apply_mismatch_flag / _maybe_flag_bank_mismatch flag a successful legacy
result when the Slice-2 detector is HIGH-confidence for a *different*
supported bank. Never blocks, never switches banks, flag-off = no change.
"""
import os

import pytest

from app.services.pipeline_orchestrator import (
    _apply_mismatch_flag,
    _maybe_flag_bank_mismatch,
)
from app.services.statement_engine import Confidence, DetectionResult

LEGACY_BLOCK = {
    "engine": "legacy",
    "mode": "off",
    "layout_id": None,
    "verdict": None,
    "needs_review": False,
    "review_codes": [],
    "anchored": False,
    "detected_bank": None,
    "advisory": None,
}


def det(bank_id, confidence, supported=True, processor_key=None):
    return DetectionResult(
        bank_id=bank_id,
        bank_name=f"{bank_id} Bank",
        confidence=confidence,
        supported=supported,
        processor_key=processor_key if processor_key is not None else bank_id,
    )


class TestApplyMismatchFlag:
    def test_match_same_bank_no_flag(self):
        out = _apply_mismatch_flag(det("icici", Confidence.VERY_HIGH), "icici", LEGACY_BLOCK)
        assert out is LEGACY_BLOCK

    def test_mismatch_flags_needs_review(self):
        out = _apply_mismatch_flag(det("hdfc", Confidence.HIGH), "icici", LEGACY_BLOCK)
        assert out is not LEGACY_BLOCK
        assert out["needs_review"] is True
        assert "BANK_MISMATCH" in out["review_codes"]
        assert out["detected_bank"]["key"] == "hdfc"
        assert out["detected_bank"]["source"] == "detector"
        assert out["engine"] == "legacy" and out["verdict"] is None  # unchanged

    def test_unknown_detector_no_flag(self):
        out = _apply_mismatch_flag(
            det(None, Confidence.UNKNOWN, supported=False, processor_key=None), "icici", LEGACY_BLOCK
        )
        assert out is LEGACY_BLOCK

    def test_medium_confidence_no_flag(self):
        assert _apply_mismatch_flag(det("hdfc", Confidence.MEDIUM), "icici", LEGACY_BLOCK) is LEGACY_BLOCK

    def test_unsupported_detected_no_flag(self):
        out = _apply_mismatch_flag(
            det("citi", Confidence.HIGH, supported=False, processor_key=None), "icici", LEGACY_BLOCK
        )
        assert out is LEGACY_BLOCK

    def test_none_detection_no_flag(self):
        assert _apply_mismatch_flag(None, "icici", LEGACY_BLOCK) is LEGACY_BLOCK

    def test_no_duplicate_code_and_preserves_existing(self):
        block = dict(LEGACY_BLOCK, review_codes=["BANK_MISMATCH", "OTHER"])
        out = _apply_mismatch_flag(det("hdfc", Confidence.HIGH), "icici", block)
        assert out["review_codes"].count("BANK_MISMATCH") == 1
        assert "OTHER" in out["review_codes"]

    def test_works_on_none_block(self):
        out = _apply_mismatch_flag(det("hdfc", Confidence.HIGH), "icici", None)
        assert out["needs_review"] is True and "BANK_MISMATCH" in out["review_codes"]


class TestFlagGate:
    def test_flag_off_no_behaviour_change(self, monkeypatch):
        monkeypatch.setenv("STATEMENT_ENGINE_MISMATCH_GUARD", "0")
        out = _maybe_flag_bank_mismatch("nonexistent.pdf", "icici", LEGACY_BLOCK)
        assert out is LEGACY_BLOCK

    def test_flag_off_does_not_detect(self, monkeypatch):
        monkeypatch.setenv("STATEMENT_ENGINE_MISMATCH_GUARD", "0")

        def _boom(path):
            raise AssertionError("detector must not run when flag is off")

        import app.services.pipeline_orchestrator as po
        monkeypatch.setattr(po, "_mismatch_detect", _boom)
        out = _maybe_flag_bank_mismatch("x.pdf", "icici", None)
        assert out is None

    def test_detect_failure_returns_block(self, monkeypatch):
        monkeypatch.delenv("STATEMENT_ENGINE_MISMATCH_GUARD", raising=False)
        import app.services.pipeline_orchestrator as po
        monkeypatch.setattr(po, "_mismatch_detect", lambda p: None)
        out = po._maybe_flag_bank_mismatch("bad.pdf", "icici", LEGACY_BLOCK)
        assert out is LEGACY_BLOCK
