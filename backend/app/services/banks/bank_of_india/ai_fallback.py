"""Bank of India AI fallback wrapper."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .._shared.generic_bank import GenericAIFallback
from .structure_validator import BANK_OF_INDIA_CONFIG


class BankOfIndiaAIFallback:
    def __init__(self, api_key: Optional[str] = None):
        self._delegate = GenericAIFallback(BANK_OF_INDIA_CONFIG, api_key=api_key)

    def classify(self, transactions: List[Dict[str, Any]], bank_name: str, account_type: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        return self._delegate.classify(transactions, bank_name, account_type)
