"""
Airco Insights — Axis Bank Rule Engine
=======================================
Deterministic classification engine for Axis Bank transactions.
Bank-specific rules optimized for Axis statement patterns.

Axis-specific transaction prefixes:
- ATM-CASH/   — ATM cash withdrawal
- ATM-CASH-AXIS/ — Axis ATM
- IMPS/P2A/   — IMPS credit transfer
- IMPS/P2M/   — IMPS merchant payment
- UPI/P2A/    — UPI transfer
- UPI/P2M/    — UPI merchant payment
- ACH-DR-     — Mandate/EMI debit
- CreditCard Payment — credit card bill payment
- NEFT/       — NEFT transfer
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Classification result for a transaction."""
    category: str
    confidence: float
    source: str
    matched_rule: Optional[str] = None
    matched_keyword: Optional[str] = None


class AxisRuleEngine:
    """Axis Bank-specific deterministic rule engine."""

    CONF_EXACT   = 0.99
    CONF_PATTERN = 0.95
    CONF_MERCHANT = 0.90
    CONF_UPI     = 0.85
    CONF_AMOUNT  = 0.70

    DEBIT_RULES = {
        "ATM Withdrawal": {
            "exact": [
                "ATM-CASH", "ATM CASH", "ATM WDL", "CASH WITHDRAWAL",
                "ATM-CASH-AXIS", "ATM-CASH/HYDERABAD", "ATM-CASH/MUMBAI",
                "ATM-CASH/DELHI", "ATM-CASH/BANGALORE", "ATM-CASH/CHENNAI",
                "ATM-CASH/KOLKATA", "ATM-CASH/PUNE", "ATM-CASH/NCBI",
                "ATM-CASH/KANDI", "ATM-CASH/BANDLAGU", "ATM OFFSITE",
            ],
            "patterns": [
                r"ATM-CASH.*",
                r"ATM.*CASH.*",
                r"CASH.*WITHDRA.*",
                r"ATM-CASH-AXIS.*",
            ],
        },
        "Food": {
            "exact": [
                "SWIGGY", "ZOMATO", "DOMINOS", "MCDONALDS", "KFC", "BURGER",
                "PIZZA", "PIZZAHUT", "SUBWAY", "STARBUCKS", "CCD", "CAFE",
                "RESTAURANT", "FOOD", "DINING", "EATERY", "BIRYANI",
                "HALDIRAM", "BARBEQUE", "CHAAYOS", "FAASOS", "REBEL FOODS",
            ],
            "patterns": [
                r"UPI/P2M.*SWIGGY.*",
                r"UPI/P2M.*ZOMATO.*",
                r"IMPS/P2M.*FOOD.*",
            ],
        },
        "Shopping": {
            "exact": [
                "AMAZON", "FLIPKART", "MYNTRA", "AJIO", "NYKAA", "MEESHO",
                "SNAPDEAL", "TATACLIQ", "DMART", "BIGBASKET", "BLINKIT",
                "ZEPTO", "INSTAMART", "JIOMART", "DECATHLON", "IKEA",
                "SHOPPERS STOP", "LIFESTYLE", "WESTSIDE", "PANTALOONS",
                "MAX", "ZARA", "H&M", "MINISO", "CROMA", "VIJAY SALES",
                "RELIANCE DIGITAL",
            ],
            "patterns": [
                r"UPI/P2M.*AMAZON.*",
                r"UPI/P2M.*FLIPKART.*",
                r"IMPS/P2M.*SHOP.*",
            ],
        },
        "Transport": {
            "exact": [
                "UBER", "OLA", "RAPIDO", "PETROL", "DIESEL", "FUEL",
                "IOCL", "BPCL", "HPCL", "INDIAN OIL", "BHARAT PETROLEUM",
                "IRCTC", "RAILWAY", "METRO", "TOLL", "FASTAG", "PARKING",
                "REDBUS", "MAKEMYTRIP", "GOIBIBO", "YATRA", "CLEARTRIP",
                "INDIGO", "SPICEJET", "AIRINDIA", "VISTARA", "AKASA",
            ],
            "patterns": [
                r"UPI/P2M.*UBER.*",
                r"UPI/P2M.*OLA.*",
                r"UPI/P2M.*IRCTC.*",
                r"FASTAG.*",
            ],
        },
        "Bill Payment": {
            "exact": [
                "ELECTRICITY", "WATER", "GAS", "BROADBAND", "MOBILE",
                "RECHARGE", "AIRTEL", "JIO", "VI", "BSNL", "ACT",
                "TATA SKY", "DISH", "HATHWAY",
                "PHARMACY", "APOLLO", "MEDPLUS", "NETMEDS", "PHARMEASY",
                "1MG", "TATA 1MG", "HOSPITAL", "CLINIC", "DIAGNOSTIC",
                "THYROCARE", "METROPOLIS", "DR LAL", "PRACTO",
                "GST", "CBDT", "TDS", "INCOME TAX",
            ],
            "patterns": [
                r"BILL.*PAYMENT.*",
                r".*RECHARGE.*",
                r"MOBILE.*BILL.*",
                r".*ELECTRICITY.*BILL.*",
                r".*PHARMACY.*",
                r".*HOSPITAL.*",
            ],
        },
        "Entertainment": {
            "exact": [
                "NETFLIX", "AMAZON PRIME", "HOTSTAR", "DISNEY", "SONYLIV",
                "ZEE5", "VOOT", "ALTBALAJI", "SPOTIFY", "GAANA", "WYNK",
                "APPLE MUSIC", "YOUTUBE", "PLAYSTATION", "XBOX", "STEAM",
                "GOOGLE PLAY", "APP STORE",
            ],
            "patterns": [
                r"UPI/P2M.*NETFLIX.*",
                r"PRIME.*MEMBER.*",
                r"HOTSTAR.*PREMIUM.*",
            ],
        },
        "Loan Payments": {
            "exact": [
                "EMI", "LOAN", "BAJAJ FINANCE", "HOME LOAN", "CAR LOAN",
                "PERSONAL LOAN", "LIC HOUSING", "HDFC HOME LOAN",
                "ICICI HOME LOAN",
            ],
            "patterns": [
                r"ACH-DR-.*",           # Axis mandate debit
                r"ACH-DR-LIC.*",        # LIC Housing mandate
                r"EMI.*DEBIT.*",
                r"LOAN.*REPAYMENT.*",
                r".*EMI.*\d+/\d+.*",
                r"NACH.*DEBIT.*",
                r"ECS.*DEBIT.*",
            ],
        },
        "Credit Card Payment": {
            "exact": [
                "CREDITCARD PAYMENT", "CREDIT CARD PAYMENT",
                "CC PAYMENT", "CCPAYMENT",
            ],
            "patterns": [
                r"CreditCard\s*Payment.*",
                r"Credit\s*Card\s*Payment.*",
                r"CC\s*PAYMENT.*",
                r".*Ref#[A-Z0-9]{10,}.*",   # CC payment reference
            ],
        },
        "Transfer": {
            "exact": [
                "NEFT", "RTGS", "IMPS", "UPI", "TRANSFER", "TRF",
            ],
            "patterns": [
                r"NEFT.*DR.*",
                r"RTGS.*DR.*",
                r"IMPS/P2A.*",
                r"IMPS/P2M.*",
                r"UPI/P2A.*",
                r"UPI/P2M.*",
            ],
        },
    }

    CREDIT_RULES = {
        "Salary Credits": {
            "exact": [
                "SALARY", "SAL", "PAYROLL", "WAGES", "STIPEND",
            ],
            "patterns": [
                r"SALARY.*CR.*",
                r"SAL.*CREDIT.*",
                r"PAYROLL.*",
                r".*SALARY.*",
            ],
        },
        "Loan": {
            "exact": [
                "LIC HOUSING", "HOME LOAN CREDIT", "LOAN DISBURSAL",
            ],
            "patterns": [
                r"LOAN.*CREDIT.*",
                r"DISBURS.*",
            ],
        },
        "Interest": {
            "exact": [
                "INTEREST", "INT", "INT.PD", "INTPD", "INT PAID",
                "CREDIT INTEREST",
            ],
            "patterns": [
                r"INTEREST.*CREDIT.*",
                r".*INTEREST.*",
            ],
        },
        "Refund": {
            "exact": [
                "REFUND", "REVERSAL", "CASHBACK", "CASH BACK",
                "NEFT RETURN", "ACH RETURN",
            ],
            "patterns": [
                r"REFUND.*",
                r".*REVERSAL.*",
                r".*CASHBACK.*",
                r"NEFT.*RETURN.*",
                r"ACH.*RETURN.*",
            ],
        },
        "Bank Transfer In": {
            "exact": [
                "NEFT CR", "RTGS CR", "IMPS CR", "NEFTCR", "RTGSCR",
            ],
            "patterns": [
                r"IMPS/P2A.*",           # IMPS credit to account
                r"NEFT.*CR.*",
                r"RTGS.*CR.*",
                r"UPI/P2A.*",            # UPI credit to account
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
        "paytm": "Others Debit",
        "phonepe": "Others Debit",
        "gpay": "Others Debit",
    }

    def __init__(self, rules_path: Optional[str] = None):
        """
        Phase 2b: runtime classification delegates to shared JsonRuleEngine
        loaded from banks/axis/rules.json (mechanical dump via
        scripts/dev/extract_bank_rules.py).

        Class-level DEBIT_RULES / CREDIT_RULES / UPI_MERCHANTS remain the
        extract source of truth. Do not delete until all banks are green.
        """
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        from app.services.pipeline.classification.rule_engine import (
            JsonRuleEngine,
            default_rules_path,
        )

        path = rules_path or str(default_rules_path("axis"))
        self._engine = JsonRuleEngine(rules_path=path, bank_key="axis")
        self._debit_compiled = {}
        self._credit_compiled = {}

    def classify(
        self,
        transactions: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return self._engine.classify(transactions)

    def get_statistics(self) -> Dict[str, Any]:
        return self._engine.get_statistics()
