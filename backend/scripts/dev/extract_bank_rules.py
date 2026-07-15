"""Mechanical dump of bank rule-engine dicts -> rules.json.

Usage:
  python scripts/dev/extract_bank_rules.py <bank>

Do NOT hand-transcribe rules. Re-run when Python source changes.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict

BACKEND = Path(__file__).resolve().parents[2]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

BANK_MODULES = {
    "hdfc": "app.services.banks.hdfc.rule_engine.HDFCRuleEngine",
    "axis": "app.services.banks.axis.rule_engine.AxisRuleEngine",
    "canara": "app.services.banks.canara.rule_engine.CanaraRuleEngine",
    "icici": "app.services.banks.icici.rule_engine.ICICIRuleEngine",
    "kotak": "app.services.banks.kotak.rule_engine.KotakRuleEngine",
    "sbi": "app.services.banks.sbi.rule_engine.SBIRuleEngine",
}

AXIS_STYLE_MERCHANT_MAP = {
    "amazon": {"debit": "Shopping", "credit": "Refund"},
    "flipkart": {"debit": "Shopping", "credit": "Refund"},
    "myntra": {"debit": "Shopping", "credit": "Refund"},
    "ajio": {"debit": "Shopping", "credit": "Refund"},
    "nykaa": {"debit": "Shopping", "credit": "Refund"},
    "swiggy": "Food",
    "zomato": "Food",
    "dominos": "Food",
    "mcdonalds": "Food",
    "kfc": "Food",
    "uber": "Transport",
    "ola": "Transport",
    "rapido": "Transport",
    "netflix": "Entertainment",
    "hotstar": "Entertainment",
    "spotify": "Entertainment",
    "paytm": {"debit": "Others Debit", "credit": "Transfer In"},
    "phonepe": {"debit": "Others Debit", "credit": "Transfer In"},
    "gpay": {"debit": "Others Debit", "credit": "Transfer In"},
}

AXIS_STYLE_AMOUNT = {
    "emi": {
        "enabled": True,
        "debit_only": True,
        "min_amount": 500,
        "max_amount": 100000,
        "multiple_of": 100,
        "description_tokens": ["emi", "loan", "installment"],
        "category": "Loan Payments",
        "matched_rule": "amount_emi",
        "token_case": "lower",
    },
    "salary": {
        "enabled": True,
        "credit_only": True,
        "min_amount": 10000,
        "multiple_of": 1000,
        "description_tokens": ["salary", "payroll", "wages"],
        "category": "Salary Credits",
        "matched_rule": "amount_salary",
        "token_case": "lower",
    },
}

BANK_PROFILES: Dict[str, Dict[str, Any]] = {
    "hdfc": {
        "match_semantics": {
            "layers": ["exact_keyword", "pattern_match", "upi_merchant", "amount_heuristic", "default"],
            "is_debit": "debit_not_none",
            "upi_gate": "upi_or_at",
            "upi_debit_only": True,
            "return_mode": "split",
        },
        "merchant_map": {},
        "amount_heuristics": {
            "atm": {
                "enabled": True, "min_amount": 500, "max_amount": 50000, "multiple_of": 100,
                "description_tokens": ["ATM", "ATW"], "category": "ATM",
                "matched_rule": "amount_atm", "debit_only": True, "token_case": "upper",
            },
            "subscription": {
                "enabled": True, "min_amount": 99, "max_amount": 999,
                "description_tokens": ["SUB", "MEMBERSHIP", "PREMIUM"],
                "category": "Entertainment", "matched_rule": "amount_subscription",
                "debit_only": True, "token_case": "upper",
            },
        },
    },
    "axis": {
        "match_semantics": {
            "layers": ["exact_keyword", "pattern_match", "merchant_mapping", "upi_merchant", "amount_heuristic", "default"],
            "is_debit": "debit_positive",
            "upi_gate": "upi_only",
            "upi_debit_only": True,
            "return_mode": "split",
        },
        "merchant_map": AXIS_STYLE_MERCHANT_MAP,
        "amount_heuristics": AXIS_STYLE_AMOUNT,
    },
    "canara": {
        "match_semantics": {
            "layers": ["exact_keyword", "pattern_match", "upi_merchant", "amount_heuristic", "default"],
            "is_debit": "debit_truthy",
            "upi_gate": "upi_or_at",
            "upi_debit_only": True,
            # Legacy returned (all, unclassified_subset); final pipeline set is same as split.
            "return_mode": "split",
            "legacy_return_note": "Canara used to return classified+unclassified as first tuple; base_processor deduped. Shared engine uses split.",
        },
        "merchant_map": {},
        "amount_heuristics": {
            "atm": {
                "enabled": True, "min_amount": 500, "max_amount": 50000, "multiple_of": 100,
                "description_tokens": ["ATM", "ATW", "CASH"], "category": "ATM Withdrawal",
                "matched_rule": "amount_atm", "debit_only": True, "token_case": "upper",
            },
            "subscription": {
                "enabled": True, "min_amount": 99, "max_amount": 999,
                "description_tokens": ["SUB", "MEMBERSHIP", "PREMIUM"],
                "category": "Entertainment", "matched_rule": "amount_subscription",
                "debit_only": True, "token_case": "upper",
            },
        },
    },
    "icici": {
        "match_semantics": {
            "layers": ["exact_keyword", "pattern_match", "merchant_mapping", "upi_merchant", "amount_heuristic", "default"],
            "is_debit": "debit_positive",
            "upi_gate": "upi_only",
            "upi_debit_only": True,
            "return_mode": "split",
        },
        "merchant_map": AXIS_STYLE_MERCHANT_MAP,
        "amount_heuristics": AXIS_STYLE_AMOUNT,
    },
    "kotak": {
        "match_semantics": {
            "layers": [
                "exact_keyword", "pattern_match", "merchant_mapping",
                "upi_merchant", "upi_path_merchant", "amount_heuristic", "default",
            ],
            "is_debit": "debit_positive",
            # Kotak UPI layer has no gate — always scan merchants, then UPI/path
            "upi_gate": "always",
            "upi_debit_only": False,
            "return_mode": "split",
        },
        "merchant_map": AXIS_STYLE_MERCHANT_MAP,
        "amount_heuristics": AXIS_STYLE_AMOUNT,
    },
    "sbi": {
        "match_semantics": {
            "layers": [
                "exact_keyword", "pattern_match", "merchant_mapping",
                "upi_merchant", "upi_path_merchant", "amount_heuristic",
                "generic_fallback", "default",
            ],
            "is_debit": "debit_positive",
            "upi_gate": "always",
            "upi_debit_only": False,
            "return_mode": "split",
            "generic_fallback": True,
            "words_json_merge": True,
            "extract_note": "DEBIT/CREDIT exact lists dumped AFTER SBIRuleEngine() words.json merge.",
        },
        "merchant_map": AXIS_STYLE_MERCHANT_MAP,
        "amount_heuristics": AXIS_STYLE_AMOUNT,
    },
}


def _import_class(path: str):
    mod_name, _, cls_name = path.rpartition(".")
    mod = importlib.import_module(mod_name)
    return getattr(mod, cls_name)


def _norm_rule_block(block: dict) -> dict:
    out = {}
    for cat, rules in block.items():
        out[cat] = {
            "exact": list(rules.get("exact") or []),
            "patterns": list(rules.get("patterns") or []),
        }
    return out


def _confidence(engine_cls) -> dict:
    return {
        "exact": float(getattr(engine_cls, "CONF_EXACT", 0.99)),
        "pattern": float(getattr(engine_cls, "CONF_PATTERN", 0.95)),
        "merchant": float(getattr(engine_cls, "CONF_MERCHANT", 0.90)),
        "upi": float(getattr(engine_cls, "CONF_UPI", 0.85)),
        "amount": float(getattr(engine_cls, "CONF_AMOUNT", 0.70)),
        "default": 0.5,
    }


def extract_rules(engine_cls, bank_key: str) -> dict:
    profile = BANK_PROFILES.get(bank_key)
    if not profile:
        raise ValueError(f"No BANK_PROFILES for {bank_key!r}")

    # SBI mutates DEBIT_RULES/CREDIT_RULES on init via words.json — dump post-merge.
    if bank_key == "sbi":
        instance = engine_cls()
        debit = getattr(instance, "DEBIT_RULES", {})
        credit = getattr(instance, "CREDIT_RULES", {})
        upi = getattr(instance, "UPI_MERCHANTS", {})
        source = f"{engine_cls.__module__}.{engine_cls.__name__} (post words.json merge)"
    else:
        debit = getattr(engine_cls, "DEBIT_RULES", {})
        credit = getattr(engine_cls, "CREDIT_RULES", {})
        upi = getattr(engine_cls, "UPI_MERCHANTS", {})
        source = f"{engine_cls.__module__}.{engine_cls.__name__}"

    return {
        "schema_version": 1,
        "bank_key": bank_key,
        "source_class": source,
        "match_semantics": dict(profile["match_semantics"]),
        "confidence": _confidence(engine_cls),
        "debit_rules": _norm_rule_block(debit),
        "credit_rules": _norm_rule_block(credit),
        "upi_merchants": dict(upi),
        "merchant_map": dict(profile.get("merchant_map") or {}),
        "amount_heuristics": dict(profile.get("amount_heuristics") or {}),
        "defaults": {
            "debit_category": "Others Debit",
            "credit_category": "Others Credit",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bank", choices=sorted(BANK_MODULES.keys()))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    cls = _import_class(BANK_MODULES[args.bank])
    payload = extract_rules(cls, args.bank)
    out = args.out or (BACKEND / "app" / "services" / "banks" / args.bank / "rules.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    print(
        f"  debit={len(payload['debit_rules'])} credit={len(payload['credit_rules'])} "
        f"upi={len(payload['upi_merchants'])} merchants={len(payload['merchant_map'])} "
        f"layers={payload['match_semantics']['layers']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
