"""Bank of India rule engine."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .bank_of_india_classifier import BankOfIndiaClassifier


class BankOfIndiaRuleEngine:
    def __init__(self, keywords_file: str | None = None):
        self.classifier = BankOfIndiaClassifier(keywords_file=keywords_file)

    def classify(self, transactions: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return self.classifier.classify(transactions)

    def get_statistics(self) -> Dict[str, Any]:
        return self.classifier.get_statistics()
