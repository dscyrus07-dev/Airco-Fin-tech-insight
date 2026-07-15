"""
Airco Insights — Bank of Baroda Rule Engine
============================================
Full-grade deterministic rule engine mirroring HDFCRuleEngine:
compiled debit/credit exact-keyword rules, regex patterns,
UPI merchant detection, amount-band heuristics.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .._shared.category_registry import normalize_category
from .._shared.generic_bank import GenericBankConfig, GenericRuleEngine

CONFIG = GenericBankConfig(
    bank_key="bank_of_baroda",
    bank_name="Bank of Baroda",
    file_prefix="bank_of_baroda",
    markers=["bank of baroda", "baroda", "bob", "barb0"],
    support_aliases=["bank of baroda", "bankofbaroda", "bob", "baroda"],
)

logger = logging.getLogger(__name__)


@dataclass
class RuleClassificationResult:
    category: str
    confidence: float
    source: str
    matched_rule: Optional[str] = None
    matched_keyword: Optional[str] = None


class BankOfBarodaRuleEngine:
    """Deterministic rule-based classifier for Bank of Baroda transactions."""

    DEBIT_EXACT: List[Tuple[str, str, float]] = [
        ("ATM CASH",            "ATM Withdrawal",  0.99),
        ("ATM/CASH",            "ATM Withdrawal",  0.99),
        ("CASH WITHDRAWAL",     "ATM Withdrawal",  0.99),
        ("CHARGES FOR",         "Bank Charges",    0.99),
        ("ANNUAL MAINTENANCE",  "Bank Charges",    0.99),
        ("GST CHARGES",         "Bank Charges",    0.97),
        ("CHEQUE RETURN",       "Bounce",          0.99),
        ("RETURN CHARGES",      "Bounce",          0.99),
        ("NACH BOUNCE",         "Bounce",          0.99),
        # ── Insurance — must come before EMI (avoids prEMIum false-positive) ──
        ("LIC PREMIUM",         "Insurance",       0.99),
        ("LICPREMIUM",          "Insurance",       0.99),
        ("LIC POLICY",          "Insurance",       0.99),
        ("INSURANCE",           "Insurance",       0.97),
        # ── Loan / EMI — specific phrases before bare EMI token ─────────────
        ("INSTALLMENT",         "Loan Payment",    0.97),
        ("LOAN REPAYMENT",      "Loan Payment",    0.97),
        ("NACH DR",             "Loan Payment",    0.95),
        ("ECS DR",              "Loan Payment",    0.95),
        ("TVSCREDITSERVICESLTD","Loan Payment",    0.99),
        ("IDFC FIRST",          "Loan Payment",    0.99),
        ("BAJAJ FINANCE",       "Loan Payment",    0.99),
        ("BAJAJ FINSERV",       "Loan Payment",    0.99),
        # ── Food ─────────────────────────────────────────────────────────────
        ("SWIGGY",              "Food",            0.99),
        ("ZOMATO",              "Food",            0.99),
        ("DOMINOS",             "Food",            0.99),
        ("MCDONALDS",           "Food",            0.99),
        ("BURGER KING",         "Food",            0.99),
        ("PIZZA HUT",           "Food",            0.99),
        # ── Shopping ─────────────────────────────────────────────────────────
        ("AMAZON",              "Shopping",        0.97),
        ("FLIPKART",            "Shopping",        0.97),
        ("MYNTRA",              "Shopping",        0.97),
        ("MEESHO",              "Shopping",        0.95),
        # ── Entertainment ────────────────────────────────────────────────────
        ("NETFLIX",             "Entertainment",   0.99),
        ("HOTSTAR",             "Entertainment",   0.99),
        ("PRIME VIDEO",         "Entertainment",   0.99),
        ("SPOTIFY",             "Entertainment",   0.99),
        # ── Travel ───────────────────────────────────────────────────────────
        ("IRCTC",               "Travel",          0.99),
        # ── Transport ────────────────────────────────────────────────────────
        ("UBER",                "Transport",       0.99),
        ("OLA",                 "Transport",       0.97),
        ("FASTAG",              "Transport",       0.99),
        # ── Fuel — separate from Transport ───────────────────────────────────
        ("PETROL",              "Fuel",            0.97),
        ("DIESEL",              "Fuel",            0.97),
        ("FUEL",                "Fuel",            0.97),
        ("HPCL",                "Fuel",            0.99),
        ("BPCL",                "Fuel",            0.99),
        ("IOCL",                "Fuel",            0.99),
        ("INDIAN OIL",          "Fuel",            0.99),
        # ── Bill Payment ─────────────────────────────────────────────────────
        ("ELECTRICITY",         "Bill Payment",    0.99),
        ("AIRTEL",              "Bill Payment",    0.97),
        ("JIO",                 "Bill Payment",    0.97),
        ("BROADBAND",           "Bill Payment",    0.97),
        # ── Investment ───────────────────────────────────────────────────────
        ("DIVIDEND",            "Investment",      0.95),
        # ── Transfer ─────────────────────────────────────────────────────────
        ("MONTHLY TRANSFER",    "Transfer",        0.99),
        ("SELF TRANSFER",       "Transfer",        0.99),
    ]

    CREDIT_EXACT: List[Tuple[str, str, float]] = [
        ("SALARY",          "Salary",         0.99),
        ("SAL CR",          "Salary",         0.99),
        ("PAYROLL",         "Salary",         0.99),
        ("BY CASH",         "Cash Deposit",   0.99),
        ("CASH DEPOSIT",    "Cash Deposit",   0.99),
        ("REVERSAL",        "Refund",         0.97),
        ("REFUND",          "Refund",         0.97),
        ("CASHBACK",        "Refund",         0.95),
        ("INT CR",          "Interest",       0.99),
        ("INTEREST CREDIT", "Interest",       0.99),
        ("LOAN",            "Loan Credit",    0.90),
        ("DISBURSAL",       "Loan Credit",    0.97),
        ("DIVIDEND",        "Investment",     0.97),
    ]

    DEBIT_REGEX: List[Tuple[re.Pattern, str, float]] = []
    CREDIT_REGEX: List[Tuple[re.Pattern, str, float]] = []

    UPI_FOOD     = {"swiggy", "zomato", "dominos", "mcdonalds", "pizza"}
    UPI_SHOPPING = {"amazon", "flipkart", "myntra", "meesho", "snapdeal"}
    UPI_TRAVEL   = {"irctc", "makemytrip", "goibibo", "redbus"}
    UPI_FUEL     = {"petrol", "diesel", "fuel", "hpcl", "bpcl", "iocl"}

    def __init__(self, keywords_file: Optional[str] = None):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._compile_patterns()
        self._stats = {"total": 0, "classified": 0, "unclassified": 0}
        self._generic = GenericRuleEngine(CONFIG, keywords_file=keywords_file or self._resolve_keywords_file())

    def _compile_patterns(self) -> None:
        BankOfBarodaRuleEngine.DEBIT_REGEX = [
            (re.compile(r"\bECS\s*DR\b",                  re.I), "Loan Payment",   0.97),
            (re.compile(r"\bNACH\s*DR\b",                 re.I), "Loan Payment",   0.97),
            (re.compile(r"\bEMI\b",                         re.I), "Loan Payment",   0.97),
            (re.compile(r"\bATM\s*WDL\b",                 re.I), "ATM Withdrawal", 0.99),
            (re.compile(r"\bPOS\s+\d{6}",                 re.I), "Shopping",       0.80),
            (re.compile(r"\bCHQPAID\b|\bCHEQUE PAID\b",  re.I), "Cheque",         0.95),
            # Bare numeric transfer (no merchant name)
            (re.compile(r"^IMPS/P2A/\d+/?\d*$",           re.I), "Transfer",       0.90),
            (re.compile(r"^NEFT/[A-Z0-9]+/\d+$",          re.I), "Transfer",       0.88),
            (re.compile(r"^RTGS/[A-Z0-9]+/\d+$",          re.I), "Transfer",       0.88),
        ]
        BankOfBarodaRuleEngine.CREDIT_REGEX = [
            (re.compile(r"\bSAL\s+CR\b",                  re.I), "Salary",         0.99),
        ]

    def classify(
        self, transactions: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        processed, unclassified = [], []
        for txn in transactions:
            result = self._classify_single(txn)
            txn_copy = dict(txn)
            is_debit = bool(txn.get("debit"))
            txn_copy["category"]      = normalize_category(result.category, is_debit=is_debit)
            txn_copy["confidence"]    = result.confidence
            txn_copy["source"]        = result.source
            txn_copy["matched_rule"]  = result.matched_rule
            txn_copy["matched_keyword"] = result.matched_keyword
            processed.append(txn_copy)
            self._stats["total"] += 1
            if txn_copy["category"].startswith("Others"):
                unclassified.append(txn_copy)
                self._stats["unclassified"] += 1
            else:
                self._stats["classified"] += 1
        return processed, unclassified

    def _classify_single(self, txn: Dict[str, Any]) -> RuleClassificationResult:
        desc = str(txn.get("description") or "").upper()
        is_debit = bool(txn.get("debit"))

        exact_rules = self.DEBIT_EXACT if is_debit else self.CREDIT_EXACT
        for token, category, confidence in exact_rules:
            if token in desc:
                return RuleClassificationResult(category, confidence, "exact_rule", token, token)

        regex_rules = self.DEBIT_REGEX if is_debit else self.CREDIT_REGEX
        for pattern, category, confidence in regex_rules:
            m = pattern.search(desc)
            if m:
                return RuleClassificationResult(category, confidence, "regex_rule", pattern.pattern, m.group(0))

        upi_result = self._classify_upi(desc, is_debit)
        if upi_result:
            return upi_result

        # ── words.json entity fallback ─────────────────────────────────────
        generic_c, generic_u = self._generic.classify([txn])
        if generic_c and not generic_u:
            fb = generic_c[0]
            cat = str(fb.get("category") or "")
            if cat and not cat.startswith("Others"):
                return RuleClassificationResult(
                    cat, float(fb.get("confidence") or 0.80),
                    str(fb.get("source") or "entity_lookup"),
                    fb.get("matched_rule"), fb.get("matched_keyword"),
                )

        if is_debit:
            amt = float(txn.get("debit") or 0)
            return self._classify_by_amount(amt) or RuleClassificationResult(
                "Others Debit", 0.5, "default", "amount_fallback"
            )
        return RuleClassificationResult("Others Credit", 0.5, "default", "default")

    def _classify_upi(self, desc: str, is_debit: bool) -> Optional[RuleClassificationResult]:
        if "UPI" not in desc and "@" not in desc:
            return None
        desc_lower = desc.lower()
        if is_debit:
            for m in self.UPI_FOOD:
                if m in desc_lower: return RuleClassificationResult("Food", 0.90, "upi_merchant", f"upi_{m}", m)
            for m in self.UPI_SHOPPING:
                if m in desc_lower: return RuleClassificationResult("Shopping", 0.88, "upi_merchant", f"upi_{m}", m)
            for m in self.UPI_TRAVEL:
                if m in desc_lower: return RuleClassificationResult("Travel", 0.90, "upi_merchant", f"upi_{m}", m)
            for m in self.UPI_FUEL:
                if m in desc_lower: return RuleClassificationResult("Fuel", 0.92, "upi_merchant", f"upi_{m}", m)
        return RuleClassificationResult("Transfer", 0.80, "upi_transfer", "upi_default")

    def _classify_by_amount(self, amount: float) -> Optional[RuleClassificationResult]:
        if amount > 50000:
            return RuleClassificationResult("Transfer", 0.65, "amount_heuristic", "high_value")
        if 5000 <= amount <= 50000:
            return RuleClassificationResult("Transfer", 0.55, "amount_heuristic", "mid_value")
        return None

    def _resolve_keywords_file(self) -> Optional[str]:
        from pathlib import Path
        current = Path(__file__).resolve()
        for parent in current.parents:
            if parent.name == "backend":
                repo_root = parent.parent
                break
        else:
            repo_root = current.parents[-1]
        candidates = [
            repo_root / "samples" / "bank of baroda" / "output" / "words.json",
            repo_root / "samples" / "bank_of_baroda" / "output" / "words.json",
            repo_root / "backend" / "words.json",
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        return None

    def get_statistics(self) -> Dict[str, Any]:
        total = self._stats["total"] or 1
        return {
            "total": self._stats["total"],
            "classified": self._stats["classified"],
            "unclassified": self._stats["unclassified"],
            "classification_rate": round(self._stats["classified"] / total * 100, 1),
        }
