"""
Airco Insights — ICICI Bank Rule Engine
========================================
Deterministic classification for ICICI Bank transactions.

ICICI-specific prefixes:
- UPI/VPA@bank/   — UPI transfers (credit/debit)
- NEFT/           — NEFT transfers
- B/F             — Opening balance (not a transaction)
- ECS             — ECS/mandate debits
- ATM             — ATM withdrawals
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    category: str
    confidence: float
    source: str
    matched_rule: Optional[str] = None
    matched_keyword: Optional[str] = None


class ICICIRuleEngine:
    """ICICI Bank-specific deterministic rule engine."""

    CONF_EXACT    = 0.99
    CONF_PATTERN  = 0.95
    CONF_MERCHANT = 0.90
    CONF_UPI      = 0.85
    CONF_AMOUNT   = 0.70

    DEBIT_RULES = {
        "ATM Withdrawal": {
            "exact": [
                "ATM", "CASH WITHDRAWAL", "ATM CASH", "ATM WDL",
                "ATM-WDL", "CASHWDL", "ATM WITHDL",
            ],
            "patterns": [
                r"ATM.*",
                r"CASH.*WITHDRA.*",
            ],
        },
        "Food": {
            "exact": [
                "SWIGGY", "ZOMATO", "DOMINOS", "MCDONALDS", "KFC",
                "PIZZA", "SUBWAY", "STARBUCKS", "CAFE", "RESTAURANT",
                "HALDIRAM", "FAASOS", "REBEL FOODS", "BIRYANI",
            ],
            "patterns": [
                r"UPI.*SWIGGY.*",
                r"UPI.*ZOMATO.*",
            ],
        },
        "Shopping": {
            "exact": [
                "AMAZON", "FLIPKART", "MYNTRA", "AJIO", "NYKAA",
                "DMART", "BIGBASKET", "BLINKIT", "ZEPTO", "JIOMART",
                "DECATHLON", "CROMA", "VIJAY SALES",
            ],
            "patterns": [
                r"UPI.*AMAZON.*",
                r"UPI.*FLIPKART.*",
            ],
        },
        "Transport": {
            "exact": [
                "UBER", "OLA", "RAPIDO", "PETROL", "DIESEL",
                "IRCTC", "METRO", "FASTAG", "TOLL",
                "REDBUS", "MAKEMYTRIP", "INDIGO", "SPICEJET",
            ],
            "patterns": [
                r"UPI.*UBER.*",
                r"UPI.*OLA.*",
                r"FASTAG.*",
                r"IRCTC.*",
            ],
        },
        "Bill Payment": {
            "exact": [
                "ELECTRICITY", "WATER", "GAS", "BROADBAND",
                "RECHARGE", "AIRTEL", "JIO", "VI", "BSNL",
                "PHARMACY", "APOLLO", "MEDPLUS", "HOSPITAL",
                "GST", "CBDT", "TDS", "INCOME TAX",
            ],
            "patterns": [
                r"BILL.*PAYMENT.*",
                r".*RECHARGE.*",
                r".*ELECTRICITY.*",
                r".*PHARMACY.*",
            ],
        },
        "Entertainment": {
            "exact": [
                "NETFLIX", "HOTSTAR", "AMAZON PRIME", "DISNEY",
                "SONYLIV", "ZEE5", "SPOTIFY", "GAANA",
            ],
            "patterns": [
                r"UPI.*NETFLIX.*",
                r"PRIME.*MEMBER.*",
            ],
        },
        "Loan Payments": {
            "exact": [
                "EMI", "LOAN", "LIC HOUSING", "HOME LOAN",
                "BAJAJ FINANCE",
            ],
            "patterns": [
                r"ECS.*DEBIT.*",
                r"NACH.*DEBIT.*",
                r".*EMI.*",
                r"ACH.*DR.*",
            ],
        },
        "Transfer": {
            "exact": ["NEFT", "RTGS", "IMPS", "UPI", "TRANSFER"],
            "patterns": [
                r"UPI/.*@.*",
                r"NEFT.*",
                r"RTGS.*",
                r"IMPS.*",
            ],
        },
    }

    CREDIT_RULES = {
        "Salary Credits": {
            "exact": ["SALARY", "SAL", "PAYROLL", "WAGES"],
            "patterns": [
                r"SALARY.*",
                r"SAL.*CREDIT.*",
                r"PAYROLL.*",
            ],
        },
        "Interest": {
            "exact": ["INTEREST", "INT", "INT.PD", "CREDIT INTEREST"],
            "patterns": [
                r"INTEREST.*CREDIT.*",
                r".*INTEREST.*",
            ],
        },
        "Refund": {
            "exact": ["REFUND", "REVERSAL", "CASHBACK", "NEFT RETURN"],
            "patterns": [
                r"REFUND.*",
                r".*REVERSAL.*",
                r"NEFT.*RETURN.*",
            ],
        },
        "Bank Transfer In": {
            "exact": ["NEFT CR", "RTGS CR", "IMPS CR"],
            "patterns": [
                r"UPI/.*@.*/.*",
                r"NEFT.*CR.*",
                r"RTGS.*CR.*",
                r"IMPS.*CR.*",
            ],
        },
    }

    UPI_MERCHANTS = {
        "swiggy": "Food",
        "zomato": "Food",
        "amazon": "Shopping",
        "flipkart": "Shopping",
        "uber": "Transport",
        "ola": "Transport",
        "netflix": "Entertainment",
        "hotstar": "Entertainment",
    }

    def __init__(self, rules_path: Optional[str] = None, keywords_file: Optional[str] = None):
        """Phase 2b: runtime delegates to JsonRuleEngine. Tables kept for extract."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        from app.services.pipeline.classification.rule_engine import (
            JsonRuleEngine,
            default_rules_path,
        )
        path = rules_path or str(default_rules_path("icici"))
        self._engine = JsonRuleEngine(rules_path=path, bank_key="icici")
        self._debit_compiled = {}
        self._credit_compiled = {}

    def classify(
        self, transactions: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return self._engine.classify(transactions)

    def get_statistics(self) -> Dict[str, Any]:
        return self._engine.get_statistics()

