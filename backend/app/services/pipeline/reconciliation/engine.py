"""Shared balance reconciliation core (Phase 3 + accuracy repair).

Core math: opening + credits - debits, progression check.
repair_transaction_sides: optional debit/credit correction from balance delta
(sign-off: RECON-HIGH-MISMATCH accuracy work).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


DEFAULT_TOLERANCE = 0.01


@dataclass
class ReconciliationMismatch:
    transaction_index: int
    expected_balance: float
    actual_balance: float
    difference: float
    previous_balance: float
    transaction_amount: float
    is_debit: bool


@dataclass
class SharedReconciliationResult:
    is_reconciled: bool
    opening_balance: float
    closing_balance: float
    total_credits: float
    total_debits: float
    calculated_closing: float
    final_difference: float
    transaction_count: int
    mismatches: List[ReconciliationMismatch] = field(default_factory=list)

    def to_dict(self, *, include_passed: bool = False) -> dict:
        out = {
            "is_reconciled": self.is_reconciled,
            "opening_balance": self.opening_balance,
            "closing_balance": self.closing_balance,
            "total_credits": self.total_credits,
            "total_debits": self.total_debits,
            "calculated_closing": self.calculated_closing,
            "final_difference": self.final_difference,
            "transaction_count": self.transaction_count,
            "mismatch_count": len(self.mismatches),
        }
        if include_passed:
            out["passed"] = self.is_reconciled
        return out


def _num(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _opt_num(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def check_balance_progression(
    transactions: Sequence[Dict[str, Any]],
    *,
    tolerance: float = DEFAULT_TOLERANCE,
) -> List[ReconciliationMismatch]:
    """prev_balance + credit - debit == curr_balance (per row after first)."""
    mismatches: List[ReconciliationMismatch] = []
    for i in range(1, len(transactions)):
        prev = transactions[i - 1]
        curr = transactions[i]
        prev_balance = _num(prev.get("balance"))
        curr_balance = _num(curr.get("balance"))
        credit = _num(curr.get("credit"))
        debit = _num(curr.get("debit"))
        expected_balance = prev_balance + credit - debit
        diff = abs(expected_balance - curr_balance)
        if diff > tolerance:
            mismatches.append(
                ReconciliationMismatch(
                    transaction_index=i,
                    expected_balance=expected_balance,
                    actual_balance=curr_balance,
                    difference=diff,
                    previous_balance=prev_balance,
                    transaction_amount=credit if credit else debit,
                    is_debit=debit > 0,
                )
            )
    return mismatches


def compute_reconciliation(
    transactions: Sequence[Dict[str, Any]],
    *,
    expected_opening: Optional[float] = None,
    expected_closing: Optional[float] = None,
    expected_credits: Optional[float] = None,
    expected_debits: Optional[float] = None,
    tolerance: float = DEFAULT_TOLERANCE,
) -> SharedReconciliationResult:
    del expected_closing
    txns = list(transactions)
    total_credits = sum(_num(t.get("credit")) for t in txns)
    total_debits = sum(_num(t.get("debit")) for t in txns)

    first = txns[0]
    first_balance = _num(first.get("balance"))
    first_credit = _num(first.get("credit"))
    first_debit = _num(first.get("debit"))
    inferred_opening = first_balance - first_credit + first_debit
    opening_balance = (
        float(expected_opening) if expected_opening is not None else inferred_opening
    )
    closing_balance = _num(txns[-1].get("balance"))
    calculated_closing = opening_balance + total_credits - total_debits
    final_diff = abs(calculated_closing - closing_balance)
    mismatches = check_balance_progression(txns, tolerance=tolerance)
    is_reconciled = (final_diff <= tolerance) and not mismatches

    _ = expected_credits
    _ = expected_debits

    return SharedReconciliationResult(
        is_reconciled=is_reconciled,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        total_credits=total_credits,
        total_debits=total_debits,
        calculated_closing=calculated_closing,
        final_difference=final_diff,
        transaction_count=len(txns),
        mismatches=mismatches,
    )


def auto_correct_debit_credit(
    transactions: Sequence[Dict[str, Any]],
    *,
    tolerance: float = DEFAULT_TOLERANCE,
) -> Tuple[List[Dict[str, Any]], int]:
    """Swap debit/credit when balance progression improves (legacy helper)."""
    corrected: List[Dict[str, Any]] = []
    corrections = 0
    for i, txn in enumerate(transactions):
        txn_copy = dict(txn)
        if i == 0:
            corrected.append(txn_copy)
            continue
        prev_balance = _num(corrected[i - 1].get("balance"))
        curr_balance = _num(txn.get("balance"))
        debit = _num(txn.get("debit"))
        credit = _num(txn.get("credit"))
        if debit:
            expected = prev_balance - debit
        else:
            expected = prev_balance + credit
        diff = abs(expected - curr_balance)
        if diff > tolerance:
            if debit:
                new_expected = prev_balance + debit
            else:
                new_expected = prev_balance - credit
            new_diff = abs(new_expected - curr_balance)
            if new_diff < diff:
                txn_copy["debit"] = credit if credit else None
                txn_copy["credit"] = debit if debit else None
                corrections += 1
        corrected.append(txn_copy)
    return corrected, corrections


def repair_transaction_sides(
    transactions: Sequence[Dict[str, Any]],
    *,
    opening_balance: Optional[float] = None,
    tolerance: float = DEFAULT_TOLERANCE,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Repair debit/credit sides so running balance holds when possible.

    Order of attempts per row:
    1. Keep as-is if progression already matches.
    2. Swap debit/credit if that matches (legacy auto_correct).
    3. Set amount from balance delta (parse amount/side errors).

    Returns (corrected_transactions, stats).
    """
    stats = {"swap": 0, "delta_repair": 0, "unchanged": 0, "unfixed": 0}
    if not transactions:
        return [], stats

    corrected: List[Dict[str, Any]] = []
    first = transactions[0]
    if opening_balance is None:
        opening_balance = (
            _num(first.get("balance"))
            - _num(first.get("credit"))
            + _num(first.get("debit"))
        )

    for i, txn in enumerate(transactions):
        txn_copy = dict(txn)
        prev = float(opening_balance) if i == 0 else _num(corrected[i - 1].get("balance"))
        bal = _opt_num(txn.get("balance"))
        debit = _num(txn.get("debit"))
        credit = _num(txn.get("credit"))

        if bal is None:
            stats["unchanged"] += 1
            corrected.append(txn_copy)
            continue

        expected = prev + credit - debit
        if abs(expected - bal) <= tolerance:
            stats["unchanged"] += 1
            corrected.append(txn_copy)
            continue

        # 2) swap
        swap_expected = prev + debit - credit
        if abs(swap_expected - bal) <= tolerance and (debit or credit):
            txn_copy["debit"] = credit if credit else None
            txn_copy["credit"] = debit if debit else None
            stats["swap"] += 1
            corrected.append(txn_copy)
            continue

        # 3) balance-delta repair
        delta = bal - prev
        if abs(delta) <= tolerance:
            # balance unchanged: clear both sides if they had amounts
            if debit or credit:
                txn_copy["debit"] = None
                txn_copy["credit"] = None
                stats["delta_repair"] += 1
            else:
                stats["unchanged"] += 1
            corrected.append(txn_copy)
            continue

        if delta > 0:
            new_credit = round(delta, 2)
            new_debit = None
            trial = prev + new_credit
        else:
            new_debit = round(-delta, 2)
            new_credit = None
            trial = prev - new_debit

        if abs(trial - bal) <= tolerance:
            txn_copy["debit"] = new_debit
            txn_copy["credit"] = new_credit
            stats["delta_repair"] += 1
        else:
            stats["unfixed"] += 1
        corrected.append(txn_copy)

    return corrected, stats
