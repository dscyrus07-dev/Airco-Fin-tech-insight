"""Bank of India-specific transaction classifier."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .._shared.generic_bank import GenericClassifier
from .structure_validator import BANK_OF_INDIA_CONFIG


DEFAULT_KEYWORDS_FILE = str(Path(__file__).resolve().parents[5] / "backend" / "words.json")


class BankOfIndiaClassifier(GenericClassifier):
    """Bank of India classifier with bank-specific tuning on top of shared rules."""

    def __init__(self, keywords_file: Optional[str] = None):
        super().__init__(BANK_OF_INDIA_CONFIG, keywords_file=keywords_file or DEFAULT_KEYWORDS_FILE)
        self._apply_bank_of_india_tuning()

    def _apply_bank_of_india_tuning(self) -> None:
        # Bank-specific aliases frequently seen in Bank of India statements.
        tuned_entities = {
            "cash dep": {"credit_cat": "Business Income", "debit_cat": "Cash Deposit", "priority": 95, "group": "Bank of India"},
            "cash deposit": {"credit_cat": "Business Income", "debit_cat": "Cash Deposit", "priority": 95, "group": "Bank of India"},
            "deposit by": {"credit_cat": "Business Income", "debit_cat": "Transfer", "priority": 90, "group": "Bank of India"},
            "salary": {"credit_cat": "Salary", "debit_cat": "Salary", "priority": 95, "group": "Bank of India"},
            "interest": {"credit_cat": "Interest Credit", "debit_cat": "Interest Debit", "priority": 88, "group": "Bank of India"},
            "refund": {"credit_cat": "Refund", "debit_cat": "Refund", "priority": 88, "group": "Bank of India"},
            "reversal": {"credit_cat": "Refund", "debit_cat": "Refund", "priority": 88, "group": "Bank of India"},
            "atm cash withdrawal": {"credit_cat": "ATM Withdrawal", "debit_cat": "ATM Withdrawal", "priority": 92, "group": "Bank of India"},
            "bank charges": {"credit_cat": "Bank Charges", "debit_cat": "Bank Charges", "priority": 90, "group": "Bank of India"},
            "service charge": {"credit_cat": "Bank Charges", "debit_cat": "Bank Charges", "priority": 90, "group": "Bank of India"},
            "gst": {"credit_cat": "Bank Charges", "debit_cat": "Bank Charges", "priority": 85, "group": "Bank of India"},
            "emi": {"credit_cat": "Loan Disbursed", "debit_cat": "Loan Payment", "priority": 85, "group": "Bank of India"},
        }

        tuned_entities.update(self._load_bnpl_aliases())
        tuned_entities.update(self._load_bank_specific_aliases())

        for alias, cfg in tuned_entities.items():
            existing = self._entity_lookup.get(alias)
            if existing is None or cfg["priority"] >= existing.get("priority", 0):
                self._entity_lookup[alias] = cfg

        self._broad_transfer_aliases = {"upi", "neft", "rtgs", "imps", "transfer"}
        self._sorted_aliases = sorted(self._entity_lookup.keys(), key=len, reverse=True)

        # Extra keyword tuning for Bank of India narration patterns.
        self._upi_handles = list(dict.fromkeys([
            *self._upi_handles,
            "@boi",
            "@bankofindia",
            "@ibl",
            "@ybl",
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
        self._priority_aliases = sorted(
            [alias for alias in tuned_entities.keys() if alias not in self._broad_transfer_aliases],
            key=len,
            reverse=True,
        )

    def _load_bnpl_aliases(self) -> dict:
        """Promote BNPL tokens from the shared words.json classification section into the entity lookup."""
        data = self._read_keywords_file()
        bnpl_aliases = (
            data.get("entity_interpretation", {})
            .get("classification", {})
            .get("FINANCIAL_INSTRUMENT", {})
            .get("BNPL", [])
        )
        tuned_entities = {}
        for alias in bnpl_aliases:
            key = str(alias).strip().lower()
            if not key:
                continue
            tuned_entities[key] = {
                "credit_cat": "Loan Disbursed",
                "debit_cat": "Loan Payment",
                "priority": 97,
                "group": "Bank of India",
            }
        return tuned_entities

    def _load_bank_specific_aliases(self) -> dict:
        """Extra Bank of India narration overrides that commonly appear in the sample statements."""
        return {
            "google play": {"credit_cat": "Subscription", "debit_cat": "Subscription", "priority": 94, "group": "Bank of India"},
            "google play store": {"credit_cat": "Subscription", "debit_cat": "Subscription", "priority": 94, "group": "Bank of India"},
            "playstore": {"credit_cat": "Subscription", "debit_cat": "Subscription", "priority": 94, "group": "Bank of India"},
            "paytmqr": {"credit_cat": "Transfer", "debit_cat": "Transfer", "priority": 93, "group": "Bank of India"},
            "paytmqrgl": {"credit_cat": "Transfer", "debit_cat": "Transfer", "priority": 93, "group": "Bank of India"},
            "paytmqrpj": {"credit_cat": "Transfer", "debit_cat": "Transfer", "priority": 93, "group": "Bank of India"},
            "paytm.s": {"credit_cat": "Transfer", "debit_cat": "Transfer", "priority": 93, "group": "Bank of India"},
            "cwrr": {"credit_cat": "Refund", "debit_cat": "Refund", "priority": 93, "group": "Bank of India"},
            "medr": {"credit_cat": "Business Income", "debit_cat": "Transfer", "priority": 92, "group": "Bank of India"},
            "ttd": {"credit_cat": "Transfer", "debit_cat": "Transfer", "priority": 90, "group": "Bank of India"},
        }

    def _classify_single(self, txn):
        description = self._normalize(str(txn.get("description") or txn.get("narration") or ""))
        is_debit = float(txn.get("debit") or 0) > 0

        for alias in getattr(self, "_priority_aliases", []):
            if alias and alias in description:
                entry = self._entity_lookup.get(alias)
                if entry:
                    raw_cat = entry["debit_cat"] if is_debit else entry["credit_cat"]
                    return raw_cat, 98, "bank_of_india_override", "priority_alias", alias

        for alias in getattr(self, "_sorted_aliases", []):
            if not alias or alias in getattr(self, "_broad_transfer_aliases", set()):
                continue
            if alias in description:
                entry = self._entity_lookup.get(alias)
                if entry:
                    raw_cat = entry["debit_cat"] if is_debit else entry["credit_cat"]
                    return raw_cat, 88, "bank_of_india_override", "entity_alias", alias

        if is_debit and "upi" in description:
            for merchant, category in self._upi_merchant_map().items():
                if merchant in description:
                    return category, 92, "bank_of_india_override", "upi_merchant", merchant

        return super()._classify_single(txn)

    @staticmethod
    def _read_keywords_file() -> dict:
        try:
            with open(DEFAULT_KEYWORDS_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}
