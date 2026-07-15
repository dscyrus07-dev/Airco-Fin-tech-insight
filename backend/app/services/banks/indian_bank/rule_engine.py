"""Indian Bank rule engine."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .indian_bank_classifier import IndianBankClassifier


class IndianBankRuleEngine:
    def __init__(self, keywords_file: str | None = None):
        self.classifier = IndianBankClassifier(keywords_file=keywords_file)

    def classify(self, transactions: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return self.classifier.classify(transactions)

    def get_statistics(self) -> Dict[str, Any]:
        return self.classifier.get_statistics()
