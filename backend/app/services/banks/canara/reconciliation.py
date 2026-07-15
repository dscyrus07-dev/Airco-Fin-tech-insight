"""Phase 3: Canara reconciliation wraps shared pipeline.reconciliation."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.services.pipeline.reconciliation.engine import (
    ReconciliationMismatch,
    SharedReconciliationResult,
    auto_correct_debit_credit as _shared_auto_correct,
    compute_reconciliation,
)

logger = logging.getLogger(__name__)


class CanaraReconciliationError(Exception):
    def __init__(self, message: str, error_code: str, details: dict = None):
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


@dataclass
class CanaraReconciliationResult:
    is_reconciled: bool
    opening_balance: float
    closing_balance: float
    total_credits: float
    total_debits: float
    calculated_closing: float
    final_difference: float
    transaction_count: int
    mismatches: List[ReconciliationMismatch] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "is_reconciled": self.is_reconciled,
            "opening_balance": self.opening_balance,
            "closing_balance": self.closing_balance,
            "total_credits": self.total_credits,
            "total_debits": self.total_debits,
            "calculated_closing": self.calculated_closing,
            "final_difference": self.final_difference,
            "transaction_count": self.transaction_count,
            "mismatch_count": len(self.mismatches),
            "passed": self.is_reconciled,
        }

    @classmethod
    def from_shared(cls, shared: SharedReconciliationResult) -> "CanaraReconciliationResult":
        return cls(
            is_reconciled=shared.is_reconciled,
            opening_balance=shared.opening_balance,
            closing_balance=shared.closing_balance,
            total_credits=shared.total_credits,
            total_debits=shared.total_debits,
            calculated_closing=shared.calculated_closing,
            final_difference=shared.final_difference,
            transaction_count=shared.transaction_count,
            mismatches=list(shared.mismatches),
        )


class CanaraReconciliation:
    TOLERANCE = 0.01

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def reconcile(
        self,
        transactions: List[Dict[str, Any]],
        expected_opening: Optional[float] = None,
        expected_closing: Optional[float] = None,
        expected_credits: Optional[float] = None,
        expected_debits: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not transactions:
            return {
                "passed": True,
                "opening_balance": 0,
                "closing_balance": 0,
                "total_credits": 0,
                "total_debits": 0,
                "mismatch_count": 0,
            }
        self.logger.info("Reconciling %d Canara transactions", len(transactions))
        shared = compute_reconciliation(
            transactions,
            expected_opening=expected_opening,
            expected_closing=expected_closing,
            expected_credits=expected_credits,
            expected_debits=expected_debits,
            tolerance=self.TOLERANCE,
        )
        result = CanaraReconciliationResult.from_shared(shared)
        self.logger.info(
            "Canara reconciliation %s: open=%.2f close=%.2f calc=%.2f diff=%.2f mismatches=%d",
            "PASSED" if result.is_reconciled else "FAILED",
            result.opening_balance,
            result.closing_balance,
            result.calculated_closing,
            result.final_difference,
            len(result.mismatches),
        )
        if not result.is_reconciled and self.strict_mode:
            if result.mismatches:
                m = result.mismatches[0]
                raise CanaraReconciliationError(
                    f"Balance mismatch at txn {m.transaction_index}: "
                    f"expected {m.expected_balance:.2f}, got {m.actual_balance:.2f}",
                    error_code="BALANCE_MISMATCH",
                    details={
                        "transaction_index": m.transaction_index,
                        "expected": m.expected_balance,
                        "actual": m.actual_balance,
                    },
                )
            raise CanaraReconciliationError(
                f"Final balance mismatch: calc={result.calculated_closing:.2f} "
                f"actual={result.closing_balance:.2f}",
                error_code="FINAL_BALANCE_MISMATCH",
                details={
                    "calculated": result.calculated_closing,
                    "actual": result.closing_balance,
                },
            )
        return result.to_dict()

    def auto_correct_debit_credit(
        self, transactions: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], int]:
        return _shared_auto_correct(transactions, tolerance=self.TOLERANCE)


__all__ = [
    "CanaraReconciliationError",
    "ReconciliationMismatch",
    "CanaraReconciliationResult",
    "CanaraReconciliation",
]
