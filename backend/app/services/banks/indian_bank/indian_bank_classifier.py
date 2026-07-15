"""Indian Bank-specific transaction classifier."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .._shared.generic_bank import GenericClassifier
from .structure_validator import INDIAN_BANK_CONFIG


DEFAULT_KEYWORDS_FILE = str(Path(__file__).resolve().parents[5] / "words.json")


class IndianBankClassifier(GenericClassifier):
    """Indian Bank classifier with bank-specific tuning on top of shared rules."""

    def __init__(self, keywords_file: Optional[str] = None):
        super().__init__(INDIAN_BANK_CONFIG, keywords_file=keywords_file or DEFAULT_KEYWORDS_FILE)
        self._apply_indian_tuning()

    def _apply_indian_tuning(self) -> None:
        # Bank-specific aliases frequently seen in Indian Bank statements.
        tuned_entities = {
            "cash dep": {"credit_cat": "Business Income", "debit_cat": "Cash Deposit", "priority": 95, "group": "Indian Bank"},
            "cash deposit": {"credit_cat": "Business Income", "debit_cat": "Cash Deposit", "priority": 95, "group": "Indian Bank"},
            "deposit by": {"credit_cat": "Business Income", "debit_cat": "Transfer", "priority": 90, "group": "Indian Bank"},
            "salary": {"credit_cat": "Salary", "debit_cat": "Salary", "priority": 95, "group": "Indian Bank"},
            "upi": {"credit_cat": "Transfer", "debit_cat": "Transfer", "priority": 90, "group": "Indian Bank"},
            "neft": {"credit_cat": "Transfer", "debit_cat": "Transfer", "priority": 90, "group": "Indian Bank"},
            "rtgs": {"credit_cat": "Transfer", "debit_cat": "Transfer", "priority": 90, "group": "Indian Bank"},
            "imps": {"credit_cat": "Transfer", "debit_cat": "Transfer", "priority": 90, "group": "Indian Bank"},
            "interest": {"credit_cat": "Interest Credit", "debit_cat": "Interest Debit", "priority": 88, "group": "Indian Bank"},
            "refund": {"credit_cat": "Refund", "debit_cat": "Refund", "priority": 88, "group": "Indian Bank"},
            "reversal": {"credit_cat": "Refund", "debit_cat": "Refund", "priority": 88, "group": "Indian Bank"},
            "atm cash withdrawal": {"credit_cat": "ATM Withdrawal", "debit_cat": "ATM Withdrawal", "priority": 92, "group": "Indian Bank"},
            "bank charges": {"credit_cat": "Bank Charges", "debit_cat": "Bank Charges", "priority": 90, "group": "Indian Bank"},
            "service charge": {"credit_cat": "Bank Charges", "debit_cat": "Bank Charges", "priority": 90, "group": "Indian Bank"},
            "gst": {"credit_cat": "Bank Charges", "debit_cat": "Bank Charges", "priority": 85, "group": "Indian Bank"},
            "emi": {"credit_cat": "Loan Disbursed", "debit_cat": "Loan Payment", "priority": 85, "group": "Indian Bank"},
        }

        for alias, cfg in tuned_entities.items():
            existing = self._entity_lookup.get(alias)
            if existing is None or cfg["priority"] >= existing.get("priority", 0):
                self._entity_lookup[alias] = cfg

        self._sorted_aliases = sorted(self._entity_lookup.keys(), key=len, reverse=True)

        # Extra keyword tuning for Indian Bank narration patterns.
        self._upi_handles = list(dict.fromkeys([
            *self._upi_handles,
            "@ibl",
            "@okicici",
            "@axl",
            "@ybl",
            "@ptys",
            "@paytm",
        ]))
        self._transfer_patterns = list(dict.fromkeys([
            *self._transfer_patterns,
            "cash dep",
            "cash deposit",
            "deposit by",
            "fund transfer",
            "branch transfer",
        ]))
        self._salary_tokens = list(dict.fromkeys([
            *self._salary_tokens,
            "salary credit",
            "pay salary",
        ]))
        self._charge_tokens = list(dict.fromkeys([
            *self._charge_tokens,
            "charge",
            "charges",
            "sms charges",
        ]))
        self._refund_tokens = list(dict.fromkeys([
            *self._refund_tokens,
            "charge reversal",
            "cash back",
        ]))
        self._loan_patterns = list(dict.fromkeys([
            *self._loan_patterns,
            "emi",
            "loan payment",
        ]))
