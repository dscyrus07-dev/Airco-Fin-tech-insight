"""
Airco Insights - Paytm Bank Rule Engine
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .._shared.category_registry import normalize_category
from .._shared.generic_bank import GenericBankConfig, GenericRuleEngine

CONFIG = GenericBankConfig(
    bank_key="paytm",
    bank_name="Paytm Bank",
    file_prefix="paytm",
    markers=["paytm payments bank", "account statement for:", "paytm"],
    support_aliases=["paytm", "paytm bank", "paytm payments bank"],
)

logger = logging.getLogger(__name__)


@dataclass
class RuleClassificationResult:
    category: str
    confidence: float
    source: str
    matched_rule: Optional[str] = None
    matched_keyword: Optional[str] = None


class PaytmRuleEngine:
    def __init__(self, rules_path: Optional[str] = None, keywords_file: Optional[str] = None):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        from app.services.pipeline.classification.rule_engine import (
            JsonRuleEngine,
            default_rules_path,
        )
        path = rules_path or str(default_rules_path("paytm"))
        self._engine = JsonRuleEngine(rules_path=path, bank_key="paytm")
        self.keywords_file = keywords_file or self._resolve_keywords_file()
        self.generic_rule_engine = GenericRuleEngine(CONFIG, keywords_file=self.keywords_file)

    def classify(self, transactions: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        processed: List[Dict[str, Any]] = []
        unclassified: List[Dict[str, Any]] = []
        for txn in transactions:
            result = self._classify_single(txn)
            txn_copy = dict(txn)
            is_debit = bool(txn.get("debit"))
            txn_copy["category"] = normalize_category(result.category, is_debit=is_debit)
            txn_copy["confidence"] = result.confidence
            txn_copy["source"] = result.source
            txn_copy["matched_rule"] = result.matched_rule
            txn_copy["matched_keyword"] = result.matched_keyword
            processed.append(txn_copy)
            if txn_copy["category"].startswith("Others"):
                unclassified.append(txn_copy)
        return processed, unclassified

    # Regex to extract merchant name from Paytm UPI narration:
    # "Money Sent using UPI | Paid to swiggy@ybl"  → "swiggy"
    # "Money Received using UPI | Received from rakesh@okaxis" → "rakesh"
    _UPI_PAYEE_RE = re.compile(
        r"(?:paid to|received from|sent to)\s+([a-z0-9_.\-]+)@",
        re.IGNORECASE,
    )

    def _classify_single(self, txn: Dict[str, Any]) -> RuleClassificationResult:
        description = str(txn.get("description") or "").upper()
        is_debit = bool(txn.get("debit"))

        # ── Try JsonRuleEngine first (rules.json exact/pattern + words.json fallback) ──
        jrc, jru = self._engine.classify([txn])
        if jrc and not jru:
            fb = jrc[0]
            cat = str(fb.get("category") or "")
            if cat and not cat.startswith("Others"):
                return RuleClassificationResult(
                    cat, float(fb.get("confidence") or 0.85),
                    str(fb.get("source") or "rule_engine"),
                    fb.get("matched_rule"), fb.get("matched_keyword"),
                )

        # ── For UPI sends/receives: extract merchant and run entity lookup ─────
        is_upi_narration = (
            "MONEY SENT USING UPI" in description
            or "MONEY RECEIVED USING UPI" in description
            or "PAID USING YOUR BANK ACCOUNT" in description
        )
        if is_upi_narration:
            match = self._UPI_PAYEE_RE.search(str(txn.get("description") or ""))
            if match:
                merchant_name = match.group(1).lower()
                merchant_txn = dict(txn)
                merchant_txn["description"] = merchant_name
                m_classified, m_unclassified = self.generic_rule_engine.classify([merchant_txn])
                if m_classified and not m_unclassified:
                    fb = m_classified[0]
                    cat = str(fb.get("category") or "")
                    if cat and not cat.startswith("Others"):
                        return RuleClassificationResult(
                            cat, float(fb.get("confidence") or 0.85),
                            "entity_lookup", fb.get("matched_rule"), merchant_name,
                        )
            # No merchant match → plain Transfer
            label = "upi_send" if is_debit else "upi_receive"
            return RuleClassificationResult("Transfer", 0.88, "rule_engine", label, "UPI")

        # ── AMOUNT DEBITED — check entity lookup first (e.g. Bajaj Finance) ───
        if "AMOUNT DEBITED" in description:
            generic_classified, generic_unclassified = self.generic_rule_engine.classify([txn])
            if generic_classified and not generic_unclassified:
                fb = generic_classified[0]
                cat = str(fb.get("category") or "")
                if cat and not cat.startswith("Others"):
                    return RuleClassificationResult(
                        cat, float(fb.get("confidence") or 0.82),
                        str(fb.get("source") or "entity_lookup"), fb.get("matched_rule"), fb.get("matched_keyword"),
                    )
            return RuleClassificationResult("Transfer", 0.84, "rule_engine", "amount_debited", "AMOUNT DEBITED")

        # ── Final fallback: use JsonRuleEngine result (may be Others) ──────────
        if jrc:
            fb = jrc[0]
            return RuleClassificationResult(
                str(fb.get("category") or ("Others Debit" if is_debit else "Others Credit")),
                float(fb.get("confidence") or 0.5),
                str(fb.get("source") or "rule_engine"),
                fb.get("matched_rule"), fb.get("matched_keyword"),
            )

        return RuleClassificationResult(
            "Others Debit" if is_debit else "Others Credit",
            0.5,
            "rule_engine",
            "default",
        )

    def _resolve_keywords_file(self) -> Optional[str]:
        current = Path(__file__).resolve()
        repo_root = None
        for parent in current.parents:
            if parent.name == "backend":
                repo_root = parent.parent
                break
        if repo_root is None:
            repo_root = current.parents[-1]
        candidates = [
            repo_root / "samples" / "paytm" / "output" / "words.json",
            repo_root / "backend" / "words.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None
