from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .._shared.category_registry import normalize_category
from .._shared.generic_bank import GenericBankConfig, GenericClassifier, GenericRuleEngine


CONFIG = GenericBankConfig(
    bank_key="union",
    bank_name="Union Bank of India",
    file_prefix="union",
    markers=["union bank of india", "statement of account", "ubin"],
    support_aliases=["union", "union bank", "union bank of india", "ubi"],
)


@dataclass
class RuleClassificationResult:
    category: str
    confidence: float
    source: str
    matched_rule: Optional[str] = None
    matched_keyword: Optional[str] = None


class UnionRuleEngine:
    def __init__(self, rules_path: Optional[str] = None, keywords_file: Optional[str] = None):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        from app.services.pipeline.classification.rule_engine import (
            JsonRuleEngine,
            default_rules_path,
        )
        path = rules_path or str(default_rules_path("union"))
        self._engine = JsonRuleEngine(rules_path=path, bank_key="union")
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

    # Prefixes whose payload should be re-classified via entity lookup
    _PAYLOAD_STRIP_RE = re.compile(
        r"^(?:UPIAR|UPIAB|IMPSAB|NEFT|RTGS|POS)[:/]\s*",
        re.IGNORECASE,
    )

    def _entity_lookup_on_payload(self, description: str, txn: Dict[str, Any]) -> Optional[RuleClassificationResult]:
        """Strip protocol prefix, run entity lookup on the remaining payload."""
        payload = self._PAYLOAD_STRIP_RE.sub("", description).strip()
        if not payload or payload == description:
            return None
        probe = dict(txn)
        probe["description"] = payload
        classified, unclassified = self.generic_rule_engine.classify([probe])
        if classified and not unclassified:
            fb = classified[0]
            cat = str(fb.get("category") or "")
            if cat and not cat.startswith("Others"):
                return RuleClassificationResult(
                    cat, float(fb.get("confidence") or 0.82),
                    "entity_lookup", fb.get("matched_rule"), fb.get("matched_keyword"),
                )
        return None

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

        # ── Entity lookup on payload for protocol-prefixed narrations ──────────
        if any(description.startswith(p) for p in ("UPIAR/", "UPIAB/", "IMPSAB/", "NEFT:", "NEFT/", "RTGS:", "POS:")):
            entity_result = self._entity_lookup_on_payload(description, txn)
            if entity_result:
                return entity_result
            if description.startswith("POS:"):
                return RuleClassificationResult("Shopping", 0.84, "rule_engine", "pos_fallback", "POS:")
            return RuleClassificationResult("Transfer", 0.88, "rule_engine", "protocol_prefix", description[:8])

        if "/CR/" in description:
            return RuleClassificationResult("Transfer", 0.88, "rule_engine", "cr_pattern", "/CR/")
        if "/DR/" in description and any(token in description for token in ("PAYTM", "BHARATPE", "POS/")):
            return RuleClassificationResult("Shopping", 0.84, "rule_engine", "dr_merchant", "/DR/")
        if "/DR/" in description:
            return RuleClassificationResult("Transfer", 0.82, "rule_engine", "dr_pattern", "/DR/")
        if re.fullmatch(r"\d{12,20}/[0-9A-Z]{6,20}/\d{10,20}", description):
            return RuleClassificationResult("Transfer", 0.84, "rule_engine", "numeric_transfer", "NUMERIC_TRANSFER")

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
            category="Others Debit" if is_debit else "Others Credit",
            confidence=0.5,
            source="rule_engine",
            matched_rule="default",
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
        candidates = [repo_root / "samples" / "union" / "output" / "words.json", repo_root / "backend" / "words.json"]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None


class UnionClassifier(GenericClassifier):
    def __init__(self, keywords_file: Optional[str] = None):
        super().__init__(CONFIG, keywords_file=keywords_file)

