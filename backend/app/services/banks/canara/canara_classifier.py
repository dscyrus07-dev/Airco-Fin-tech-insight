"""
Airco Insights — Canara Bank Classifier
=========================================
Full-grade classifier for Canara Bank transactions.
Uses words.json rule loading with entity lookup, normalization,
UPI handle detection, and confidence scoring.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .._shared.category_registry import normalize_category

logger = logging.getLogger(__name__)


def _to_display(internal: str, direction: str) -> str:
    return normalize_category(internal, is_debit=(direction == "debit"))


class CanaraClassifier:
    """
    Canara Bank transaction classifier.
    Mirrors HDFCClassifier architecture — words.json driven,
    entity lookup, normalization, L1-L4 override tiers.
    """

    BANK_NAME = "Canara"

    # Confidence tiers
    CONF_L1 = 99   # entity / exact bank-rule override
    CONF_L2 = 90   # pattern_detection keyword hit
    CONF_L3 = 75   # generic description keyword
    CONF_L4 = 60   # heuristic / amount-band
    CONF_DEFAULT = 50

    def __init__(self, keywords_file: Optional[str] = None):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._db = self._load_db(keywords_file)
        self._build_normalization(self._db.get("text_normalization", {}))
        self._build_entity_lookup(self._db.get("entity_interpretation", {}))
        self._build_pattern_sets(self._db.get("pattern_detection", {}))

    # ------------------------------------------------------------------
    # DB loading
    # ------------------------------------------------------------------
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
                import json
                try:
                    return json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    pass
        self.logger.warning("words.json not found — using empty rule set")
        return {}

    # ------------------------------------------------------------------
    # Build internal lookup structures
    # ------------------------------------------------------------------
    def _build_normalization(self, tnorm: Dict[str, Any]) -> None:
        self._norm_map: Dict[str, str] = {}
        for canonical, aliases in tnorm.items():
            if isinstance(aliases, list):
                for alias in aliases:
                    self._norm_map[str(alias).upper()] = canonical.upper()

    def _normalize(self, text: str) -> str:
        words = text.upper().split()
        return " ".join(self._norm_map.get(w, w) for w in words)

    def _build_entity_lookup(self, entity_interp: Dict[str, Any]) -> None:
        self._entity_map: Dict[str, Tuple[str, str, int, str]] = {}
        for token, info in entity_interp.items():
            if not isinstance(info, dict):
                continue
            cat = info.get("category", "")
            direction = info.get("direction", "both")
            conf = int(info.get("confidence", self.CONF_L1))
            source = info.get("source", "entity")
            self._entity_map[token.upper()] = (cat, direction, conf, source)

    def _build_pattern_sets(self, pd_cfg: Dict[str, Any]) -> None:
        self._pat_sets: Dict[str, Tuple[List[str], str, str]] = {}
        for key, block in pd_cfg.items():
            if not isinstance(block, dict):
                continue
            tokens = [t.upper() for t in block.get("keywords", [])]
            category = block.get("category", "")
            direction = block.get("direction", "both")
            self._pat_sets[key] = (tokens, category, direction)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def ll(key: str) -> List[str]:
        return []

    def _detect_entity(self, norm: str) -> Optional[Tuple[str, str, int, str]]:
        for token, info in self._entity_map.items():
            if token in norm:
                return info
        return None

    @staticmethod
    def _first_hit(tokens: List[str], text: str) -> Optional[str]:
        for t in tokens:
            if t in text:
                return t
        return None

    def _resolve(
        self,
        raw: str,
        norm: str,
        direction: str,
    ) -> Tuple[str, int, str, str]:
        """
        Multi-layer resolution:
        L1 → entity lookup
        L2 → pattern_detection keyword
        L3 → generic keywords
        L4 → heuristic
        """
        # L1: entity lookup
        entity = self._detect_entity(norm)
        if entity:
            cat, ent_dir, conf, src = entity
            if ent_dir in ("both", direction):
                return _to_display(cat, direction), conf, src, cat

        # L2: pattern_detection blocks
        for _key, (tokens, category, pat_dir) in self._pat_sets.items():
            if pat_dir not in ("both", direction):
                continue
            hit = self._first_hit(tokens, norm)
            if hit:
                return _to_display(category, direction), self.CONF_L2, "pattern_detection", category

        # L3: generic keyword heuristics (Canara-specific narration patterns)
        if direction == "debit":
            if any(k in norm for k in ("ATM", "ATW", "CASH W")):
                return _to_display("ATM_WITHDRAWAL", direction), self.CONF_L3, "keyword", "ATM_WITHDRAWAL"
            if any(k in norm for k in ("SWIGGY", "ZOMATO", "FOOD", "RESTAURANT")):
                return _to_display("FOOD", direction), self.CONF_L3, "keyword", "FOOD"
            if any(k in norm for k in ("AMAZON", "FLIPKART", "MYNTRA", "MEESHO", "NYKAA")):
                return _to_display("SHOPPING", direction), self.CONF_L3, "keyword", "SHOPPING"
            if any(k in norm for k in ("UBER", "OLA", "PETROL", "FUEL", "IRCTC", "FASTAG")):
                return _to_display("TRANSPORT", direction), self.CONF_L3, "keyword", "TRANSPORT"
            if any(k in norm for k in ("EMI", "LOAN", "NACH", "ECS", "SI DEBIT", "STANDING")):
                return _to_display("LOAN_REPAYMENT", direction), self.CONF_L3, "keyword", "LOAN_REPAYMENT"
            if any(k in norm for k in ("ELECTRICITY", "BROADBAND", "MOBILE", "RECHARGE", "AIRTEL", "JIO")):
                return _to_display("BILL_PAYMENT", direction), self.CONF_L3, "keyword", "BILL_PAYMENT"
            if any(k in norm for k in ("NETFLIX", "HOTSTAR", "PRIME", "SPOTIFY", "SUBSCRIPTION")):
                return _to_display("ENTERTAINMENT", direction), self.CONF_L3, "keyword", "ENTERTAINMENT"
            if any(k in norm for k in ("INSURANCE", "LIC", "PREMIUM")):
                return _to_display("INSURANCE", direction), self.CONF_L3, "keyword", "INSURANCE"
            if any(k in norm for k in ("SCHOOL", "COLLEGE", "TUITION", "FEES", "EDUCATION")):
                return _to_display("EDUCATION", direction), self.CONF_L3, "keyword", "EDUCATION"
            if any(k in norm for k in ("HOSPITAL", "PHARMACY", "MEDICAL", "CLINIC", "DOCTOR")):
                return _to_display("HEALTH", direction), self.CONF_L3, "keyword", "HEALTH"
            if "UPI" in norm or "@" in norm:
                return _to_display("UPI_TRANSFER", direction), self.CONF_L4, "upi_heuristic", "UPI_TRANSFER"
        else:  # credit
            if any(k in norm for k in ("SALARY", "SAL CR", "PAYROLL", "WAGES")):
                return _to_display("SALARY", direction), self.CONF_L2, "keyword", "SALARY"
            if any(k in norm for k in ("REFUND", "REVERSAL", "CASHBACK")):
                return _to_display("REFUND", direction), self.CONF_L3, "keyword", "REFUND"
            if any(k in norm for k in ("INTEREST", "INT CR", "INTCR")):
                return _to_display("INTEREST", direction), self.CONF_L3, "keyword", "INTEREST"
            if any(k in norm for k in ("LOAN", "DISBURSAL", "DISBURSEMENT")):
                return _to_display("LOAN_CREDIT", direction), self.CONF_L3, "keyword", "LOAN_CREDIT"

        # Default
        fallback = "OTHERS_DEBIT" if direction == "debit" else "OTHERS_CREDIT"
        return _to_display(fallback, direction), self.CONF_DEFAULT, "default", fallback

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def classify(self, row: Any) -> Dict[str, Any]:
        if isinstance(row, dict):
            desc = str(row.get("description") or row.get("narration") or "")
            debit = float(row.get("debit") or 0)
            credit = float(row.get("credit") or 0)
        else:
            desc = str(getattr(row, "description", "") or getattr(row, "narration", "") or "")
            debit = float(getattr(row, "debit", 0) or 0)
            credit = float(getattr(row, "credit", 0) or 0)

        direction = "debit" if debit > 0 else "credit"
        norm = self._normalize(desc)
        display, conf, source, internal = self._resolve(desc, norm, direction)

        return {
            "category": display,
            "confidence": conf,
            "source": source,
            "internal_category": internal,
            "direction": direction,
        }

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


__all__ = ["CanaraClassifier"]
