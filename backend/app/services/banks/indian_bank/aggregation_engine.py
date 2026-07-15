"""Indian Bank aggregation engine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .._shared.generic_bank import GenericAggregationEngine


class IndianBankAggregationEngine:
    def __init__(self):
        self._delegate = GenericAggregationEngine()

    def aggregate(self, transactions: List[Dict[str, Any]], opening: Optional[float], closing: Optional[float]) -> Dict[str, Any]:
        return self._delegate.aggregate(transactions, opening, closing)
