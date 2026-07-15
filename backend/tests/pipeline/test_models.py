"""Phase 1 unit tests for NormalizedTransaction / normalize."""

from __future__ import annotations

from decimal import Decimal

from app.services.pipeline import (
    NormalizedTransaction,
    StatementMetadata,
    to_normalized,
    transactions_to_dicts,
)


def test_normalized_transaction_to_dict():
    txn = NormalizedTransaction(
        date="2023-07-01",
        description="SALARY",
        credit=Decimal("1000.00"),
        balance=Decimal("1000.00"),
        category="Salary",
        confidence=0.99,
    )
    d = txn.to_dict()
    assert d["credit"] == 1000.0
    assert d["debit"] is None
    assert d["category"] == "Salary"


def test_to_normalized_from_object_with_to_dict():
    class FakeTxn:
        def to_dict(self):
            return {
                "date": "15-08-2023",
                "description": "UPI PAY",
                "debit": 50,
                "credit": None,
                "balance": 950,
            }

    rows = to_normalized([FakeTxn()], bank_key="axis")
    assert len(rows) == 1
    assert rows[0].debit == Decimal("50")
    assert rows[0].credit is None


def test_transactions_to_dicts_roundtrip():
    rows = to_normalized(
        [
            {
                "date": "2023-01-01",
                "description": "X",
                "credit": 10,
                "balance": 10,
                "category": "Others Credit",
            }
        ]
    )
    dicts = transactions_to_dicts(rows)
    assert dicts[0]["balance"] == 10.0
    again = NormalizedTransaction.from_mapping(dicts[0])
    assert again.credit == Decimal("10")
