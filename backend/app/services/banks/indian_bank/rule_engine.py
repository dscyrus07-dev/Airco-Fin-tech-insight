"""Indian Bank rule engine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .indian_bank_classifier import IndianBankClassifier


class IndianBankRuleEngine:
    def __init__(self, keywords_file: str | None = None, rules_path: Optional[str] = None):
        self.logger = __import__("logging").getLogger(__name__)
        from app.services.pipeline.classification.rule_engine import (
            JsonRuleEngine,
            default_rules_path,
        )
        path = rules_path or str(default_rules_path("indian_bank"))
        self._engine = JsonRuleEngine(rules_path=path, bank_key="indian_bank")
        self.classifier = IndianBankClassifier(keywords_file=keywords_file)

    def classify(self, transactions: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return self._engine.classify(transactions)

    def get_statistics(self) -> Dict[str, Any]:
        return self._engine.get_statistics()
