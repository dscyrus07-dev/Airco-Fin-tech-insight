"""
Airco Insights - SBI Bank Rule Engine
=====================================
Deterministic classification for SBI transactions with SBI-specific keywords
and a shared generic-bank fallback.
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .._shared.generic_bank import GenericBankConfig, GenericRuleEngine

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    category: str
    confidence: float
    source: str
    matched_rule: Optional[str] = None
    matched_keyword: Optional[str] = None


class SBIRuleEngine:
    """SBI-specific deterministic rule engine."""

    BANK_KEYWORDS_FILE_CANDIDATES = [
        str(Path(__file__).resolve().parents[5] / "samples" / "sbi" / "output" / "words.json"),
        "/app/keywords.json",
        "/app/words.json",
        str(Path(__file__).resolve().parents[5] / "backend" / "words.json"),
        str(Path(__file__).resolve().parents[5] / "keywords.json"),
    ]

    CONF_EXACT = 0.99
    CONF_PATTERN = 0.95
    CONF_MERCHANT = 0.90
    CONF_UPI = 0.85
    CONF_AMOUNT = 0.70

    DEBIT_RULES = {
        "ATM Withdrawal": {
            "exact": ["ATM", "CASH WITHDRAWAL", "ATM CASH", "CDM"],
            "patterns": [r"ATM.*", r"CASH.*WITHDRA.*", r".*KOTHAWADA.*", r".*HANAMKONDA.*", r".*NALGONDA.*"],
        },
        "Food": {
            "exact": [
                "SWIGGY", "ZOMATO", "DOMINOS", "KFC", "MCDONALDS",
                "PIZZA", "SUBWAY", "STARBUCKS", "CAFE", "RESTAURANT",
                "HALDIRAM", "FAASOS", "REBEL FOODS", "BIRYANI",
                "BLINKIT COMMERC", "HYDERABAD IRANI", "NAGORI", "PUNJAB DHA",
            ],
            "patterns": [
                r"UPI.*SWIGGY.*", r"UPI.*ZOMATO.*", r"UPI.*BLINKIT.*", r"UPI.*CAFE.*",
            ],
        },
        "Shopping": {
            "exact": [
                "AMAZON", "FLIPKART", "MYNTRA", "AJIO", "NYKAA",
                "DMART", "BIGBASKET", "ZEPTO", "JIOMART", "DECATHLON", "CROMA", "7 ELEVEN", "OTHPOS",
            ],
            "patterns": [r"UPI.*AMAZON.*", r"UPI.*FLIPKART.*", r"UPI.*7\s*ELEVEN.*", r"OTHPOS.*"],
        },
        "Transport": {
            "exact": [
                "UBER", "OLA", "RAPIDO", "PETROL", "DIESEL", "IRCTC", "METRO", "FASTAG",
                "TOLL", "REDBUS", "MAKEMYTRIP", "INDIGO",
            ],
            "patterns": [r"UPI.*RAPIDO.*", r"UPI.*UBER.*", r"UPI.*OLA.*", r"FASTAG.*"],
        },
        "Bill Payment": {
            "exact": [
                "ELECTRICITY", "BROADBAND", "RECHARGE", "AIRTEL", "JIO", "VI", "BSNL",
                "PHARMACY", "HOSPITAL", "GST", "CBDT", "TAX", "MAHARASHTRA SAL",
            ],
            "patterns": [
                r"BILL.*PAYMENT.*", r".*RECHARGE.*", r".*ELECTRICITY.*",
                r".*PHARMACY.*", r"UPI.*MAHARASHTRA.*SAL.*",
            ],
        },
        "Entertainment": {
            "exact": ["NETFLIX", "HOTSTAR", "AMAZON PRIME", "ZEE5", "SPOTIFY", "GOOGLE PLAY"],
            "patterns": [r"UPI.*NETFLIX.*", r"PRIME.*MEMBER.*"],
        },
        "Loan Payments": {
            "exact": [
                "EMI", "LOAN", "LIC HOUSING", "HOME LOAN", "BAJAJ FINANCE", "ACHDR",
                "MANDATE DEBIT", "CMP MANDATE DEBIT", "NORTHERN ARC", "TRUECREDIT", "MPOKKET",
                "CTRAZORPAY", "SHRIRAM AKARA CAPITAL", "NDX P2P PRIVATE LIM",
            ],
            "patterns": [r"NACH.*DEBIT.*", r"ECS.*DEBIT.*", r".*EMI.*", r"ACHDR.*", r"NACH.*", r".*MANDATE DEBIT.*"],
        },
        "Transfer": {
            "exact": ["NEFT", "RTGS", "IMPS", "UPI", "TRANSFER", "PHONEPE PRIVATE"],
            "patterns": [r"UPI/.*/.*/.*", r"NEFT.*", r"RTGS.*", r"IMPS.*", r".*SENT.*PAYT.*", r".*/PAYME.*", r".*/PAYMENT.*", r".*INB.*"],
        },
        "Cash Deposit": {
            "exact": ["CASH DEPOSIT", "CSH DEP", "CASH DEP", "DEPOSITED AT GCC"],
            "patterns": [r"CASH\s+DEPOSIT.*", r"CSH\s+DEP.*", r".*DEPOSITED AT GCC.*"],
        },
        "Insurance": {
            "exact": ["SHRIRAM LIFE", "LIFE INS", "INSURANCE", "SBIMF SIP"],
            "patterns": [r".*LIFE INS.*", r".*INSURANCE.*"],
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
            "exact": ["NEFT CR", "RTGS CR", "IMPS CR", "PHONEPE PRIVATE", "PRIVATE FROM", "PRIVATE TO"],
            "patterns": [r"UPI/.*/.*/.*", r"NEFT.*CR.*", r"RTGS.*CR.*", r"IMPS.*CR.*", r".*RAMSUMAN.*", r".*INB.*", r".*/PAYME.*", r".*/PAYMENT.*", r"TRANSFER (?:TO|FROM).*"],
        },
        "Cash Deposit": {
            "exact": ["CASH DEPOSIT", "CSH DEP", "CASH DEP", "DEPOSITED AT GCC"],
            "patterns": [r"CASH\s+DEPOSIT.*", r"CSH\s+DEP.*", r".*DEPOSITED AT GCC.*"],
        },
    }

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
        path = rules_path or str(default_rules_path("sbi"))
        self._engine = JsonRuleEngine(rules_path=path, bank_key="sbi")
        self._debit_compiled = {}
        self._credit_compiled = {}

    def classify(
        self, transactions: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return self._engine.classify(transactions)

    def get_statistics(self) -> Dict[str, Any]:
        return self._engine.get_statistics()

