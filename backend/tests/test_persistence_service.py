"""
Tests for Airco Insights — Supabase Persistence Layer
=======================================================
Uses mock SQLAlchemy sessions to test without real DB connection.

Test groups:
    1.  Transaction persistence — bulk insert
    2.  Merchant upsert
    3.  Input validation
    4.  Rollback on failure
    5.  Edge cases
    6.  Combined persist_all
"""

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import date

from app.services.persistence_service import (
    persist_transactions,
    upsert_merchants,
    persist_all,
    _parse_date,
    _mask_account_number,
    BULK_INSERT_SIZE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_txn(
    description: str = "TEST TXN",
    date_str: str = "2025-06-01",
    debit: float = None,
    credit: float = None,
    balance: float = 50000.0,
    category: str = "Shopping",
    confidence: float = 0.95,
    is_recurring: bool = False,
) -> dict:
    return {
        "date": date_str,
        "description": description,
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "category": category,
        "confidence": confidence,
        "is_recurring": is_recurring,
    }


def mock_session():
    """Create a mock SQLAlchemy session."""
    session = MagicMock()
    session.bulk_save_objects = MagicMock()
    session.execute = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    return session


# ---------------------------------------------------------------------------
# Helper Function Tests
# ---------------------------------------------------------------------------

class TestHelpers:

    def test_parse_date_yyyy_mm_dd(self):
        result = _parse_date("2025-06-01")
        assert result == date(2025, 6, 1)

    def test_parse_date_dd_mm_yyyy(self):
        result = _parse_date("01-06-2025")
        assert result == date(2025, 6, 1)

    def test_parse_date_none(self):
        assert _parse_date(None) is None

    def test_parse_date_invalid(self):
        assert _parse_date("not-a-date") is None

    def test_mask_account_full(self):
        assert _mask_account_number("1234567890") == "XXXXXX7890"

    def test_mask_account_short(self):
        assert _mask_account_number("1234") == "XXXX1234"

    def test_mask_account_empty(self):
        assert _mask_account_number("") == "XXXX****"

    def test_mask_account_none(self):
        assert _mask_account_number(None) == "XXXX****"


# ---------------------------------------------------------------------------
# 1. Transaction Persistence
# ---------------------------------------------------------------------------

class TestTransactionPersistence:

    def test_basic_insert(self):
        db = mock_session()
        txns = [make_txn(debit=5000.0)]
        count = persist_transactions(db, txns, "Test User", "HDFC", "Salaried")
        assert count == 1
        db.bulk_save_objects.assert_called_once()
        db.commit.assert_called_once()

    def test_multiple_transactions(self):
        db = mock_session()
        txns = [make_txn(debit=1000.0 * i) for i in range(10)]
        count = persist_transactions(db, txns, "User", "SBI", "Business")
        assert count == 10
        db.commit.assert_called_once()

    def test_empty_list_returns_zero(self):
        db = mock_session()
        count = persist_transactions(db, [], "User", "HDFC", "Salaried")
        assert count == 0
        db.commit.assert_not_called()

    def test_preserves_is_recurring(self):
        db = mock_session()
        txns = [make_txn(debit=5000.0, is_recurring=True)]
        persist_transactions(db, txns, "User", "HDFC", "Salaried")
        # Verify bulk_save_objects was called with objects
        call_args = db.bulk_save_objects.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0].is_recurring is True

    def test_truncates_long_description(self):
        db = mock_session()
        long_desc = "A" * 1000
        txns = [make_txn(description=long_desc, debit=100.0)]
        persist_transactions(db, txns, "User", "HDFC", "Salaried")
        call_args = db.bulk_save_objects.call_args[0][0]
        assert len(call_args[0].description) <= 500


# ---------------------------------------------------------------------------
# 2. Merchant Upsert
# ---------------------------------------------------------------------------

