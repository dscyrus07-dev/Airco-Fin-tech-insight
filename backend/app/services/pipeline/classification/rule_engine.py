"""Shared JSON-backed rule engine (Phase 2b)."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    category: str
    confidence: float
    source: str
    matched_rule: Optional[str] = None
    matched_keyword: Optional[str] = None


def default_rules_path(bank_key: str) -> Path:
    return Path(__file__).resolve().parents[2] / "banks" / bank_key / "rules.json"


def load_rules(path: Path | str) -> Dict[str, Any]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"rules.json must be an object: {p}")
    return data


class JsonRuleEngine:
    def __init__(
        self,
        rules: Dict[str, Any] | None = None,
        *,
        rules_path: Path | str | None = None,
        bank_key: str | None = None,
    ):
        if rules is None:
            if rules_path is None:
                if not bank_key:
                    raise ValueError("Provide rules, rules_path, or bank_key")
                rules_path = default_rules_path(bank_key)
            rules = load_rules(rules_path)
            self._rules_path = str(rules_path)
        else:
            self._rules_path = None

        self.bank_key = rules.get("bank_key") or bank_key or "unknown"
        self._rules = rules
        conf = rules.get("confidence") or {}
        self.CONF_EXACT = float(conf.get("exact", 0.99))
        self.CONF_PATTERN = float(conf.get("pattern", 0.95))
        self.CONF_MERCHANT = float(conf.get("merchant", 0.90))
        self.CONF_UPI = float(conf.get("upi", 0.85))
        self.CONF_AMOUNT = float(conf.get("amount", 0.70))
        self.CONF_DEFAULT = float(conf.get("default", 0.5))

        defaults = rules.get("defaults") or {}
        self._default_debit = defaults.get("debit_category", "Others Debit")
        self._default_credit = defaults.get("credit_category", "Others Credit")

        sem = rules.get("match_semantics") or {}
        self._layers = list(
            sem.get("layers")
            or ["exact_keyword", "pattern_match", "upi_merchant", "amount_heuristic", "default"]
        )
        self._is_debit_mode = str(sem.get("is_debit") or "debit_not_none")
        self._upi_gate = str(sem.get("upi_gate") or "upi_or_at")
        self._upi_debit_only = bool(sem.get("upi_debit_only", True))
        self._generic_fallback = bool(sem.get("generic_fallback", False))

        self._upi_merchants: Dict[str, str] = dict(rules.get("upi_merchants") or {})
        self._merchant_map: Dict[str, Any] = dict(rules.get("merchant_map") or {})
        self._amount_heuristics = rules.get("amount_heuristics") or {}

        self._debit_compiled = self._compile_block(rules.get("debit_rules") or {})
        self._credit_compiled = self._compile_block(rules.get("credit_rules") or {})
        self._generic_engine = None
        if self._generic_fallback:
            try:
                from app.services.banks._shared.generic_bank import GenericBankConfig, GenericRuleEngine
                self._generic_engine = GenericRuleEngine(
                    GenericBankConfig(
                        bank_key=self.bank_key,
                        bank_name=self.bank_key.upper(),
                        file_prefix=f"{self.bank_key}_report",
                        markers=[self.bank_key.upper()],
                    )
                )
            except Exception:
                logger.exception("Failed to init generic fallback for %s", self.bank_key)

        logger.info(
            "JsonRuleEngine[%s] debit=%d credit=%d upi=%d merchants=%d layers=%s",
            self.bank_key,
            len(self._debit_compiled),
            len(self._credit_compiled),
            len(self._upi_merchants),
            len(self._merchant_map),
            self._layers,
        )

    @staticmethod
    def _compile_block(block: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        compiled: Dict[str, Dict[str, Any]] = {}
        for cat, rules in block.items():
            exact = [str(kw).upper() for kw in (rules.get("exact") or [])]
            patterns = [re.compile(str(p), re.IGNORECASE) for p in (rules.get("patterns") or [])]
            compiled[cat] = {"exact": exact, "patterns": patterns}
        return compiled

    def _is_debit(self, txn: Dict[str, Any]) -> bool:
        debit = txn.get("debit")
        if self._is_debit_mode == "debit_positive":
            try:
                return debit is not None and float(debit) > 0
            except (TypeError, ValueError):
                return False
        if self._is_debit_mode == "debit_truthy":
            return bool(debit)
        return debit is not None

    def classify(
        self, transactions: Sequence[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        classified: List[Dict[str, Any]] = []
        unclassified: List[Dict[str, Any]] = []
        for txn in transactions:
            result = self._classify_single(txn)
            txn_copy = dict(txn)
            txn_copy["category"] = result.category
            txn_copy["confidence"] = result.confidence
            txn_copy["source"] = result.source
            txn_copy["matched_rule"] = result.matched_rule
            if result.matched_keyword is not None:
                txn_copy["matched_keyword"] = result.matched_keyword
            if result.category.startswith("Others"):
                unclassified.append(txn_copy)
            else:
                classified.append(txn_copy)
        logger.info(
            "Classification complete: %d classified, %d unclassified",
            len(classified),
            len(unclassified),
        )
        return classified, unclassified

    def _classify_single(self, txn: Dict[str, Any]) -> ClassificationResult:
        description = (txn.get("description") or "").upper()
        is_debit = self._is_debit(txn)
        rules = self._debit_compiled if is_debit else self._credit_compiled
        default_category = self._default_debit if is_debit else self._default_credit

        for layer in self._layers:
            if layer == "exact_keyword":
                hit = self._match_exact(description, rules)
                if hit:
                    return hit
            elif layer == "pattern_match":
                hit = self._match_pattern(description, rules)
                if hit:
                    return hit
            elif layer == "merchant_mapping":
                hit = self._classify_merchant(description, is_debit)
                if hit:
                    return hit
            elif layer == "upi_merchant":
                if (not self._upi_debit_only) or is_debit:
                    hit = self._classify_upi(description, path_only=False)
                    if hit:
                        return hit
            elif layer == "upi_path_merchant":
                hit = self._classify_upi_path(description)
                if hit:
                    return hit
            elif layer == "amount_heuristic":
                hit = self._classify_by_amount(txn, is_debit, description)
                if hit:
                    return hit
            elif layer == "generic_fallback":
                hit = self._classify_generic(txn)
                if hit:
                    return hit
            elif layer == "default":
                return ClassificationResult(
                    category=default_category,
                    confidence=self.CONF_DEFAULT,
                    source="rule_engine",
                    matched_rule="default",
                )

        return ClassificationResult(
            category=default_category,
            confidence=self.CONF_DEFAULT,
            source="rule_engine",
            matched_rule="default",
        )

    def _match_exact(self, description: str, rules: Dict[str, Dict[str, Any]]) -> Optional[ClassificationResult]:
        for category, compiled in rules.items():
            for keyword in compiled["exact"]:
                if keyword and keyword in description:
                    return ClassificationResult(
                        category=category,
                        confidence=self.CONF_EXACT,
                        source="rule_engine",
                        matched_rule="exact_keyword",
                        matched_keyword=keyword,
                    )
        return None

    def _match_pattern(self, description: str, rules: Dict[str, Dict[str, Any]]) -> Optional[ClassificationResult]:
        for category, compiled in rules.items():
            for pattern in compiled["patterns"]:
                if pattern.search(description):
                    return ClassificationResult(
                        category=category,
                        confidence=self.CONF_PATTERN,
                        source="rule_engine",
                        matched_rule="pattern_match",
                        matched_keyword=pattern.pattern,
                    )
        return None

    def _classify_merchant(self, description: str, is_debit: bool) -> Optional[ClassificationResult]:
        if not self._merchant_map:
            return None
        desc_lower = description.lower()
        for merchant, category_spec in self._merchant_map.items():
            if merchant not in desc_lower:
                continue
            if isinstance(category_spec, dict):
                category = category_spec.get("debit" if is_debit else "credit")
            else:
                category = category_spec
            if not category:
                continue
            return ClassificationResult(
                category=str(category),
                confidence=self.CONF_MERCHANT,
                source="rule_engine",
                matched_rule="merchant_mapping",
                matched_keyword=merchant,
            )
        return None

    def _classify_upi(self, description: str, *, path_only: bool = False) -> Optional[ClassificationResult]:
        description_lower = description.lower()
        if self._upi_gate == "upi_only":
            if "upi" not in description_lower:
                return None
        elif self._upi_gate == "always":
            pass
        else:
            if "upi" not in description_lower and "@" not in description_lower:
                return None
        if path_only:
            return None
        for merchant, category in self._upi_merchants.items():
            if merchant in description_lower:
                return ClassificationResult(
                    category=category,
                    confidence=self.CONF_UPI,
                    source="rule_engine",
                    matched_rule="upi_merchant",
                    matched_keyword=merchant,
                )
        return None

    def _classify_upi_path(self, description: str) -> Optional[ClassificationResult]:
        upi_match = re.match(r"UPI/([^/]+)/", description, re.IGNORECASE)
        if not upi_match:
            return None
        merchant_name = upi_match.group(1).lower()
        for merchant, category in self._upi_merchants.items():
            if merchant in merchant_name:
                return ClassificationResult(
                    category=category,
                    confidence=self.CONF_UPI,
                    source="rule_engine",
                    matched_rule="upi_path_merchant",
                    matched_keyword=merchant,
                )
        return None

    def _classify_generic(self, txn: Dict[str, Any]) -> Optional[ClassificationResult]:
        if not self._generic_engine:
            return None
        try:
            classified, unclassified = self._generic_engine.classify([txn])
        except Exception:
            logger.debug("generic fallback failed", exc_info=True)
            return None
        if not classified or unclassified:
            return None
        fallback = classified[0]
        category = str(fallback.get("category") or "").strip()
        if not category or category.startswith("Others"):
            return None
        return ClassificationResult(
            category=category,
            confidence=float(fallback.get("confidence") or self.CONF_MERCHANT),
            source="generic_rule_engine",
            matched_rule=fallback.get("matched_rule") or "generic_fallback",
            matched_keyword=fallback.get("matched_keyword"),
        )

    def _classify_by_amount(
        self, txn: Dict[str, Any], is_debit: bool, description: str
    ) -> Optional[ClassificationResult]:
        h = self._amount_heuristics or {}

        # HDFC/Canara style: debit or credit or 0 + upper tokens
        if "atm" in h or "subscription" in h:
            amount = txn.get("debit") or txn.get("credit") or 0
            try:
                amount_f = float(amount)
            except (TypeError, ValueError):
                amount_f = 0.0
            atm = h.get("atm") or {}
            if is_debit and amount_f > 0 and atm.get("enabled", True):
                mult = float(atm.get("multiple_of", 100) or 100)
                min_a = float(atm.get("min_amount", 500))
                max_a = float(atm.get("max_amount", 50000))
                tokens = [str(t).upper() for t in (atm.get("description_tokens") or ["ATM", "ATW"])]
                if amount_f % mult == 0 and min_a <= amount_f <= max_a:
                    if any(t in description.upper() for t in tokens):
                        return ClassificationResult(
                            category=str(atm.get("category", "ATM")),
                            confidence=self.CONF_AMOUNT,
                            source="rule_engine",
                            matched_rule=str(atm.get("matched_rule", "amount_atm")),
                        )
            sub = h.get("subscription") or {}
            if is_debit and sub.get("enabled", True):
                min_a = float(sub.get("min_amount", 99))
                max_a = float(sub.get("max_amount", 999))
                tokens = [str(t).upper() for t in (sub.get("description_tokens") or [])]
                if min_a <= amount_f <= max_a and any(t in description.upper() for t in tokens):
                    return ClassificationResult(
                        category=str(sub.get("category", "Entertainment")),
                        confidence=self.CONF_AMOUNT,
                        source="rule_engine",
                        matched_rule=str(sub.get("matched_rule", "amount_subscription")),
                    )

        amount_raw = txn.get("debit") if is_debit else txn.get("credit")
        try:
            amount_side = float(amount_raw) if amount_raw is not None else 0.0
        except (TypeError, ValueError):
            amount_side = 0.0
        if not amount_side or amount_side <= 0:
            return None

        emi = h.get("emi") or {}
        if emi.get("enabled", False) and is_debit and emi.get("debit_only", True):
            mult = float(emi.get("multiple_of", 100) or 100)
            min_a = float(emi.get("min_amount", 500))
            max_a = float(emi.get("max_amount", 100000))
            tokens = [str(t).lower() for t in (emi.get("description_tokens") or [])]
            desc_l = (txn.get("description") or "").lower()
            if amount_side % mult == 0 and min_a <= amount_side <= max_a:
                if any(t in desc_l for t in tokens):
                    return ClassificationResult(
                        category=str(emi.get("category", "Loan Payments")),
                        confidence=self.CONF_AMOUNT,
                        source="rule_engine",
                        matched_rule=str(emi.get("matched_rule", "amount_emi")),
                    )

        salary = h.get("salary") or {}
        if salary.get("enabled", False) and (not is_debit) and salary.get("credit_only", True):
            mult = float(salary.get("multiple_of", 1000) or 1000)
            min_a = float(salary.get("min_amount", 10000))
            tokens = [str(t).lower() for t in (salary.get("description_tokens") or [])]
            desc_l = (txn.get("description") or "").lower()
            if amount_side % mult == 0 and amount_side >= min_a:
                if any(t in desc_l for t in tokens):
                    return ClassificationResult(
                        category=str(salary.get("category", "Salary Credits")),
                        confidence=self.CONF_AMOUNT,
                        source="rule_engine",
                        matched_rule=str(salary.get("matched_rule", "amount_salary")),
                    )
        return None

    def get_statistics(self) -> Dict[str, Any]:
        debit_rules = sum(len(r["exact"]) + len(r["patterns"]) for r in self._debit_compiled.values())
        credit_rules = sum(len(r["exact"]) + len(r["patterns"]) for r in self._credit_compiled.values())
        return {
            "bank_key": self.bank_key,
            "debit_categories": len(self._debit_compiled),
            "credit_categories": len(self._credit_compiled),
            "debit_rules": debit_rules,
            "credit_rules": credit_rules,
            "upi_merchants": len(self._upi_merchants),
            "merchant_map": len(self._merchant_map),
            "total_rules": debit_rules + credit_rules,
            "rules_path": self._rules_path,
            "layers": list(self._layers),
        }


RuleEngine = JsonRuleEngine
