"""
Airco Insights — Canara Bank Rule Engine
==========================================
Deterministic classification engine for Canara Bank transactions.
Mirrors HDFCRuleEngine: exact keywords, regex patterns, UPI detection,
amount-range heuristics, and get_statistics().
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .._shared.generic_bank import GenericBankConfig

CONFIG = GenericBankConfig(
    bank_key="canara",
    bank_name="Canara Bank",
    file_prefix="canara",
    markers=["canara bank", "current & saving account statement", "cnrb"],
    support_aliases=["canara", "canara bank"],
)

logger = logging.getLogger(__name__)


@dataclass
class RuleClassificationResult:
    category: str
    confidence: float
    source: str
    matched_rule: Optional[str] = None
    matched_keyword: Optional[str] = None


class CanaraRuleEngine:
    """Full-grade deterministic rule engine for Canara Bank transactions."""

    CONF_EXACT   = 0.99
    CONF_PATTERN = 0.95
    CONF_UPI     = 0.85
    CONF_AMOUNT  = 0.70

    DEBIT_RULES: Dict[str, Dict] = {
        "ATM Withdrawal": {
            "exact": ["ATM CASH", "ATM WDL", "ATW", "CASH WITHDRAWAL", "CASH W/D"],
            "patterns": [r"ATM.*CASH", r"ATW-\d+", r"CASH\s*W/D"],
        },
        "Bank Charges": {
            "exact": [
                "SMS CHARGES", "SLABWISE NMMB CHARGES", "ATM INSUFFICIENT FUND CHARGES",
                "ATM / IMPS TRANSACTION CHARGE", "ATM / IMPS TRANSACTION CHARGES",
                "MAINTENANCE CHARGE", "ANNUAL CHARGES", "LEDGER FOLIO CHARGES",
                "MINIMUM BALANCE CHARGE", "MIN BAL CHARGE", "DEBIT CARD ANNUAL FEE",
                "GST ON CHARGES",
            ],
            "patterns": [r".*CHARGES.*", r".*CHARGE.*FEE.*", r".*ANNUAL.*FEE.*"],
        },
        "Loan Payments": {
            "exact": ["EMI", "ECS ", "NACH DR", "LOAN EMI", "LOAN REPAY", "SI DEBIT", "STANDING INST"],
            "patterns": [r"ECS.*DR", r"NACH.*DR", r".*EMI.*\d+", r"LOAN.*REPAY"],
        },
        "Food": {
            "exact": ["SWIGGY", "ZOMATO", "DOMINOS", "MCDONALDS", "KFC", "PIZZA", "RESTAURANT", "FOOD"],
            "patterns": [r"SWIGGY.*", r"ZOMATO.*ORDER"],
        },
        "Shopping": {
            "exact": ["AMAZON", "FLIPKART", "MYNTRA", "MEESHO", "NYKAA", "AJIO", "BIGBASKET", "BLINKIT", "ZEPTO"],
            "patterns": [r"AMZN.*MKTP", r"FLIPKART.*INTERNET"],
        },
        "Transport": {
            "exact": ["UBER", "OLA", "RAPIDO", "PETROL", "DIESEL", "FUEL", "FASTAG", "IRCTC", "REDBUS", "MAKEMYTRIP"],
            "patterns": [r"UBER.*TRIP", r"OLA.*CAB", r"FASTAG.*", r"IRCTC.*"],
        },
        "Bill Payment": {
            "exact": [
                "ELECTRICITY", "WATER BILL", "GAS BILL", "BROADBAND", "MOBILE RECHARGE",
                "AIRTEL", "JIO", "BSNL", "VI ", "TATA SKY", "DISH TV",
            ],
            "patterns": [r".*RECHARGE.*", r"BILL.*PAYMENT", r"MOBILE.*BILL"],
        },
        "Entertainment": {
            "exact": ["NETFLIX", "HOTSTAR", "AMAZON PRIME", "SPOTIFY", "ZEE5", "SONYLIV", "YOUTUBE PREMIUM"],
            "patterns": [r"NETFLIX.*", r"PRIME.*MEMBER"],
        },
        "Insurance": {
            "exact": ["LIC PREMIUM", "INSURANCE PREMIUM", "LIC ", "HDFC LIFE", "SBI LIFE", "ICICI PRU"],
            "patterns": [r".*INSURANCE.*PREMIUM.*", r"LIC.*PREMIUM"],
        },
        "Investment": {
            "exact": ["RD DRAWDOWN", "INSTL PAY TO RD", "MUTUAL FUND", "SIP", "NSC", "PPF"],
            "patterns": [r"RD.*DRAWDOWN", r".*SIP.*", r"MUTUAL.*FUND"],
        },
        "Education": {
            "exact": ["SCHOOL FEES", "COLLEGE FEES", "TUITION", "BYJU", "UNACADEMY"],
            "patterns": [r"SCHOOL.*FEE", r"COLLEGE.*FEE"],
        },
        "Health": {
            "exact": ["PHARMACY", "HOSPITAL", "CLINIC", "DOCTOR", "MEDICAL", "APOLLO", "MEDPLUS"],
            "patterns": [r".*PHARMACY.*", r".*HOSPITAL.*"],
        },
        "Transfer": {
            "exact": [
                "NEFT DR", "RTGS DR", "IMPS DR", "IB OAT", "IB ITG",
                "BY XFER", "EFS. BY XFER", "SELF TRANSFER",
            ],
            "patterns": [r"NEFT.*DR", r"RTGS.*DR", r"IMPS.*DR", r"UPI.*DR"],
        },
    }

    CREDIT_RULES: Dict[str, Dict] = {
        "Salary": {
            "exact": ["SALARY", "SAL CR", "PAYROLL", "WAGES", "SALARY CREDIT"],
            "patterns": [r"SAL.*CR", r"PAYROLL.*CR", r"SALARY.*CREDIT"],
        },
        "Interest Income": {
            "exact": [
                "GROSS INT CR", "SBINT FOR THE PERIOD", "INT CR", "INTEREST CREDIT",
                "FD REDEEM INTEREST", "SB INTEREST",
            ],
            "patterns": [r"INT.*CR", r"INTEREST.*CR", r"FD.*INTEREST"],
        },
        "Investment Returns": {
            "exact": ["FD REDEEM PRINCIPAL", "RD MATURITY", "MF REDEMPTION"],
            "patterns": [r"FD.*REDEEM", r"RD.*MATURITY"],
        },
        "Refund": {
            "exact": ["REFUND", "REVERSAL", "CASHBACK", "CASH BACK", "GST REV"],
            "patterns": [r".*REFUND.*", r".*REVERSAL.*", r"GST.*REV"],
        },
        "Loan Credit": {
            "exact": ["LOAN DISBURSAL", "LOAN CREDIT", "DISBURSEMENT"],
            "patterns": [r"LOAN.*DISBURSAL", r"LOAN.*CR"],
        },
        "Business Income": {
            "exact": ["CASHFREE PAYMENTS INDIA PRIVATE", "RAZORPAY", "PAYTM PAYMENTS"],
            "patterns": [r"CASHFREE.*", r"RAZORPAY.*CR"],
        },
        "Transfer": {
            "exact": [
                "NEFT CR", "RTGS CR", "IMPS CR", "IB OAT", "IB ITG",
                "INET-IMPS-CR", "EFS. BY XFER. FROM CASA", "BY XFER. FROM CASA",
            ],
            "patterns": [r"NEFT.*CR", r"RTGS.*CR", r"IMPS.*CR", r"UPI.*CR"],
        },
    }

    UPI_MERCHANTS: Dict[str, str] = {
        "swiggy": "Food", "zomato": "Food",
        "amazon": "Shopping", "flipkart": "Shopping",
        "uber": "Transport", "ola": "Transport",
        "netflix": "Entertainment", "hotstar": "Entertainment",
    }

    def __init__(self, rules_path: Optional[str] = None, keywords_file: Optional[str] = None):
        """Phase 2b: runtime delegates to JsonRuleEngine. Tables kept for extract."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        from app.services.pipeline.classification.rule_engine import (
            JsonRuleEngine,
            default_rules_path,
        )
        path = rules_path or str(default_rules_path("canara"))
        self._engine = JsonRuleEngine(rules_path=path, bank_key="canara")
        self._debit_compiled = {}
        self._credit_compiled = {}

    def classify(
        self, transactions: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return self._engine.classify(transactions)

    def get_statistics(self) -> Dict[str, Any]:
        return self._engine.get_statistics()

