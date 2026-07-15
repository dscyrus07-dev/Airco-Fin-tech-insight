"""
Airco Insights — IDFC Bank Classifier
=======================================
Full-grade classifier mirroring HDFCClassifier:
words.json rule loading, entity lookup, L1-L4 tiers, UPI heuristics.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .._shared.category_registry import normalize_category

logger = logging.getLogger(__name__)


def _to_display(internal: str, direction: str) -> str:
    return normalize_category(internal, is_debit=(direction == "debit"))


class IDFCClassifier:
    """IDFC Bank transaction classifier (HDFC-grade)."""

    BANK_NAME = "IDFC Bank"
    CONF_L1 = 99; CONF_L2 = 90; CONF_L3 = 75; CONF_L4 = 60; CONF_DEFAULT = 50

    def __init__(self, keywords_file: Optional[str] = None):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._db = self._load_db(keywords_file)
        self._build_normalization(self._db.get("text_normalization", {}))
        self._build_entity_lookup(self._db.get("entity_interpretation", {}))
        self._build_pattern_sets(self._db.get("pattern_detection", {}))

    def _load_db(self, path: Optional[str]) -> Dict[str, Any]:
        candidates = []
        if path:
            candidates.append(Path(path))
        base = Path(__file__).resolve().parent
        for _ in range(6):
            candidates.append(base / "words.json")
            base = base.parent
        for p in candidates:
            if p.exists():
                try:
                    return json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    pass
        return {}

    def _build_normalization(self, tnorm: Dict[str, Any]) -> None:
        self._norm_map: Dict[str, str] = {}
        for canonical, aliases in tnorm.items():
            if isinstance(aliases, list):
                for alias in aliases:
                    self._norm_map[str(alias).upper()] = canonical.upper()

    def _normalize(self, text: str) -> str:
        return " ".join(self._norm_map.get(w, w) for w in text.upper().split())

    def _build_entity_lookup(self, entity_interp: Dict[str, Any]) -> None:
        self._entity_map: Dict[str, Tuple[str, str, int, str]] = {}
        for token, info in entity_interp.items():
            if isinstance(info, dict):
                self._entity_map[token.upper()] = (
                    info.get("category", ""), info.get("direction", "both"),
                    int(info.get("confidence", self.CONF_L1)), info.get("source", "entity"),
                )

    def _build_pattern_sets(self, pd_cfg: Dict[str, Any]) -> None:
        self._pat_sets: Dict[str, Tuple[List[str], str, str]] = {}
        for key, block in pd_cfg.items():
            if isinstance(block, dict):
                self._pat_sets[key] = (
                    [t.upper() for t in block.get("keywords", [])],
                    block.get("category", ""), block.get("direction", "both"),
                )

    def _resolve(self, raw: str, norm: str, direction: str) -> Tuple[str, int, str, str]:
        for token, (cat, ent_dir, conf, src) in self._entity_map.items():
            if token in norm and ent_dir in ("both", direction):
                return _to_display(cat, direction), conf, src, cat
        for _, (tokens, category, pat_dir) in self._pat_sets.items():
            if pat_dir in ("both", direction) and any(t in norm for t in tokens):
                return _to_display(category, direction), self.CONF_L2, "pattern_detection", category
        if direction == "debit":
            for k, cat in [("ATM", "ATM_WITHDRAWAL"), ("EMI", "LOAN_REPAYMENT"), ("NACH", "LOAN_REPAYMENT"),
                           ("SWIGGY", "FOOD"), ("ZOMATO", "FOOD"), ("AMAZON", "SHOPPING"), ("FLIPKART", "SHOPPING"),
                           ("UBER", "TRANSPORT"), ("OLA", "TRANSPORT"), ("NETFLIX", "ENTERTAINMENT"),
                           ("ELECTRICITY", "BILL_PAYMENT"), ("INSURANCE", "INSURANCE")]:
                if k in norm: return _to_display(cat, direction), self.CONF_L3, "keyword", cat
            if "UPI" in norm or "@" in norm:
                return _to_display("UPI_TRANSFER", direction), self.CONF_L4, "upi_heuristic", "UPI_TRANSFER"
        else:
            for k, cat in [("SALARY", "SALARY"), ("PAYROLL", "SALARY"), ("REFUND", "REFUND"),
                           ("CASHBACK", "REFUND"), ("INTEREST", "INTEREST"), ("DISBURSAL", "LOAN_CREDIT")]:
                if k in norm: return _to_display(cat, direction), self.CONF_L3, "keyword", cat
        fallback = "OTHERS_DEBIT" if direction == "debit" else "OTHERS_CREDIT"
        return _to_display(fallback, direction), self.CONF_DEFAULT, "default", fallback

    def classify(self, row: Any) -> Dict[str, Any]:
        if isinstance(row, dict):
            desc = str(row.get("description") or row.get("particulars") or "")
            debit = float(row.get("debit") or 0); credit = float(row.get("credit") or 0)
        else:
            desc = str(getattr(row, "description", "") or getattr(row, "particulars", "") or "")
            debit = float(getattr(row, "debit", 0) or 0); credit = float(getattr(row, "credit", 0) or 0)
        direction = "debit" if debit > 0 else "credit"
        norm = self._normalize(desc)
        display, conf, source, internal = self._resolve(desc, norm, direction)
        return {"category": display, "confidence": conf, "source": source,
                "internal_category": internal, "direction": direction}

    def get_all_categories(self) -> Dict[str, List[str]]:
        """Return all possible display categories grouped by direction."""
        return {
            "credit": [
                "Salary", "Interest Income", "Refund", "Loan Disbursed",
                "Transfer", "Cashback", "Business Income",
            ],
            "debit": [
                "Loan Payment", "ATM Withdrawal", "Transfer",
                "Food", "Transport", "Shopping", "Bill Payment",
                "Bank Charges", "Medical", "Entertainment", "Travel",
                "Business Expense", "Others Debit",
            ],
        }

    def get_category_stats(self) -> Dict[str, Any]:
        return {
            "bank": self.BANK_NAME,
            "entity_count": len(self._entity_map),
            "pattern_sets": len(self._pat_sets),
            "norm_rules": len(self._norm_map),
        }

__all__ = ["IDFCClassifier"]
