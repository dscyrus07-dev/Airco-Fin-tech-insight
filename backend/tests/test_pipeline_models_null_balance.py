from decimal import Decimal

from app.services.pipeline.models import NormalizedTransaction


def test_to_dict_serializes_null_balance_without_crashing():
    t = NormalizedTransaction(date="2024-01-01", description="x", debit=Decimal("5"))
    t.balance = None  # REVIEW rows from the v2 engine can carry no printed balance
    d = t.to_dict()
    assert d["balance"] is None and d["debit"] == 5.0


def test_to_dict_keeps_numeric_balance():
    t = NormalizedTransaction(date="2024-01-01", description="x", balance=Decimal("12.5"))
    assert t.to_dict()["balance"] == 12.5
