"""
ICICI Bank Unified Transaction Classifier
==========================================
Strict collision-resolution classifier for ICICI Bank transactions.

ICICI-specific transaction patterns:
- UPI/VPA@bank/... format with long alphanumeric IDs
- NEFT/... transfers
- B/F entry = opening balance (not a transaction)
- MODE** column: ECS, SI, ATM, etc.
- UPI withdrawals are debits, UPI deposits are credits

Collision resolution (same 14-layer architecture):
  1. Interest  2. ATM  3. GST  4. Charges  5. Refund
  6. Salary  7. Entity  8. ACH  9. Insurance  10. Fuel
  11. Bill  12. Payout  13. Transfer  14. Fallback
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .._shared.category_registry import normalize_category

logger = logging.getLogger(__name__)

DISPLAY_MAP: Dict[str, str] = {
    "BUSINESS_INCOME":   "Business Income",
    "BUSINESS_EXPENSE":  "Business Expense",
    "LOAN_DISBURSED":    "Loan Disbursal",
    "LOAN_REPAYMENT":    "Loan Repayment",
    "EMI_PAYMENT":       "Loan Payment / EMI",
    "MERCHANT_PAYOUT":   "Merchant Settlement",
    "UPI_TRANSFER":      "UPI Transfer",
    "WALLET_TRANSFER":   "Wallet Transfer",
    "OTA_INCOME":        "Travel Booking Income",
    "TRANSFER":          "Bank Transfer",
    "TRAVEL_EXPENSE":    "Travel Expense",
    "FOOD_EXPENSE":      "Food & Dining",
    "DELIVERY_EXPENSE":  "Delivery",
    "TRANSPORT_EXPENSE": "Transport",
    "SHOPPING_EXPENSE":  "Shopping",
    "GROCERY_EXPENSE":   "Grocery",
    "MEDICAL_EXPENSE":   "Medical & Health",
    "FITNESS_EXPENSE":   "Fitness & Sports",
    "PG_CHARGES":        "Payment Gateway Charges",
    "REFUND":            "Refund",
    "TRANSFER_IN":       "Bank Transfer",
    "TRANSFER_OUT":      "Transfer Out",
    "INTEREST_CREDIT":   "Interest Credit",
    "INTEREST_DEBIT":    "Interest Debit",
    "GST_CHARGES":       "GST Charges",
    "BANK_CHARGES":      "Bank Charges",
    "SALARY":            "Salary",
    "ATM_WITHDRAWAL":    "ATM Withdrawal",
    "UNCATEGORIZED":     "Uncategorised",
}


def _to_display(internal: str, direction: str) -> str:
    if internal == "TRANSFER":
        return "Bank Transfer" if direction == "credit" else "Transfer Out"
    return DISPLAY_MAP.get(internal, internal.replace("_", " ").title())


class ICICIClassifier:
    """
    Unified ICICI Bank transaction classifier.
    Loads rules from keywords.json with ICICI-specific collision overrides.
    """

    def __init__(self, keywords_file: Optional[str] = None):
        db = self._load_db(keywords_file)
        self._meta = db.get("metadata", {})
        self._build_normalization(db.get("text_normalization", {}))
        self._build_entity_lookup(db.get("entity_interpretation", {}))
        self._build_pattern_sets(db.get("pattern_detection", {}))
        logger.info(
            "ICICIClassifier loaded: %d entity aliases — v%s",
            len(self._entity_lookup),
            self._meta.get("version", "?"),
        )

    @staticmethod
    def _load_db(path: Optional[str]) -> Dict[str, Any]:
        candidates = [
            path,
            "/app/keywords.json",
            "/app/words.json",
            str(Path(__file__).resolve().parents[5] / "backend" / "words.json"),
            str(Path(__file__).resolve().parents[5] / "samples" / "icici" / "output" / "words.json"),
            str(Path(__file__).resolve().parents[5] / "keywords.json"),
            str(Path(__file__).resolve().parents[5] / "words (1).json"),
        ]
        for p in candidates:
            if not p:
                continue
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                continue
        logger.warning("No keyword database found; using empty rules")
        return {}

    def _build_normalization(self, tnorm: Dict[str, Any]) -> None:
        self._strip_regex = [
            re.compile(p, re.IGNORECASE)
            for p in tnorm.get("strip_patterns", [])
        ]
        self._replace_rules: List[Tuple[re.Pattern, str]] = []
        for old, new in tnorm.get("replace_rules", {}).items():
            if old.isalpha() and len(old) <= 4:
                pat = re.compile(r"\b" + re.escape(old) + r"\b", re.IGNORECASE)
            else:
                pat = re.compile(re.escape(old), re.IGNORECASE)
            self._replace_rules.append((pat, new))

    def _normalize(self, text: str) -> str:
        t = text.lower().strip()
        # Remove ICICI-specific long hex transaction IDs
        t = re.sub(r'\bibl[0-9a-f]{10,}\b', '', t)
        for pat in self._strip_regex:
            t = pat.sub("", t)
        for pat, replacement in self._replace_rules:
            t = pat.sub(replacement, t)
        return " ".join(t.split())

    def _build_entity_lookup(self, entity_interp: Dict[str, Any]) -> None:
        self._entity_lookup: Dict[str, Dict] = {}
        for group_name, group_data in entity_interp.items():
            if group_name.startswith("_") or not isinstance(group_data, dict):
                continue
            for alias, cfg in group_data.items():
                if alias.startswith("_") or not isinstance(cfg, dict):
                    continue
                key = alias.lower()
                if "credit" in cfg and "debit" in cfg:
                    cc = cfg["credit"]
                    dc = cfg["debit"]
                    credit_cat = cc.get("category", "TRANSFER_IN")
                    debit_cat  = dc.get("category", "TRANSFER_OUT")
                    priority   = max(cc.get("priority", 50), dc.get("priority", 50))
                    g          = cc.get("group", group_name)
                elif "category" in cfg:
                    credit_cat = debit_cat = cfg["category"]
                    priority   = cfg.get("priority", 50)
                    g          = cfg.get("group", group_name)
                else:
                    continue
                existing = self._entity_lookup.get(key)
                if existing is None or priority > existing["priority"]:
                    self._entity_lookup[key] = {
                        "credit_cat": credit_cat,
                        "debit_cat":  debit_cat,
                        "priority":   priority,
                        "group":      g,
                    }
        self._sorted_aliases: List[str] = sorted(
            self._entity_lookup.keys(), key=len, reverse=True
        )

    def _build_pattern_sets(self, pd_cfg: Dict[str, Any]) -> None:
        def ll(key: str) -> List[str]:
            return [p.lower() for p in pd_cfg.get(key, [])]

        self._upi_handles:         List[str] = ll("upi_handle")
        self._loan_patterns:       List[str] = ll("loan_patterns")
        self._refund_patterns:     List[str] = ll("refund_patterns")
        self._bill_patterns:       List[str] = ll("bill_payment_patterns")
        self._insurance_patterns:  List[str] = ll("insurance_patterns")
        self._transfer_patterns:   List[str] = ll("transfer_patterns")
        self._settlement_patterns: List[str] = ll("settlement_patterns")
        self._fuel_patterns:       List[str] = ll("fuel_travel_patterns")

        self._interest_tokens: List[str] = [
            "interest credit", "interest debit",
            "int credit", "int debit", "int cr", "int dr",
            "interest earned", "interest charged",
        ]
        self._atm_tokens: List[str] = [
            "atm", "cash withdrawal", "atm cash", "atm wdl",
        ]
        self._gst_tokens: List[str] = ["cgst", "sgst", "igst", " gst"]
        self._charge_tokens: List[str] = [
            "bank charges", "service charge", "processing fee",
            "annual fee", "card fee", "late payment charge",
            "cheque bounce", "sms charge", "min bal charge", "minimum balance",
            "non-maintenance", "non maintenance",
        ]
        self._refund_tokens: List[str] = list({
            *self._refund_patterns,
            "refund", "reversal", "chargeback", "cashback", "cash back",
        })
        self._salary_tokens: List[str] = [
            "salary", "payroll", "wages", "pay slip",
            "sal credit", "sal cr", "monthly salary",
        ]
        self._ach_tokens: List[str] = [
            "ach d", "ach debit", "nach", "ecs ", "auto debit",
            "si debit", "standing instruction",
        ]

    def _detect_entity(self, norm: str) -> Optional[Tuple[str, str, int, str]]:
        for alias in self._sorted_aliases:
            if alias in norm:
                cfg = self._entity_lookup[alias]
                return cfg["credit_cat"], cfg["debit_cat"], cfg["priority"], alias
        return None

    @staticmethod
    def _first_hit(tokens: List[str], text: str) -> Optional[str]:
        for tok in tokens:
            if tok in text:
                return tok
        return None

    def _resolve(
        self, raw: str, norm: str, direction: str
    ) -> Tuple[str, int, str, str]:
        is_debit  = direction == "debit"
        is_credit = direction == "credit"

        tok = self._first_hit(self._interest_tokens, norm)
        if tok:
            return ("INTEREST_CREDIT" if is_credit else "INTEREST_DEBIT"), 100, "override", tok

        if is_debit:
            tok = self._first_hit(self._atm_tokens, raw) or self._first_hit(self._atm_tokens, norm)
            if tok:
                return "ATM_WITHDRAWAL", 99, "override", tok

        tok = self._first_hit(self._gst_tokens, norm)
        if tok:
            return "GST_CHARGES", 95, "override", tok.strip()

        tok = self._first_hit(self._charge_tokens, norm)
        if tok:
            return "BANK_CHARGES", 90, "override", tok

        tok = self._first_hit(self._refund_tokens, norm) or self._first_hit(self._refund_tokens, raw)
        if tok:
            return "REFUND", 100, "override", tok

        if is_credit:
            tok = self._first_hit(self._salary_tokens, norm) or self._first_hit(self._salary_tokens, raw)
            if tok:
                return "SALARY", 95, "override", tok

        entity = self._detect_entity(norm)
        if entity:
            credit_cat, debit_cat, priority, alias = entity
            return (credit_cat if is_credit else debit_cat), min(100, priority), "entity", alias

        if is_debit:
            tok = self._first_hit(self._ach_tokens, norm) or self._first_hit(self._loan_patterns, norm)
            if tok:
                return "EMI_PAYMENT", 85, "pattern", tok

        if is_debit:
            tok = self._first_hit(self._insurance_patterns, norm)
            if tok:
                return "EMI_PAYMENT", 80, "pattern", tok

        if is_debit:
            tok = self._first_hit(self._fuel_patterns, norm)
            if tok:
                return "TRANSPORT_EXPENSE", 85, "pattern", tok

        tok = self._first_hit(self._bill_patterns, norm)
        if tok:
            return ("BANK_CHARGES" if is_debit else "TRANSFER_IN"), 80, "pattern", tok

        if is_credit:
            tok = self._first_hit(self._settlement_patterns, norm)
            if tok:
                return "MERCHANT_PAYOUT", 80, "pattern", tok

        tok = self._first_hit(self._transfer_patterns, norm)
        if tok:
            return ("TRANSFER_IN" if is_credit else "TRANSFER_OUT"), 75, "keyword", tok

        return ("TRANSFER_IN" if is_credit else "TRANSFER_OUT"), 70, "fallback", ""

    def classify(self, row) -> Dict[str, Any]:
        description = str(row.get("Description", "")).strip()
        debit  = float(row.get("Debit",  0) or 0)
        credit = float(row.get("Credit", 0) or 0)

        _null = {
            "internal_category": "UNCATEGORIZED",
            "display_category":  "Uncategorised",
            "confidence_score":  0,
            "matched_rule":      "fallback",
            "matched_token":     "",
        }

        if not description:
            return _null
        if credit > 0:
            direction = "credit"
        elif debit > 0:
            direction = "debit"
        else:
            return _null

        raw  = description.lower()
        norm = self._normalize(description)
        internal, confidence, rule, token = self._resolve(raw, norm, direction)
        display = _to_display(internal, direction)

        return {
            "internal_category": normalize_category(
                internal,
                is_debit=bool(debit),
            ),
            "display_category":  display,
            "confidence_score":  confidence,
            "matched_rule":      rule,
            "matched_token":     token,
        }

    def get_all_categories(self) -> Dict[str, List[str]]:
        return {
            "credit": [
                "Salary", "Loan Disbursal", "Business Income",
                "Travel Booking Income", "Merchant Settlement",
                "UPI Transfer", "Bank Transfer", "Interest Credit", "Refund",
            ],
            "debit": [
                "Loan Payment / EMI", "ATM Withdrawal",
                "Business Expense", "Travel Expense",
                "Food & Dining", "Transport", "Shopping",
                "Grocery", "Medical & Health", "Fitness & Sports", "Delivery",
                "GST Charges", "Bank Charges", "Payment Gateway Charges",
                "UPI Transfer", "Transfer Out",
            ],
        }

    def get_category_stats(self) -> Dict[str, Any]:
        return {
            "entity_aliases": len(self._entity_lookup),
            "source":         "keywords.json",
            "version":        self._meta.get("version", "unknown"),
        }


BankingGradeClassifier = ICICIClassifier
