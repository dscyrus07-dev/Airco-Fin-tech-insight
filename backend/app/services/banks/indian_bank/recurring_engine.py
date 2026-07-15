"""Indian Bank recurring detection engine."""

from __future__ import annotations

from typing import Any, Dict, List

from .._shared.generic_bank import GenericRecurringEngine


class IndianBankRecurringEngine:
    def __init__(self):
        self._delegate = GenericRecurringEngine()

    def detect(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self._delegate.detect(transactions)
