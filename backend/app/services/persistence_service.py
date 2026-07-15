"""Legacy persistence helpers kept for compatibility with older tests.

This module provides a small SQLAlchemy-based API for persisting transaction
rows and merchant categorizations. The production code now uses newer service
paths, but a number of tests still import these helpers directly.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, date
from typing import Any, Callable, Iterable, Mapping

from sqlalchemy.dialects.postgresql import insert

from app.database.models import Merchant, Transaction

BULK_INSERT_SIZE = 500


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None

    if isinstance(value, date):
        return value

    if isinstance(value, datetime):
        return value.date()

    if not isinstance(value, str):
        return None

    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _mask_account_number(account_number: Any) -> str:
    if not account_number:
        return "XXXX****"

    account_text = str(account_number).strip()
    if not account_text:
        return "XXXX****"

    last_four = account_text[-4:]
    prefix_length = max(4, len(account_text) - 4)
    return f"{'X' * prefix_length}{last_four}"


def _normalize_description(description: Any, normalize_fn: Callable[[str], str] | None = None) -> str:
    raw = "" if description is None else str(description)
    if normalize_fn is not None:
        return normalize_fn(raw).strip()
    return raw.strip().upper()


def _build_transaction_row(
    txn: Mapping[str, Any],
    user_name: str,
    bank_name: str,
    account_type: str,
) -> Transaction:
    description = str(txn.get("description") or "")[:500]
    return Transaction(
        user_name=user_name,
        bank_name=bank_name,
        account_type=account_type,
        date=_parse_date(txn.get("date")),
        description=description,
        debit=txn.get("debit"),
        credit=txn.get("credit"),
        balance=txn.get("balance"),
        category=txn.get("category"),
        confidence=txn.get("confidence"),
        is_recurring=bool(txn.get("is_recurring", False)),
    )


def persist_transactions(
    db,
    transactions: list[Mapping[str, Any]],
    user_name: str,
    bank_name: str,
    account_type: str,
) -> int:
    if not isinstance(transactions, list):
        raise ValueError("transactions must be a list")

    if not transactions:
        return 0

    persisted = 0
    try:
        for start in range(0, len(transactions), BULK_INSERT_SIZE):
            batch = transactions[start : start + BULK_INSERT_SIZE]
            rows = [
                _build_transaction_row(txn, user_name=user_name, bank_name=bank_name, account_type=account_type)
                for txn in batch
            ]
            db.bulk_save_objects(rows)
            persisted += len(rows)
        db.commit()
        return persisted
    except Exception:
        db.rollback()
        raise


def upsert_merchants(
    db,
    transactions: Iterable[Mapping[str, Any]],
    normalize_fn: Callable[[str], str] | None = None,
) -> int:
    if not transactions:
        return 0

    deduped: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for txn in transactions:
        category = txn.get("category")
        if not category:
            continue

        normalized_name = _normalize_description(txn.get("description"), normalize_fn)
        if not normalized_name:
            continue

        confidence = float(txn.get("confidence") or 0.0)
        current = deduped.get(normalized_name)
        if current is None or confidence >= current["confidence"]:
            deduped[normalized_name] = {
                "normalized_name": normalized_name,
                "category": category,
                "confidence": confidence,
            }

    if not deduped:
        return 0

    try:
        merchant_rows = list(deduped.values())
        stmt = insert(Merchant).values(merchant_rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Merchant.normalized_name],
            set_={
                "category": stmt.excluded.category,
                "confidence": stmt.excluded.confidence,
            },
        )
        db.execute(stmt)
        db.commit()
        return len(merchant_rows)
    except Exception:
        db.rollback()
        raise


def persist_all(
    db,
    transactions: list[Mapping[str, Any]],
    user_name: str,
    bank_name: str,
    account_type: str,
) -> dict[str, int]:
    transaction_count = persist_transactions(db, transactions, user_name, bank_name, account_type)
    merchant_count = upsert_merchants(db, transactions)
    return {
        "transaction_count": transaction_count,
        "merchant_count": merchant_count,
    }
