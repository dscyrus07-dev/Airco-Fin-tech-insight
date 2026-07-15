"""Bank of India transaction validator."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .._shared.generic_bank import GenericTransactionValidator, GenericValidationError


class BankOfIndiaTransactionValidator:
    def __init__(self, strict_mode: bool = True):
        self._delegate = GenericTransactionValidator(strict_mode=strict_mode)

    def validate(self, transactions: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        return self._delegate.validate(transactions)


BankOfIndiaValidationError = GenericValidationError