class TestMerchantUpsert:

    def test_basic_upsert(self):
        db = mock_session()
        txns = [make_txn(description="AMAZON STORE", debit=5000.0, category="Shopping")]
        count = upsert_merchants(db, txns)
        assert count == 1
        db.execute.assert_called_once()
        db.commit.assert_called_once()

    def test_deduplicates_merchants(self):
        db = mock_session()
        txns = [
            make_txn(description="AMAZON", debit=1000.0, category="Shopping", confidence=0.90),
            make_txn(description="AMAZON", debit=2000.0, category="Shopping", confidence=0.95),
        ]
        count = upsert_merchants(db, txns)
        assert count == 1  # Same normalized name → single upsert
        db.execute.assert_called_once()

    def test_keeps_higher_confidence(self):
        db = mock_session()
        txns = [
            make_txn(description="STORE", debit=1000.0, category="Others Debit", confidence=0.80),
            make_txn(description="STORE", debit=1000.0, category="Shopping", confidence=0.95),
        ]
        count = upsert_merchants(db, txns)
        assert count == 1

    def test_empty_list_returns_zero(self):
        db = mock_session()
        count = upsert_merchants(db, [])
        assert count == 0
        db.commit.assert_not_called()

    def test_skips_no_category(self):
        db = mock_session()
        txns = [make_txn(description="TEST", debit=1000.0, category=None)]
        count = upsert_merchants(db, txns)
        assert count == 0

    def test_custom_normalize_fn(self):
        db = mock_session()
        txns = [make_txn(description="UPI/123/STORE", debit=1000.0, category="Shopping")]
        custom_fn = lambda d: d.upper().replace("UPI/123/", "")
        count = upsert_merchants(db, txns, normalize_fn=custom_fn)
        assert count == 1


# ---------------------------------------------------------------------------
# 3. Input Validation
# ---------------------------------------------------------------------------

class TestInputValidation:

    def test_non_list_raises(self):
        db = mock_session()
        with pytest.raises(ValueError, match="list"):
            persist_transactions(db, "bad", "User", "HDFC", "Salaried")


# ---------------------------------------------------------------------------
# 4. Rollback on Failure
# ---------------------------------------------------------------------------

class TestRollback:

    def test_rollback_on_commit_failure(self):
        db = mock_session()
        db.commit.side_effect = Exception("DB connection lost")
        txns = [make_txn(debit=5000.0)]
        with pytest.raises(Exception, match="DB connection lost"):
            persist_transactions(db, txns, "User", "HDFC", "Salaried")
        db.rollback.assert_called_once()

    def test_merchant_rollback_on_failure(self):
        db = mock_session()
        db.execute.side_effect = Exception("Constraint violation")
        txns = [make_txn(description="TEST", debit=1000.0, category="Shopping")]
        with pytest.raises(Exception, match="Constraint"):
            upsert_merchants(db, txns)
        db.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# 5. Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_none_debit_credit(self):
        db = mock_session()
        txns = [make_txn(debit=None, credit=None)]
        count = persist_transactions(db, txns, "User", "HDFC", "Salaried")
        assert count == 1

    def test_handles_missing_fields(self):
        db = mock_session()
        txns = [{"date": "2025-06-01"}]  # Minimal dict
        count = persist_transactions(db, txns, "User", "HDFC", "Salaried")
        assert count == 1

    def test_large_batch_splits(self):
        db = mock_session()
        txns = [make_txn(debit=100.0) for _ in range(BULK_INSERT_SIZE + 50)]
        count = persist_transactions(db, txns, "User", "HDFC", "Salaried")
        assert count == BULK_INSERT_SIZE + 50
        # Should have been called twice (500 + 50)
        assert db.bulk_save_objects.call_count == 2


# ---------------------------------------------------------------------------
# 6. Combined persist_all
# ---------------------------------------------------------------------------

class TestPersistAll:

    def test_returns_counts(self):
        db = mock_session()
        txns = [make_txn(description="STORE", debit=5000.0, category="Shopping")]
        result = persist_all(db, txns, "User", "HDFC", "Salaried")
        assert "transaction_count" in result
        assert "merchant_count" in result
        assert result["transaction_count"] == 1
        assert result["merchant_count"] == 1

    def test_empty_input(self):
        db = mock_session()
        result = persist_all(db, [], "User", "HDFC", "Salaried")
        assert result["transaction_count"] == 0
        assert result["merchant_count"] == 0
