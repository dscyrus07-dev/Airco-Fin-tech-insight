"""
Airco Insights — Kotak Bank Rule Engine
========================================
Deterministic classification for Kotak Mahindra Bank transactions.

Kotak-specific patterns:
- Most transactions are UPI (UPI/MerchantName/RefId/UPI)
- UPI description format: "UPI/MerchantName/RefId/Payment Type"
- Kotak UPI references: UPI-XXXXXXXXXX in Chq/Ref column
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


class KotakRuleEngine:
    """Kotak Bank-specific deterministic rule engine."""

    CONF_EXACT    = 0.99
    CONF_PATTERN  = 0.95
    CONF_MERCHANT = 0.90
    CONF_UPI      = 0.85
    CONF_AMOUNT   = 0.70

    DEBIT_RULES = {
        "ATM Withdrawal": {
            "exact": ["ATM", "CASH WITHDRAWAL", "ATM CASH", "CDM"],
            "patterns": [r"ATM.*", r"CASH.*WITHDRA.*"],
        },
        "Food": {
            "exact": [
                "SWIGGY", "ZOMATO", "DOMINOS", "KFC", "MCDONALDS",
                "PIZZA", "SUBWAY", "STARBUCKS", "CAFE", "RESTAURANT",
                "HALDIRAM", "FAASOS", "REBEL FOODS", "BIRYANI",
                "BLINKIT COMMERC",  # Blinkit grocery/food delivery
                "HYDERABAD IRANI",  # local restaurant
                "NAGORI",           # Cafe Nagori
                "PUNJAB DHA",       # Apna Punjab Dhaba
            ],
            "patterns": [
                r"UPI.*SWIGGY.*", r"UPI.*ZOMATO.*",
                r"UPI.*BLINKIT.*", r"UPI.*CAFE.*",
            ],
        },
        "Shopping": {
            "exact": [
                "AMAZON", "FLIPKART", "MYNTRA", "AJIO", "NYKAA",
                "DMART", "BIGBASKET", "ZEPTO", "JIOMART",
                "DECATHLON", "CROMA", "7 ELEVEN",
            ],
            "patterns": [
                r"UPI.*AMAZON.*", r"UPI.*FLIPKART.*",
                r"UPI.*7\s*ELEVEN.*",
            ],
        },
        "Transport": {
            "exact": [
                "UBER", "OLA", "RAPIDO", "PETROL", "DIESEL",
                "IRCTC", "METRO", "FASTAG", "TOLL",
                "REDBUS", "MAKEMYTRIP", "INDIGO",
            ],
            "patterns": [
                r"UPI.*RAPIDO.*", r"UPI.*UBER.*",
                r"UPI.*OLA.*", r"FASTAG.*",
            ],
        },
        "Bill Payment": {
            "exact": [
                "ELECTRICITY", "BROADBAND", "RECHARGE", "AIRTEL",
                "JIO", "VI", "BSNL", "PHARMACY", "HOSPITAL",
                "GST", "CBDT", "TAX",
                "MAHARASHTRA SAL",  # Maharashtra Sales Tax
            ],
            "patterns": [
                r"BILL.*PAYMENT.*", r".*RECHARGE.*",
                r".*ELECTRICITY.*", r".*PHARMACY.*",
                r"UPI.*MAHARASHTRA.*SAL.*",
            ],
        },
        "Entertainment": {
            "exact": [
                "NETFLIX", "HOTSTAR", "AMAZON PRIME",
                "ZEE5", "SPOTIFY", "GOOGLE PLAY",
            ],
            "patterns": [r"UPI.*NETFLIX.*", r"PRIME.*MEMBER.*"],
        },
        "Loan Payments": {
            "exact": ["EMI", "LOAN", "LIC HOUSING", "HOME LOAN", "BAJAJ FINANCE"],
            "patterns": [
                r"NACH.*DEBIT.*", r"ECS.*DEBIT.*", r".*EMI.*",
            ],
        },
        "Transfer": {
            "exact": ["NEFT", "RTGS", "IMPS", "UPI", "TRANSFER"],
            "patterns": [
                r"UPI/.*/.*/.*",   # UPI/MerchantName/RefId/UPI
                r"NEFT.*", r"RTGS.*", r"IMPS.*",
                r".*SENT.*PAYT.*",  # Sent using Paytm
            ],
        },
    }

    CREDIT_RULES = {
        "Salary Credits": {
            "exact": ["SALARY", "SAL", "PAYROLL", "WAGES"],
            "patterns": [r"SALARY.*", r"SAL.*CREDIT.*", r"PAYROLL.*"],
        },
        "Interest": {
            "exact": ["INTEREST", "INT", "CREDIT INTEREST"],
            "patterns": [r"INTEREST.*CREDIT.*", r".*INTEREST.*"],
        },
        "Refund": {
            "exact": ["REFUND", "REVERSAL", "CASHBACK"],
            "patterns": [r"REFUND.*", r".*REVERSAL.*", r".*CASHBACK.*"],
        },
        "Bank Transfer In": {
            "exact": ["NEFT CR", "RTGS CR", "IMPS CR"],
            "patterns": [
                r"UPI/.*/.*/.*",   # UPI credits
                r"NEFT.*CR.*", r"RTGS.*CR.*", r"IMPS.*CR.*",
                r".*RAMSUMAN.*",   # Kotak UPI credits from contacts
            ],
        },
    }

    # Kotak UPI merchant keywords in description
    UPI_MERCHANTS = {
        "swiggy": "Food",
        "zomato": "Food",
        "blinkit": "Food",
        "amazon": "Shopping",
        "flipkart": "Shopping",
        "rapido": "Transport",
        "uber": "Transport",
        "ola": "Transport",
        "netflix": "Entertainment",
        "hotstar": "Entertainment",
        "pharmeasy": "Bill Payment",
        "apollo": "Bill Payment",
    }

    def __init__(self, rules_path: Optional[str] = None, keywords_file: Optional[str] = None):
        """Phase 2b: runtime delegates to JsonRuleEngine. Tables kept for extract."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        from app.services.pipeline.classification.rule_engine import (
            JsonRuleEngine,
            default_rules_path,
        )
        path = rules_path or str(default_rules_path("kotak"))
        self._engine = JsonRuleEngine(rules_path=path, bank_key="kotak")
        self._debit_compiled = {}
        self._credit_compiled = {}

    def classify(
        self, transactions: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return self._engine.classify(transactions)

    def get_statistics(self) -> Dict[str, Any]:
        return self._engine.get_statistics()

