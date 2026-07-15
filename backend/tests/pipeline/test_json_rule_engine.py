"""Unit tests for shared JsonRuleEngine vs HDFC class-level tables."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

from app.services.banks.hdfc.rule_engine import HDFCRuleEngine
from app.services.pipeline.classification import JsonRuleEngine


def _legacy_category(txn: Dict[str, Any]) -> str:
    """Mirror pre-2b HDFCRuleEngine._classify_single category outcome."""
    description = (txn.get("description") or "").upper()
    is_debit = txn.get("debit") is not None
    debit_c = {
        cat: {
            "exact": set(k.upper() for k in r.get("exact", [])),
            "patterns": [re.compile(p, re.I) for p in r.get("patterns", [])],
        }
        for cat, r in HDFCRuleEngine.DEBIT_RULES.items()
    }
    credit_c = {
        cat: {
            "exact": set(k.upper() for k in r.get("exact", [])),
            "patterns": [re.compile(p, re.I) for p in r.get("patterns", [])],
        }
        for cat, r in HDFCRuleEngine.CREDIT_RULES.items()
    }
    rules = debit_c if is_debit else credit_c
    default = "Others Debit" if is_debit else "Others Credit"
    for category, compiled in rules.items():
        for keyword in compiled["exact"]:
            if keyword in description:
                return category
    for category, compiled in rules.items():
        for pattern in compiled["patterns"]:
            if pattern.search(description):
                return category
    if is_debit:
        dl = description.lower()
        if "upi" in dl or "@" in dl:
            for m, c in HDFCRuleEngine.UPI_MERCHANTS.items():
                if m in dl:
                    return c
    amount = txn.get("debit") or txn.get("credit") or 0
    try:
        amount = float(amount)
    except Exception:
        amount = 0.0
    if is_debit and amount > 0:
        if amount % 100 == 0 and 500 <= amount <= 50000:
            if "ATM" in description or "ATW" in description:
                return "ATM"
    if is_debit and 99 <= amount <= 999:
        if any(k in description for k in ["SUB", "MEMBERSHIP", "PREMIUM"]):
            return "Entertainment"
    return default


def test_json_engine_matches_legacy_hdfc_tables():
    engine = JsonRuleEngine(bank_key="hdfc")
    samples = [
        {"description": "ATM WDL 5000", "debit": 5000, "credit": None},
        {"description": "UPI-SWIGGY-123", "debit": 250, "credit": None},
        {"description": "NEFT CR SALARY ACME", "debit": None, "credit": 50000},
        {"description": "INT.PD 01-01-24", "debit": None, "credit": 12.5},
        {"description": "UPI-RANDOM-PERSON@ok", "debit": 100, "credit": None},
        {"description": "POS 123 VIJETHA SUPERMAR", "debit": 800, "credit": None},
        {"description": "UNKNOWN MERCHANT XYZ", "debit": 10, "credit": None},
        {"description": "NETFLIX SUBSCRIPTION", "debit": 199, "credit": None},
        {"description": "ACHD-BAJAJ-EMI", "debit": 4500, "credit": None},
        {"description": "CASH DEPOSIT BY SELF", "debit": None, "credit": 2000},
    ]
    for t in samples:
        expected = _legacy_category(t)
        cl, un = engine.classify([t])
        actual = (cl + un)[0]["category"]
        assert actual == expected, f"{t['description']}: {actual} != {expected}"


def test_hdfc_wrapper_delegates():
    eng = HDFCRuleEngine()
    cl, un = eng.classify([{"description": "ATM WDL", "debit": 1000, "credit": None}])
    assert (cl + un)[0]["category"] == "ATM Withdrawal"
    stats = eng.get_statistics()
    assert stats["debit_categories"] == 11
