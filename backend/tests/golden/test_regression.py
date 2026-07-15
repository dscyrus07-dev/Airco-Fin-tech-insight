"""
Golden regression tests.

Requires:
  - GOLDEN_SAMPLES_DIR pointing at sample PDFs (same layout as capture)
  - Committed golden JSON under tests/golden/{bank_key}/*.json

If GOLDEN_SAMPLES_DIR is unset or empty, PDF-backed tests are skipped.
Unit tests for normalize + snapshot utils always run.
"""

from __future__ import annotations

import json
import os
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List

import pytest

from app.services.pipeline.models import NormalizedTransaction, StatementMetadata
from app.services.pipeline.normalize import to_normalized, transactions_to_dicts
from tests.golden.snapshot_utils import (
    assert_snapshot_match,
    bank_display_name,
    build_snapshot_payload,
    discover_samples,
    extract_reconciliation_from_result,
    mask_account_number,
    run_bank_reconciliation,
)

GOLDEN_ROOT = Path(__file__).resolve().parent
SAMPLES_DIR = os.environ.get("GOLDEN_SAMPLES_DIR")


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _list_committed_snapshots() -> List[Path]:
    paths: List[Path] = []
    for bank_dir in sorted(GOLDEN_ROOT.iterdir()):
        if not bank_dir.is_dir():
            continue
        if bank_dir.name.startswith("_") or bank_dir.name == "__pycache__":
            continue
        for path in sorted(bank_dir.glob("*.json")):
            paths.append(path)
    return paths


# ---------------------------------------------------------------------------
# Always-on unit tests (no PDFs required)
# ---------------------------------------------------------------------------


def test_mask_account_number():
    assert mask_account_number("123456789012") == "****9012"
    assert mask_account_number("XX8705") == "****8705"
    assert mask_account_number("") == ""


def test_to_normalized_core_fields():
    raw = [
        {
            "date": "01/07/2023",
            "description": "  SALARY  CREDIT  ",
            "debit": None,
            "credit": 50000,
            "balance": 50000,
            "ref_no": "R1",
            "txn_time": "10:00:00",
            "category": "Salary",
            "confidence": 0.99,
        },
        {
            "date": "05-07-2023",
            "description": "ATM WDL",
            "debit": 2000,
            "credit": 0,
            "balance": 48000,
            "category": "ATM Withdrawal",
            "confidence_score": 95,
        },
    ]
    rows = to_normalized(raw, bank_key="hdfc")
    assert len(rows) == 2
    assert isinstance(rows[0], NormalizedTransaction)
    assert rows[0].credit == Decimal("50000")
    assert rows[0].debit is None
    assert rows[0].extras.get("txn_time") == "10:00:00"
    assert rows[0].description == "SALARY CREDIT"
    assert rows[1].debit == Decimal("2000")
    assert rows[1].credit is None
    assert rows[1].confidence == pytest.approx(0.95)

    dicts = transactions_to_dicts(rows)
    assert dicts[0]["credit"] == 50000.0
    assert dicts[1]["debit"] == 2000.0


def test_statement_metadata_from_mapping():
    meta = StatementMetadata.from_mapping(
        {
            "account_no": "1234567890",
            "full_name": "Test User",
            "opening_balance": "1000.50",
            "ifsc": "HDFC0001",
        },
        bank_name="HDFC Bank",
        bank_key="hdfc",
    )
    assert meta.account_number == "1234567890"
    assert meta.account_holder == "Test User"
    assert meta.opening_balance == Decimal("1000.50")
    assert meta.extras.get("ifsc") == "HDFC0001"
    d = meta.to_dict()
    assert d["account_no"] == "1234567890"
    assert d["ifsc"] == "HDFC0001"


def test_build_snapshot_payload_masks_account():
    payload = build_snapshot_payload(
        bank_key="hdfc",
        sample_name="demo",
        mode="free",
        process_result={"status": "success", "stats": {"total_transactions": 1}},
        transactions=[
            {
                "date": "2023-07-01",
                "description": "SALARY",
                "debit": None,
                "credit": 1000,
                "balance": 1000,
                "category": "Salary",
                "confidence": 0.9,
            }
        ],
        reconciliation={"is_reconciled": True, "mismatch_count": 0},
        aggregation={"total_credits": 1000, "total_debits": 0},
        metadata={"account_number": "9988776655", "bank_name": "HDFC Bank"},
    )
    assert payload["metadata"]["account_number"] == "****6655"
    assert payload["transaction_count"] == 1
    assert payload["categories"] == ["Salary"]
    assert "salaryCredits" in (payload.get("monthly_analysis") or {}) or payload.get(
        "summary_stats"
    )


def test_assert_snapshot_match_identity():
    payload = build_snapshot_payload(
        bank_key="hdfc",
        sample_name="demo",
        mode="free",
        process_result={"status": "success"},
        transactions=[
            {
                "date": "2023-07-01",
                "description": "SALARY",
                "debit": None,
                "credit": 1000,
                "balance": 1000,
                "category": "Salary",
            }
        ],
        reconciliation={"is_reconciled": True, "mismatch_count": 0},
        metadata={},
    )
    assert_snapshot_match(payload, payload)


