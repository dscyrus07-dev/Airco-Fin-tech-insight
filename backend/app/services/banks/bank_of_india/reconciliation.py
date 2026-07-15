"""Bank of India reconciliation engine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .._shared.generic_bank import GenericReconciliation, GenericReconciliationError


class BankOfIndiaReconciliation:
    def __init__(self, strict_mode: bool = True):
        self._delegate = GenericReconciliation(strict_mode=strict_mode)

    def reconcile(
        self,
        transactions: List[Dict[str, Any]],
        opening: Optional[float] = None,
        closing: Optional[float] = None,
        expected_opening: Optional[float] = None,
        expected_closing: Optional[float] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        resolved_opening = expected_opening if expected_opening is not None else opening
        resolved_closing = expected_closing if expected_closing is not None else closing
        return self._delegate.reconcile(transactions, resolved_opening, resolved_closing)


BankOfIndiaReconciliationError = GenericReconciliationError
