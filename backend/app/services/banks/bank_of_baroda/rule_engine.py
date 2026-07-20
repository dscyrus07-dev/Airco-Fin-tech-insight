"""
Airco Insights — Bank of Baroda Rule Engine
============================================
Full-grade deterministic rule engine mirroring HDFCRuleEngine:
compiled debit/credit exact-keyword rules, regex patterns,
UPI merchant detection, amount-band heuristics.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .._shared.category_registry import normalize_category
from .._shared.generic_bank import GenericBankConfig, GenericRuleEngine

CONFIG = GenericBankConfig(
    bank_key="bank_of_baroda",
    bank_name="Bank of Baroda",
    file_prefix="bank_of_baroda",
    markers=["bank of baroda", "baroda", "bob", "barb0"],
    support_aliases=["bank of baroda", "bankofbaroda", "bob", "baroda"],
)

logger = logging.getLogger(__name__)


@dataclass
class RuleClassificationResult:
    category: str
    confidence: float
    source: str
    matched_rule: Optional[str] = None
    matched_keyword: Optional[str] = None


class BankOfBarodaRuleEngine:
    """Deterministic rule-based classifier for Bank of Baroda transactions."""

    DEBIT_EXACT: List[Tuple[str, str, float]] = [
        ("ATM CASH",            "ATM Withdrawal",  0.99),
        ("ATM/CASH",            "ATM Withdrawal",  0.99),
        ("CASH WITHDRAWAL",     "ATM Withdrawal",  0.99),
        ("CHARGES FOR",         "Bank Charges",    0.99),
        ("ANNUAL MAINTENANCE",  "Bank Charges",    0.99),
        ("GST CHARGES",         "Bank Charges",    0.97),
        ("CHEQUE RETURN",       "Bounce",          0.99),
        ("RETURN CHARGES",      "Bounce",          0.99),
        ("NACH BOUNCE",         "Bounce",          0.99),
        ("LIC PREMIUM",         "Insurance",       0.99),
        ("LICPREMIUM",          "Insurance",       0.99),
        ("LIC POLICY",          "Insurance",       0.99),
        ("INSURANCE",           "Insurance",       0.97),
        ("INSTALLMENT",         "Loan Payment",    0.97),
        ("LOAN REPAYMENT",      "Loan Payment",    0.97),
        ("NACH DR",             "Loan Payment",    0.95),
        ("ECS DR",              "Loan Payment",    0.95),
        ("TVSCREDITSERVICESLTD","Loan Payment",    0.99),
        ("IDFC FIRST",          "Loan Payment",    0.99),
        ("BAJAJ FINANCE",       "Loan Payment",    0.99),
        ("BAJAJ FINSERV",       "Loan Payment",    0.99),
        ("SWIGGY",              "Food",            0.99),
        ("ZOMATO",              "Food",            0.99),
        ("DOMINOS",             "Food",            0.99),
        ("MCDONALDS",           "Food",            0.99),
        ("BURGER KING",         "Food",            0.99),
        ("PIZZA HUT",           "Food",            0.99),
        ("AMAZON",              "Shopping",        0.97),
        ("FLIPKART",            "Shopping",        0.97),
        ("MYNTRA",              "Shopping",        0.97),
        ("MEESHO",              "Shopping",        0.95),
        ("NETFLIX",             "Entertainment",   0.99),
        ("HOTSTAR",             "Entertainment",   0.99),
        ("PRIME VIDEO",         "Entertainment",   0.99),
        ("SPOTIFY",             "Entertainment",   0.99),
        ("IRCTC",               "Travel",          0.99),
        ("UBER",                "Transport",       0.99),
        ("OLA",                 "Transport",       0.97),
        ("FASTAG",              "Transport",       0.99),
        ("PETROL",              "Fuel",            0.97),
        ("DIESEL",              "Fuel",            0.97),
        ("FUEL",                "Fuel",            0.97),
        ("HPCL",                "Fuel",            0.99),
        ("BPCL",                "Fuel",            0.99),
        ("IOCL",                "Fuel",            0.99),
        ("INDIAN OIL",          "Fuel",            0.99),
        ("ELECTRICITY",         "Bill Payment",    0.99),
        ("AIRTEL",              "Bill Payment",    0.97),
        ("JIO",                 "Bill Payment",    0.97),
        ("BROADBAND",           "Bill Payment",    0.97),
        ("DIVIDEND",            "Investment",      0.95),
        ("MONTHLY TRANSFER",    "Transfer",        0.99),
        ("SELF TRANSFER",       "Transfer",        0.99),
    ]

    CREDIT_EXACT: List[Tuple[str, str, float]] = [
        ("SALARY",          "Salary",         0.99),
        ("SAL CR",          "Salary",         0.99),
        ("PAYROLL",         "Salary",         0.99),
        ("BY CASH",         "Cash Deposit",   0.99),
        ("CASH DEPOSIT",    "Cash Deposit",   0.99),
        ("REVERSAL",        "Refund",         0.97),
        ("REFUND",          "Refund",         0.97),
        ("CASHBACK",        "Refund",         0.95),
        ("INT CR",          "Interest",       0.99),
        ("INTEREST CREDIT", "Interest",       0.99),
        ("LOAN",            "Loan Credit",    0.90),
        ("DISBURSAL",       "Loan Credit",    0.97),
        ("DIVIDEND",        "Investment",     0.97),
    ]

    UPI_FOOD     = {"swiggy", "zomato", "dominos", "mcdonalds", "pizza"}
    UPI_SHOPPING = {"amazon", "flipkart", "myntra", "meesho", "snapdeal"}
    UPI_TRAVEL   = {"irctc", "makemytrip", "goibibo", "redbus"}
    UPI_FUEL     = {"petrol", "diesel", "fuel", "hpcl", "bpcl", "iocl"}

    def __init__(self, rules_path: Optional[str] = None, keywords_file: Optional[str] = None):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        from app.services.pipeline.classification.rule_engine import (
            JsonRuleEngine,
            default_rules_path,
        )
        path = rules_path or str(default_rules_path("bank_of_baroda"))
        self._engine = JsonRuleEngine(rules_path=path, bank_key="bank_of_baroda")
        self._stats = {"total": 0, "classified": 0, "unclassified": 0}

    def classify(
        self, transactions: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        classified, unclassified = self._engine.classify(transactions)
        self._stats["total"] += len(transactions)
        self._stats["classified"] += len(classified)
        self._stats["unclassified"] += len(unclassified)
        return classified, unclassified

    def get_statistics(self) -> Dict[str, Any]:
        total = self._stats["total"] or 1
        return {
            "total": self._stats["total"],
            "classified": self._stats["classified"],
            "unclassified": self._stats["unclassified"],
            "classification_rate": round(self._stats["classified"] / total * 100, 1),
        }
