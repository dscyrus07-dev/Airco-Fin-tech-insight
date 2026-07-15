"""Phase 3 shared reconciliation unit tests (parity math)."""
from __future__ import annotations

import pytest

from app.services.pipeline.reconciliation import (
    auto_correct_debit_credit,
    compute_reconciliation,
)
from app.services.banks.hdfc.reconciliation import (
    HDFCReconciliation,
    HDFCReconciliationError,
)


def test_perfect_progression_reconciles():
    txns = [
        {"balance": 100.0, "debit": None, "credit": 50.0},  # open 50
        {"balance": 80.0, "debit": 20.0, "credit": None},
        {"balance": 130.0, "debit": None, "credit": 50.0},
    ]
    r = compute_reconciliation(txns)
    assert r.is_reconciled is True
    assert r.opening_balance == 50.0
    assert r.closing_balance == 130.0
    assert r.mismatch_count if False else len(r.mismatches) == 0
    assert abs(r.final_difference) <= 0.01


def test_progression_mismatch_counts():
    txns = [
        {"balance": 100.0, "debit": None, "credit": 0.0},
        {"balance": 50.0, "debit": 10.0, "credit": None},  # should be 90
    ]
    r = compute_reconciliation(txns)
    assert r.is_reconciled is False
    assert len(r.mismatches) == 1
    assert r.mismatches[0].transaction_index == 1


def test_auto_correct_swaps_side():
    # balance drops by 20 but amount parked on credit
    txns = [
        {"balance": 100.0, "debit": None, "credit": None},
        {"balance": 80.0, "debit": None, "credit": 20.0},
    ]
    fixed, n = auto_correct_debit_credit(txns)
    assert n == 1
    assert fixed[1]["debit"] == 20.0
    assert fixed[1]["credit"] is None


def test_hdfc_wrapper_empty_raises():
    with pytest.raises(HDFCReconciliationError) as ei:
        HDFCReconciliation(strict_mode=True).reconcile([])
    assert ei.value.error_code == "NO_TRANSACTIONS"


def test_hdfc_wrapper_to_dict_keys():
    txns = [
        {"balance": 100.0, "debit": None, "credit": 10.0},
        {"balance": 110.0, "debit": None, "credit": 10.0},
    ]
    r = HDFCReconciliation(strict_mode=False).reconcile(txns)
    d = r.to_dict()
    for k in (
        "is_reconciled",
        "opening_balance",
        "closing_balance",
        "total_credits",
        "total_debits",
        "calculated_closing",
        "final_difference",
        "transaction_count",
        "mismatch_count",
    ):
        assert k in d

def test_repair_swap_and_delta():
    from app.services.pipeline.reconciliation import repair_transaction_sides, compute_reconciliation
    tx = [
        {"balance": 1000.0, "debit": None, "credit": None},
        {"balance": 800.0, "debit": None, "credit": 200.0},
        {"balance": 750.0, "debit": 100.0, "credit": None},
    ]
    fixed, stats = repair_transaction_sides(tx, opening_balance=1000.0)
    assert stats["swap"] >= 1
    assert fixed[1]["debit"] == 200.0
    assert fixed[2]["debit"] == 50.0
    r = compute_reconciliation(fixed, expected_opening=1000.0)
    assert r.is_reconciled is True
    assert len(r.mismatches) == 0