def test_run_bank_reconciliation_running_balance():
    """Fallback path records real mismatch_count and balances (no processor needed)."""
    txns = [
        {"date": "2023-07-01", "description": "A", "debit": None, "credit": 100, "balance": 100},
        {"date": "2023-07-02", "description": "B", "debit": 30, "credit": None, "balance": 70},
    ]
    recon = run_bank_reconciliation(
        "unknown_bank_xyz",
        txns,
        expected_opening=0.0,
        expected_closing=70.0,
    )
    assert recon["is_reconciled"] is True
    assert recon["mismatch_count"] == 0
    assert recon["opening_balance"] == 0.0
    assert recon["closing_balance"] == 70.0
    assert recon["total_credits"] == 100.0
    assert recon["total_debits"] == 30.0
    assert recon["mismatches"] == []

    broken = [
        {"date": "2023-07-01", "description": "A", "debit": None, "credit": 100, "balance": 100},
        {"date": "2023-07-02", "description": "B", "debit": 30, "credit": None, "balance": 99},
    ]
    recon_bad = run_bank_reconciliation(
        "unknown_bank_xyz",
        broken,
        expected_opening=0.0,
        expected_closing=70.0,
    )
    assert recon_bad["mismatch_count"] >= 1
    assert len(recon_bad["mismatches"]) >= 1
    assert recon_bad["is_reconciled"] is False


# ---------------------------------------------------------------------------
# PDF-backed golden regression (skipped without samples + snapshots)
# ---------------------------------------------------------------------------


def _run_processor_for_regression(pdf_path: str, bank_key: str, mode: str) -> Any:
    from app.services.pipeline_orchestrator import _get_bank_processor

    ProcessorClass = _get_bank_processor(bank_key)
    if ProcessorClass is None:
        raise RuntimeError(f"Unsupported bank_key: {bank_key}")
    processor = ProcessorClass(
        strict_mode=False,
        enable_ai=(mode == "hybrid"),
        api_key=None,
        audit_service=None,
        job_id=None,
    )
    with tempfile.TemporaryDirectory(prefix="golden_reg_") as tmp:
        return processor.process(
            file_path=pdf_path,
            user_info={
                "full_name": "Golden Snapshot",
                "account_type": "Savings",
                "bank_name": bank_display_name(bank_key),
            },
            output_dir=tmp,
        )


def _actual_from_result(result: Any, bank_key: str, sample_name: str, mode: str) -> Dict[str, Any]:
    transactions: List[Dict[str, Any]] = []
    for t in getattr(result, "transactions", None) or []:
        if isinstance(t, dict):
            transactions.append(t)
        elif hasattr(t, "to_dict"):
            transactions.append(t.to_dict())

    process_dict = result.to_dict() if hasattr(result, "to_dict") else {}
    aggregation = getattr(result, "aggregation", None)
    reconciliation = extract_reconciliation_from_result(result, transactions, bank_key)

    return build_snapshot_payload(
        bank_key=bank_key,
        sample_name=sample_name,
        mode=mode,
        process_result=process_dict if isinstance(process_dict, dict) else {},
        transactions=transactions,
        reconciliation=reconciliation,
        aggregation=aggregation,
        metadata={
            "bank_name": bank_display_name(bank_key),
            "bank_key": bank_key,
            "opening_balance": reconciliation.get("opening_balance"),
            "closing_balance": reconciliation.get("closing_balance"),
        },
    )


@pytest.mark.skipif(
    not SAMPLES_DIR or not Path(SAMPLES_DIR).is_dir(),
    reason="GOLDEN_SAMPLES_DIR not set or missing",
)
def test_golden_snapshots_against_live_pipeline():
    snapshots = _list_committed_snapshots()
    if not snapshots:
        pytest.skip("No committed golden JSON under tests/golden/{bank_key}/")

    samples = { (s["bank_key"], s["sample_name"]): s for s in discover_samples(Path(SAMPLES_DIR)) }
    if not samples:
        pytest.skip(f"No PDFs under GOLDEN_SAMPLES_DIR={SAMPLES_DIR}")

    # Free-mode snapshots only in automated regression (hybrid needs API key)
    free_snaps = [p for p in snapshots if "__hybrid" not in p.stem]
    if not free_snaps:
        pytest.skip("No free-mode golden snapshots found")

    for snap_path in free_snaps:
        bank_key = snap_path.parent.name
        sample_name = snap_path.stem
        key = (bank_key, sample_name)
        if key not in samples:
            pytest.fail(
                f"Golden snapshot {snap_path.relative_to(GOLDEN_ROOT)} has no matching PDF "
                f"under {SAMPLES_DIR}"
            )
        expected = _load_json(snap_path)
        result = _run_processor_for_regression(samples[key]["path"], bank_key, "free")
        actual = _actual_from_result(result, bank_key, sample_name, "free")
        try:
            assert_snapshot_match(expected, actual)
        except AssertionError as exc:
            raise AssertionError(f"{snap_path.name}: {exc}") from exc
