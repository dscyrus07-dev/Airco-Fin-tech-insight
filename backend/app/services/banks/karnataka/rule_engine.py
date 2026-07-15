from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .._shared.category_registry import normalize_category
from .._shared.generic_bank import GenericBankConfig, GenericClassifier, GenericRuleEngine


CONFIG = GenericBankConfig(
    bank_key="karnataka",
    bank_name="Karnataka Bank",
    file_prefix="karnataka",
    markers=["karnataka bank", "statement for a/c", "karb"],
    support_aliases=["karnataka", "karnataka bank"],
)


@dataclass
class RuleClassificationResult:
    category: str
    confidence: float
    source: str
    matched_rule: Optional[str] = None
    matched_keyword: Optional[str] = None


class KarnatakaRuleEngine:
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
        description = str(
            txn.get("description") or txn.get("Description") or
            txn.get("narration") or txn.get("Narration") or
            txn.get("particulars") or txn.get("Particulars") or ""
        ).upper()
        is_debit = bool(txn.get("debit") or txn.get("Debit"))
        amount = float(txn.get("debit") or txn.get("Debit") or txn.get("credit") or txn.get("Credit") or 0)

        exact_rules = [
            ("DEBITREVERSAL", "Refund", 0.99, "debit_reversal"),
            ("BY CASH-", "Business Income", 0.99, "cash_deposit"),
            ("BY CASH-BNA", "Business Income", 0.99, "cash_deposit_short"),
            ("BY CASH SELF", "Business Income", 0.99, "cash_self"),
            ("PAYOUTS@PAYTM", "Business Income", 0.95, "paytm_payout"),
            ("CF.PAYOUT@ICICI", "Business Income", 0.95, "cashfree_icici_payout"),
            ("CASHFREEPAYOUT@IDFCBANK", "Business Income", 0.95, "cashfree_idfc_payout"),
            ("WALLETMONEYTOBANK@PAYTM", "Transfer", 0.95, "wallet_to_bank"),
            ("NEFT-NEXTBILLION TECHNOLOGY", "Business Income", 0.96, "nextbillion_neft"),
            ("MBS/TO ", "Transfer", 0.94, "mbs_transfer"),
            ("NFS-CWDR/", "ATM Withdrawal", 0.98, "nfs_cash_withdrawal"),
            ("IMPS/P2A-", "Transfer", 0.92, "imps_p2a"),
            ("TRANSFER TO ", "Transfer", 0.95, "imps_transfer"),
            ("CONS. QTRLY SMS CHRGS", "Bank Charges", 0.99, "sms_charge"),
            ("AVG BAL CHRG", "Bank Charges", 0.99, "avg_balance_charge"),
            ("AVG/MIN BAL CHRG", "Bank Charges", 0.99, "min_balance_charge"),
            ("SMS CHRGS", "Bank Charges", 0.99, "sms_charge_short"),
            ("SB INT ", "Interest Income", 0.99, "sb_interest"),
            ("ONECARD@IDFCBANK", "Credit Card Payment", 0.92, "onecard"),
            ("AMAZONPAY@APL", "Shopping", 0.88, "amazonpay"),
            ("TWIDPAY5.PAYU@INDUS", "Cashback", 0.9, "twid_rewards"),
            ("KMBL A/C", "Transfer", 0.9, "kmbl_transfer"),
            ("PAYTM", "Transfer", 0.82, "paytm_counterparty"),
            ("WAHDFCBANK", "Transfer", 0.85, "wa_hdfc"),
            ("NA-KB", "Transfer", 0.8, "upi_na_kb"),
            ("SENT FROM", "Transfer", 0.88, "upi_sent_from"),
            ("PAYMENT FROM", "Transfer", 0.88, "upi_payment_from"),
            ("REQUEST", "Transfer", 0.82, "upi_request"),
        ]
        for token, category, confidence, matched_rule in exact_rules:
            if token in description:
                return RuleClassificationResult(category, confidence, "rule_engine", matched_rule, token)

        if is_debit and amount == 5.90 and "IMPS/" in description:
            return RuleClassificationResult("Bank Charges", 0.99, "rule_engine", "imps_fee", "IMPS_FEE_5_90")

        if not is_debit and re.fullmatch(r"[A-Z][A-Z .]{8,}\d{5,}", description):
            return RuleClassificationResult("Transfer", 0.82, "rule_engine", "bare_name_credit", "BARE_NAME_CREDIT")

        if re.match(r"(IMPS|NEFT|RTGS|UPI)[/:-]", description):
            return RuleClassificationResult("Transfer", 0.80, "rule_engine", "payment_rail", "IMPS/NEFT/UPI")

        # Normalize to lowercase keys for GenericRuleEngine
        norm_txn = {
            "description": str(txn.get("description") or txn.get("Description") or ""),
            "debit": float(txn.get("debit") or txn.get("Debit") or 0),
            "credit": float(txn.get("credit") or txn.get("Credit") or 0),
        }
        generic_classified, generic_unclassified = self.generic_rule_engine.classify([norm_txn])
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
        candidates = [
            repo_root / "samples" / "karnataka bank" / "output" / "words.json",
            repo_root / "samples" / "karnataka" / "output" / "words.json",
            repo_root / "backend" / "words.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None


class KarnatakaClassifier(GenericClassifier):
    def __init__(self, keywords_file: Optional[str] = None):
        kw = keywords_file
        if kw is None:
            kw = KarnatakaRuleEngine._resolve_keywords_file(KarnatakaRuleEngine.__new__(KarnatakaRuleEngine))
        super().__init__(CONFIG, keywords_file=kw)
        self._rule_engine = KarnatakaRuleEngine(keywords_file=kw)

    def classify(self, transactions):
        """Accept either a single row dict (report_generator_base style)
        or a list of transactions (standard style).
        Always returns a result compatible with report_generator_base."""
        if isinstance(transactions, dict):
            # Single-row call from report_generator_base
            result = self._rule_engine._classify_single(transactions)
            is_debit = bool(transactions.get("debit") or transactions.get("Debit"))
            from .._shared.category_registry import normalize_category
            cat = normalize_category(result.category, is_debit=is_debit)
            return {
                "category": cat,
                "display_category": cat,
                "internal_category": cat.upper().replace(" ", "_"),
                "confidence_score": int(result.confidence * 100),
                "confidence": result.confidence,
                "source": result.source,
                "matched_rule": result.matched_rule,
                "matched_keyword": result.matched_keyword,
            }
        # List call — use rule engine for each
        return self._rule_engine.classify(transactions)

