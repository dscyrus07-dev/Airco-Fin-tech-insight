"""
Airco Insights - IDFC Bank Rule Engine
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .._shared.category_registry import normalize_category
from .._shared.generic_bank import GenericBankConfig, GenericRuleEngine

CONFIG = GenericBankConfig(
    bank_key="idfc",
    bank_name="IDFC Bank",
    file_prefix="idfc",
    markers=["idfc first bank", "idfc bank", "statement of account", "idfb"],
    support_aliases=["idfc", "idfc bank", "idfc first", "idfc first bank"],
)

logger = logging.getLogger(__name__)


@dataclass
class RuleClassificationResult:
    category: str
    confidence: float
    source: str
    matched_rule: Optional[str] = None
    matched_keyword: Optional[str] = None


class IDFCRuleEngine:
    def __init__(self, keywords_file: Optional[str] = None):
        self.keywords_file = keywords_file or self._resolve_keywords_file()
        self.generic_rule_engine = GenericRuleEngine(CONFIG, keywords_file=self.keywords_file)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

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

    def _classify_single(self, txn: Dict[str, Any]) -> RuleClassificationResult:
        description = str(txn.get("description") or "").upper()
        is_debit = bool(txn.get("debit"))

        exact_rules = [
            ("NACH/BAJAJ FINANCE", "Loan Payment", 0.99, "bajaj_nach"),
            ("NACH/TVSCREDITSERVICES", "Loan Payment", 0.99, "tvs_nach"),
            ("TVS CREDIT SERVICES", "Loan Payment", 0.96, "tvs_credit"),
            ("NACH/SHRIRAMCITYUNIONFINA", "Loan Payment", 0.99, "shriram_nach"),
            ("NACH/SHUHARITECHVENTURES", "Loan Payment", 0.96, "shuhari_nach"),
            ("NACH/1T9 TECHNOLOGY PVT L", "Loan Payment", 0.95, "1t9_nach"),
            ("NACH/WESTERN CAPITAL ADVI", "Loan Payment", 0.96, "western_capital_nach"),
            ("UPI/CREDIT ADJUSTMENT", "Refund", 0.99, "upi_credit_adjustment"),
            ("MONTHLY SAVINGS INTEREST CREDIT", "Interest Income", 0.99, "savings_interest"),
            ("MONTHLY SAVINGS INTEREST CREDI T", "Interest Income", 0.99, "savings_interest_split"),
            ("CHARGE:AMB NON-MAINTENANCE", "Bank Charges", 0.99, "amb_charge"),
            ("CGST ON CHARGE", "Tax Payment", 0.99, "cgst_charge"),
            ("SGST ON CHARGE", "Tax Payment", 0.99, "sgst_charge"),
            ("IMPS-MOB/FUND TRF", "Transfer", 0.95, "imps_mob_transfer"),
            ("IMPS-INET/FUND TRF", "Transfer", 0.95, "imps_inet_transfer"),
            ("NEFT/", "Transfer", 0.94, "neft_transfer"),
            ("PAY TO BHARATPE MERCHANT", "Shopping", 0.9, "bharatpe_merchant"),
            ("PAY BY WHATSAPP", "Transfer", 0.88, "whatsapp_pay"),
            ("PAY TO R K S MOBILE SHOPPEE", "Shopping", 0.92, "mobile_shop"),
            ("PAYMENT FROM PHONEPE", "Transfer", 0.9, "phonepe_payment"),
            ("UPI TRANSACTION FOR PPPL", "Transfer", 0.88, "pppl_upi"),
            ("MANDATE REQUEST", "Transfer", 0.84, "mandate_request"),
        ]
        for token, category, confidence, matched_rule in exact_rules:
            if token in description:
                return RuleClassificationResult(
                    category=category,
                    confidence=confidence,
                    source="rule_engine",
                    matched_rule=matched_rule,
                    matched_keyword=token,
                )

        generic_classified, generic_unclassified = self.generic_rule_engine.classify([txn])
        if generic_classified and not generic_unclassified:
            fallback = generic_classified[0]
            return RuleClassificationResult(
                category=str(fallback.get("category") or ("Others Debit" if is_debit else "Others Credit")),
                confidence=float(fallback.get("confidence") or 0.85),
                source=str(fallback.get("source") or "generic_rule_engine"),
                matched_rule=fallback.get("matched_rule"),
                matched_keyword=fallback.get("matched_keyword"),
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
        bank_words = repo_root / "samples" / "idfc" / "output" / "words.json"
        if bank_words.exists():
            return str(bank_words)
        shared_words = repo_root / "backend" / "words.json"
        if shared_words.exists():
            return str(shared_words)
        return None
