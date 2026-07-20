"""
Airco Insights - Unknown Bank Rule Engine
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .._shared.category_registry import normalize_category
from .._shared.generic_bank import GenericBankConfig, GenericRuleEngine

CONFIG = GenericBankConfig(
    bank_key="unknown",
    bank_name="Unknown",
    file_prefix="unknown",
    markers=[],
    support_aliases=["unknown", "unknown bank"],
)

logger = logging.getLogger(__name__)


@dataclass
class RuleClassificationResult:
    category: str
    confidence: float
    source: str
    matched_rule: Optional[str] = None
    matched_keyword: Optional[str] = None


class UnknownRuleEngine:
    DEBIT_EXACT: List[Tuple[str, str, float]] = [
        ("CHRG:DEBITCARDANNUALFEE", "Bank Charges", 0.99),
        ("REMCHRGS:POSDECL", "Bank Charges", 0.99),
        ("REMCHRGS:DEBITCARDANNUALFEE", "Bank Charges", 0.99),
        ("UPI/", "Transfer", 0.90),
    ]
    CREDIT_EXACT: List[Tuple[str, str, float]] = [
        ("TDINT:", "Interest Income", 0.99),
        ("RECD:IMPS/", "Transfer", 0.96),
        ("UPI/", "Transfer", 0.90),
        ("PAYMENT FROM PHONEPE", "Transfer", 0.92),
    ]

    def __init__(self, rules_path: Optional[str] = None, keywords_file: Optional[str] = None):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        from app.services.pipeline.classification.rule_engine import (
            JsonRuleEngine,
            default_rules_path,
        )
        path = rules_path or str(default_rules_path("unknown"))
        self._engine = JsonRuleEngine(rules_path=path, bank_key="unknown")

    def classify(
        self, transactions: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return self._engine.classify(transactions)

    def get_statistics(self) -> Dict[str, Any]:
        return self._engine.get_statistics()
