from __future__ import annotations

import json
import os
from typing import Optional

# ── Load canonical map from words.json once at import ──────────

def _find_words_json() -> str:
    """Walk up from this file to find words.json"""
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        candidate = os.path.join(current, "words.json")
        if os.path.isfile(candidate):
            return candidate
        current = os.path.dirname(current)
    raise FileNotFoundError("words.json not found in parent directories")


def _load_data() -> tuple[dict, list]:
    try:
        path = _find_words_json()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        canonical_map = (
            data
            .get("category_normalization", {})
            .get("canonical_map", {})
        )
        all_categories = (
            data
            .get("metadata", {})
            .get("extended_categories", [])
        )
        return canonical_map, all_categories
    except Exception:
        return {}, []


_CANONICAL_MAP, _ALL_CATEGORIES = _load_data()

_DISPLAY_ALIASES = {
    # ── Legacy display names ──────────────────────────────────────────────────
    "Loan Payment / EMI": "Loan Payment",
    "Loan Disbursal": "Loan Disbursed",
    "Bank Transfer": "Transfer",
    "Transfer Out": "Transfer",
    "Transfer In": "Transfer",
    "UPI Transfer": "Transfer",
    "Salary Credits": "Salary",
    "Interest Credit": "Interest Income",
    "Interest Debit": "Interest Income",
    "Interest": "Interest Income",
    "Bank Transfer In": "Transfer",
    "Cash Deposit": "Business Income",
    "Loan Credit": "Loan Disbursed",
    "Bounce": "Bank Charges",
    "Cheque": "Transfer",
    "Uncategorised": "Others Debit",
    # ── Rule engine legacy names ──────────────────────────────────────────────
    "Loan EMI": "Loan Payment",
    "Loan Emi": "Loan Payment",
    "EMI": "Loan Payment",
    "Food & Dining": "Food",
    "Dining": "Food",
    "Transport": "Transport",
    "Travel": "Transport",
    "Transport Expense": "Transport",
    # ── words.json SCREAMING_SNAKE codes ─────────────────────────────────────
    "FUEL_EXPENSE": "Fuel",
    "FOOD_EXPENSE": "Food",
    "SHOPPING_EXPENSE": "Shopping",
    "TRANSPORT_EXPENSE": "Transport",
    "EMI_PAYMENT": "Loan Payment",
    "LOAN_DISBURSED": "Loan Disbursed",
    "LOAN_PAYMENT": "Loan Payment",
    "MERCHANT_PAYOUT": "Business Income",
    "DELIVERY_EXPENSE": "Food",
    "UTILITY_EXPENSE": "Bill Payment",
    "INSURANCE_EXPENSE": "Insurance",
    "INSURANCE_PREMIUM": "Insurance",
    "INSURANCE_CREDIT": "Business Income",
    "SUBSCRIPTION_EXPENSE": "Subscriptions",
    "TRANSFER_IN": "Transfer",
    "TRANSFER_OUT": "Transfer",
    "TRANSFER": "Transfer",
    "SALARY_INCOME": "Salary",
    "INTEREST_INCOME": "Interest Income",
    "INTEREST_EXPENSE": "Bank Charges",
    "BANK_CHARGES": "Bank Charges",
    "ATM_WITHDRAWAL": "ATM Withdrawal",
    "REFUND": "Refund",
    "CASHBACK": "Refund",
    "BUSINESS_INCOME": "Business Income",
    "RENTAL_INCOME": "Business Income",
    "RECHARGE_EXPENSE": "Bill Payment",
    "CREDIT_CARD_PAYMENT": "Credit Card Payment",
}

# ── Public API ──────────────────────────────────────────────────

def normalize_category(
    category: Optional[str],
    is_debit: bool = True
) -> str:
    """
    Convert any category string to canonical form.
    Call this at every point a category is assigned.

    Handles:
    - SCREAMING_SNAKE from words.json (FOOD_EXPENSE → Food)
    - Title Case from rule engines (Loan Payments → Loan Payment)
    - Legacy/inconsistent names (Others → Others Debit)
    - None / empty string → safe fallback
    """
    if not category or not str(category).strip():
        return "Others Debit" if is_debit else "Others Credit"

    if isinstance(is_debit, str):
        direction = is_debit.strip().lower()
        if direction in {"credit", "cr", "in", "income", "creditin", "cash_in"}:
            is_debit = False
        elif direction in {"debit", "dr", "out", "expense", "debitout", "cash_out"}:
            is_debit = True
        else:
            is_debit = bool(direction)

    c = str(category).strip()

    # Already canonical
    if c in _ALL_CATEGORIES:
        return c

    # Lookup in canonical map (covers both words.json codes
    # and rule engine legacy names)
    if c in _DISPLAY_ALIASES:
        return _DISPLAY_ALIASES[c]

    if c in _CANONICAL_MAP:
        return _CANONICAL_MAP[c]

    # Unknown — safe fallback
    return "Others Debit" if is_debit else "Others Credit"


def get_allowed_categories() -> list[str]:
    """
    Single source of truth for AI allowed_categories.
    Use this everywhere — do not hardcode category lists.
    """
    if _ALL_CATEGORIES:
        return list(_ALL_CATEGORIES)
    # Hardcoded fallback if words.json unavailable
    return [
        "Food", "Transport", "Shopping", "Groceries", "Medical",
        "Entertainment", "Loan Payment", "Bill Payment",
        "Credit Card Payment", "ATM Withdrawal", "Bank Charges",
        "Investment", "Insurance", "Insurance Claim", "Fuel",
        "Travel", "Fitness", "Education", "Subscription",
        "Business Expense", "Tax Payment", "Transfer",
        "Others Debit", "Salary", "Business Income",
        "Freelance Income", "Interest Income", "Refund",
        "Cashback", "Dividend", "Loan Disbursed",
        "Investment Returns", "Rental Income", "Others Credit",
    ]


def is_valid_category(category: str) -> bool:
    return category in _ALL_CATEGORIES
