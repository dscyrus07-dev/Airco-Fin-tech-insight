from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .._shared.category_registry import normalize_category
from .._shared.generic_bank import GenericBankConfig, GenericClassifier, GenericRuleEngine


CONFIG = GenericBankConfig(
    bank_key="karnataka",
    bank_name="Karnataka Bank",
    file_prefix="karnataka",
    markers=["karnataka bank", "statement for a/c", "karb"],
    support_aliases=["karnataka", "karnataka bank"],
)


@dataclass
class RuleClassificationResult:
    category: str
    confidence: float
    source: str
    matched_rule: Optional[str] = None
    matched_keyword: Optional[str] = None


class KarnatakaRuleEngine:
    DEBIT_EXACT: List[Tuple[str, str, float]] = [
        ("NFS-CWDR/", "ATM Withdrawal", 0.98),
        ("CONS. QTRLY SMS CHRGS", "Bank Charges", 0.99),
        ("AVG BAL CHRG", "Bank Charges", 0.99),
        ("AVG/MIN BAL CHRG", "Bank Charges", 0.99),
        ("SMS CHRGS", "Bank Charges", 0.99),
        ("ONECARD@IDFCBANK", "Credit Card Payment", 0.92),
        ("AMAZONPAY@APL", "Shopping", 0.88),
        ("MBS/TO ", "Transfer", 0.94),
        ("TRANSFER TO ", "Transfer", 0.95),
        ("SENT FROM", "Transfer", 0.88),
        ("PAYMENT FROM", "Transfer", 0.88),
        ("REQUEST", "Transfer", 0.82),
        ("WALLETMONEYTOBANK@PAYTM", "Transfer", 0.95),
        ("KMBL A/C", "Transfer", 0.90),
        ("PAYTM", "Transfer", 0.82),
        ("WAHDFCBANK", "Transfer", 0.85),
        ("NA-KB", "Transfer", 0.80),
        ("IMPS/P2A-", "Transfer", 0.92),
    ]
    CREDIT_EXACT: List[Tuple[str, str, float]] = [
        ("DEBITREVERSAL", "Refund", 0.99),
        ("BY CASH-", "Business Income", 0.99),
        ("BY CASH-BNA", "Business Income", 0.99),
        ("BY CASH SELF", "Business Income", 0.99),
        ("PAYOUTS@PAYTM", "Business Income", 0.95),
        ("CF.PAYOUT@ICICI", "Business Income", 0.95),
        ("CASHFREEPAYOUT@IDFCBANK", "Business Income", 0.95),
        ("NEFT-NEXTBILLION TECHNOLOGY", "Business Income", 0.96),
        ("SB INT ", "Interest Income", 0.99),
        ("TWIDPAY5.PAYU@INDUS", "Cashback", 0.90),
        ("WALLETMONEYTOBANK@PAYTM", "Transfer", 0.95),
        ("KMBL A/C", "Transfer", 0.90),
        ("PAYTM", "Transfer", 0.82),
        ("WAHDFCBANK", "Transfer", 0.85),
        ("NA-KB", "Transfer", 0.80),
        ("PAYMENT FROM", "Transfer", 0.88),
        ("REQUEST", "Transfer", 0.82),
        ("IMPS/P2A-", "Transfer", 0.92),
    ]

    def __init__(self, rules_path: Optional[str] = None, keywords_file: Optional[str] = None):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        from app.services.pipeline.classification.rule_engine import (
            JsonRuleEngine,
            default_rules_path,
        )
        path = rules_path or str(default_rules_path("karnataka"))
        self._engine = JsonRuleEngine(rules_path=path, bank_key="karnataka")

    def classify(
        self, transactions: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return self._engine.classify(transactions)

    def get_statistics(self) -> Dict[str, Any]:
        return self._engine.get_statistics()


class KarnatakaClassifier(GenericClassifier):
    def __init__(self, keywords_file: Optional[str] = None):
        super().__init__(CONFIG, keywords_file=keywords_file)
        self._rule_engine = KarnatakaRuleEngine()

    def classify(self, transactions):
        """Accept either a single row dict (report_generator_base style)
        or a list of transactions (standard style).
        Always returns a result compatible with report_generator_base."""
        if isinstance(transactions, dict):
            # Single-row call from report_generator_base
            classified, unclassified = self._rule_engine.classify([transactions])
            pool = classified if classified else unclassified
            if pool:
                row = pool[0]
                cat = row.get("category", "Others")
                return {
                    "category": cat,
                    "display_category": cat,
                    "internal_category": cat.upper().replace(" ", "_"),
                    "confidence_score": int(float(row.get("confidence", 0.5)) * 100),
                    "confidence": row.get("confidence", 0.5),
                    "source": row.get("source", "rule_engine"),
                    "matched_rule": row.get("matched_rule"),
                    "matched_keyword": row.get("matched_keyword"),
                }
            cat = "Others Debit" if transactions.get("debit") else "Others Credit"
            return {
                "category": cat,
                "display_category": cat,
                "internal_category": cat.upper().replace(" ", "_"),
                "confidence_score": 50,
                "confidence": 0.5,
                "source": "rule_engine",
                "matched_rule": "default",
            }
        # List call — use rule engine for each
        return self._rule_engine.classify(transactions)

