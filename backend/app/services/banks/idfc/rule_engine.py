"""
Airco Insights - IDFC Bank Rule Engine
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .._shared.category_registry import normalize_category
from .._shared.generic_bank import GenericBankConfig, GenericRuleEngine

CONFIG = GenericBankConfig(
    bank_key="idfc",
    bank_name="IDFC Bank",
    file_prefix="idfc",
    markers=["idfc first bank", "idfc bank", "statement of account", "idfb"],
    support_aliases=["idfc", "idfc bank", "idfc first", "idfc first bank"],
)

logger = logging.getLogger(__name__)


@dataclass
class RuleClassificationResult:
    category: str
    confidence: float
    source: str
    matched_rule: Optional[str] = None
    matched_keyword: Optional[str] = None


class IDFCRuleEngine:
    DEBIT_EXACT: List[Tuple[str, str, float]] = [
        ("NACH/BAJAJ FINANCE", "Loan Payment", 0.99),
        ("NACH/TVSCREDITSERVICES", "Loan Payment", 0.99),
        ("TVS CREDIT SERVICES", "Loan Payment", 0.96),
        ("NACH/SHRIRAMCITYUNIONFINA", "Loan Payment", 0.99),
        ("NACH/SHUHARITECHVENTURES", "Loan Payment", 0.96),
        ("NACH/1T9 TECHNOLOGY PVT L", "Loan Payment", 0.95),
        ("NACH/WESTERN CAPITAL ADVI", "Loan Payment", 0.96),
        ("CHARGE:AMB NON-MAINTENANCE", "Bank Charges", 0.99),
        ("CGST ON CHARGE", "Tax Payment", 0.99),
        ("SGST ON CHARGE", "Tax Payment", 0.99),
        ("IMPS-MOB/FUND TRF", "Transfer", 0.95),
        ("IMPS-INET/FUND TRF", "Transfer", 0.95),
        ("NEFT/", "Transfer", 0.94),
        ("PAY TO BHARATPE MERCHANT", "Shopping", 0.90),
        ("PAY BY WHATSAPP", "Transfer", 0.88),
        ("PAY TO R K S MOBILE SHOPPEE", "Shopping", 0.92),
        ("PAYMENT FROM PHONEPE", "Transfer", 0.90),
        ("UPI TRANSACTION FOR PPPL", "Transfer", 0.88),
        ("MANDATE REQUEST", "Transfer", 0.84),
    ]
    CREDIT_EXACT: List[Tuple[str, str, float]] = [
        ("UPI/CREDIT ADJUSTMENT", "Refund", 0.99),
        ("MONTHLY SAVINGS INTEREST CREDIT", "Interest Income", 0.99),
        ("MONTHLY SAVINGS INTEREST CREDI T", "Interest Income", 0.99),
        ("IMPS-MOB/FUND TRF", "Transfer", 0.95),
        ("IMPS-INET/FUND TRF", "Transfer", 0.95),
        ("NEFT/", "Transfer", 0.94),
        ("PAYMENT FROM PHONEPE", "Transfer", 0.90),
        ("UPI TRANSACTION FOR PPPL", "Transfer", 0.88),
        ("MANDATE REQUEST", "Transfer", 0.84),
    ]

    def __init__(self, rules_path: Optional[str] = None, keywords_file: Optional[str] = None):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        from app.services.pipeline.classification.rule_engine import (
            JsonRuleEngine,
            default_rules_path,
        )
        path = rules_path or str(default_rules_path("idfc"))
        self._engine = JsonRuleEngine(rules_path=path, bank_key="idfc")

    def classify(
        self, transactions: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return self._engine.classify(transactions)

    def get_statistics(self) -> Dict[str, Any]:
        return self._engine.get_statistics()
