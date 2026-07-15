"""
SBI Bank Transaction Classifier
================================
Rule-based classifier for SBI transactions using keyword matching.
"""

import logging
from typing import Tuple, Dict, List

from .._shared.category_registry import normalize_category

logger = logging.getLogger(__name__)


class SBIClassifier:
    """
    Deterministic classifier for SBI Bank transactions.
    Uses keyword matching with confidence scoring.
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Category definitions with keywords
        self.categories = {
            "Salary": ["SALARY", "SAL CR", "PAYROLL", "WAGES", "STIPEND", "SALARY CREDIT", "MONTHLY SAL"],
            "ATM Withdrawal": ["ATM WDL", "ATMWDL", "ATW", "CASH WITHDRAWAL", "NFS ATM", "ATM CASH", "ATM-FROM"],
            "UPI": ["UPI/", "UPI-", "UPI/DR", "UPI/CR", "PHONEPE", "PAYTM", "GPAY", "GOOGLE PAY", "BHIM", "PAYTMQR"],
            "NEFT/RTGS": ["NEFT", "RTGS", "IMPS", "TRANSFER", "INB", "UTR", "CNABOZBO", "NISHANT"],
            "Bank Charges": ["CHARGES", "SERVICE CHARGE", "SMS ALERT", "MAINTENANCE", "ANNUAL FEE", "GST", "TDS"],
            "Loan EMI": ["EMI", "LOAN", "BAJAJ", "TATA CAPITAL", "HDFC LTD", "LOAN REPAYMENT"],
            "Credit Card": ["CREDIT CARD", "CC PAYMENT", "CRED", "SLICE", "ONECARD", "CARD PAYMENT"],
            "Food & Dining": ["SWIGGY", "ZOMATO", "DOMINOS", "KFC", "MCDONALDS", "PIZZA", "RESTAURANT", "CAFE", "FOOD"],
            "Shopping": ["AMAZON", "FLIPKART", "MYNTRA", "AJIO", "SHOPPING", "RELIANCE", "BIG BAZAAR", "DMART"],
            "Utilities": ["ELECTRICITY", "WATER", "GAS", "MOBILE RECHARGE", "BROADBAND", "AIRTEL", "JIO", "BSNL"],
            "Investment": ["MUTUAL FUND", "SIP", "ZERODHA", "GROWW", "UPSTOX", "INVESTMENT", "DEMAT"],
            "Cash Deposit": ["CASH DEPOSIT", "CDM", "CASHDEP", "CASH DEP"],
            "Cheque": ["CHEQUE", "CHQ", "CLG", "CHEQUE DEPOSIT", "CHEQUE CLEARING"],
            "Insurance": ["INSURANCE", "LIC", "HDFC LIFE", "ICICI PRU", "POLICY"],
            "Tax": ["TAX", "TDS", "GST", "INCOME TAX", "TAX DEDUCTED"],
            "Fuel": ["PETROL", "DIESEL", "FUEL", "HP", "BPCL", "IOCL", "SHELL"],
            "Travel": ["UBER", "OLA", "TAXI", "BOOKING", "IRCTC", "RAILWAY", "FLIGHT", "HOTEL"],
            "Medical": ["HOSPITAL", "MEDICAL", "PHARMACY", "DOCTOR", "MEDICINE"],
            "Education": ["SCHOOL", "COLLEGE", "FEES", "EDUCATION", "UNIVERSITY"],
            "Rent": ["RENT", "LEASE", "PROPERTY"],
            "Subscriptions": ["NETFLIX", "AMAZON PRIME", "SUBSCRIPTION", "RENEWAL"],
        }
        
        self.logger.info("SBI classifier initialized with %d categories", len(self.categories))

    def classify(self, row) -> Tuple[str, int]:
        """
        Classify a transaction based on description.
        
        Returns:
            (category, confidence) where confidence is 0-100
        """
        description = str(row.get("Description", "")).upper()
        try:
            is_debit = float(row.get("Debit", 0) or row.get("debit", 0) or 0) > 0
        except (TypeError, ValueError):
            is_debit = False
        
        # Try to match keywords
        for category, keywords in self.categories.items():
            for keyword in keywords:
                if keyword in description:
                    return (normalize_category(category, is_debit=is_debit), 100)
        
        # Default to "Others" if no match
        return (normalize_category("Others", is_debit=is_debit), 100)

    def get_all_categories(self) -> dict:
        """Return all possible display categories grouped by direction."""
        return {
            "credit": [
                "Salary",
                "Cash Deposit",
                "Cheque Deposit",
                "UPI",
                "NEFT/RTGS",
                "Investment",
            ],
            "debit": [
                "ATM Withdrawal",
                "UPI",
                "NEFT/RTGS",
                "Bank Charges",
                "Loan EMI",
                "Credit Card",
                "Food & Dining",
                "Shopping",
                "Utilities",
                "Investment",
                "Cheque",
                "Insurance",
                "Tax",
                "Fuel",
                "Travel",
                "Medical",
                "Education",
                "Rent",
                "Subscriptions",
            ],
        }

    def get_category_stats(self) -> dict:
        """Return classifier statistics."""
        return {
            "total_categories": len(self.categories),
            "source": "inline_keywords",
            "version": "1.0",
        }
