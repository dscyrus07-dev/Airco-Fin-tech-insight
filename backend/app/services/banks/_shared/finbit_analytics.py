from __future__ import annotations

import json
import logging
import math
import re
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import pandas as pd

from .category_registry import normalize_category

logger = logging.getLogger(__name__)

_WORDS_JSON_CACHE: Optional[Dict[str, Any]] = None
_PROFILE_KEYWORD_CACHE: Optional[Dict[str, set[str]]] = None

# Exact UI order requested by the Finbit specification.
FINBIT_ROWS: List[Tuple[str, str, bool]] = [
    ("monthlyAvgBal", "Avg Balance", True),
    ("maxBalance", "Max Balance", True),
    ("minBalance", "Min Balance", True),
    ("cashDeposit", "Cash Deposit", True),
    ("cashWithdrawals", "Cash Withdrawal", True),
    ("chqDeposit", "Cheque Deposit", True),
    ("chqIssues", "Cheque Issues", True),
    ("nonCashCredit", "Non Cash Credit", True),
    ("nonCashDebit", "Non Cash Debit", True),
    ("credits", "Total Credits", True),
    ("debits", "Total Debits", True),
    ("inwBounce", "Inward Bounce", False),
    ("outwBounce", "Outward Bounce", False),
    ("penaltyCharges", "Penalty Charges", True),
    ("ecsNach", "ECS / NACH", True),
    ("totalNetDebit", "Total Net Debit", True),
    ("totalNetCredit", "Total Net Credit", True),
    ("loanRepayment", "Loan Repayment", True),
    ("loanCredit", "Loan Credit", True),
    ("creditCardPayment", "Credit Card Payment", True),
    ("salary", "Salary", True),
    ("nonSalaryCredit", "Non Salary Credit", True),
    ("selfWithdraw", "Self Withdrawal", True),
    ("selfDeposit", "Self Deposit", True),
    ("internalDebitTransactions", "Internal Debit Transactions", True),
    ("internalCreditTransactions", "Internal Credit Transactions", True),
    ("minCredits", "Min Credit Amount", True),
    ("maxCredits", "Max Credit Amount", True),
    ("balanceOpening", "Opening Balance", True),
    ("balanceClosing", "Closing Balance", True),
    ("income", "Income", True),
]

# Canonical category labels are used first; metadata is only a fallback for
# legacy/partially populated transactions.
_CASH_DEPOSIT_LABELS = {"Cash Deposit"}
_CASH_WITHDRAWAL_LABELS = {"Cash Withdrawal", "ATM Withdrawal"}
_CHEQUE_DEPOSIT_LABELS = {"Cheque Deposit"}
_CHEQUE_ISSUE_LABELS = {"Cheque Issues", "Cheques Issued", "Cheque Issued"}
_LOAN_REPAYMENT_LABELS = {"Loan Payment", "Loan Payment / EMI", "EMI Payment", "Loan Repayment"}
_LOAN_CREDIT_LABELS = {"Loan Disbursal", "Loan Disbursed", "Loan Credit"}
_SALARY_LABELS = {"Salary"}
_CREDIT_CARD_LABELS = {"Credit Card Payment", "CC Payment", "CCPAYMENT"}
_BOUNCE_LABELS = {"Inward Bounce", "Outward Bounce", "Bounce", "Cheque Bounce"}
_ECS_LABELS = {"ECS / NACH", "ECS/NACH", "ECS", "NACH", "Auto Debit", "Auto Pay", "Standing Instruction", "Mandate"}
_INTERNAL_LABELS = {
    "Internal Transfer",
    "Transfer To Self",
    "Transfer From Self",
    "Self Transfer",
    "Self Withdrawal",
    "Self Deposit",
    "Own Account Transfer",
    "Own Account",
}
_INCOME_LABELS = {
    "Business Income",
    "Freelance Income",
    "Professional Income",
    "Merchant Settlement",
    "Customer Receipt",
    "Vendor Receipt",
    "Commission",
    "Rental Income",
}

_INTERNAL_MARKER_RE = re.compile(r"\b(self|own account|internal)\b", re.IGNORECASE)
_ECS_MARKER_RE = re.compile(r"\b(ach|nach|ecs|auto debit|auto pay|standing instruction|mandate|si)\b", re.IGNORECASE)
_LOAN_MARKER_RE = re.compile(r"\b(emi|loan|disburse|disbursal|disbursement)\b", re.IGNORECASE)
_SALARY_MARKER_RE = re.compile(r"\b(salary|payroll|sal credit|salary credit|monthly salary|wages)\b", re.IGNORECASE)
_CREDIT_CARD_MARKER_RE = re.compile(
    r"\b(credit\s*card|cc\s*payment|ccpayment|card\s*payment|onecard|"
    r"cred\.in|cred\b|slice\b|jupiter\b|kiwi\b|uni\s*card|"
    r"idfc\s*power\s*card|hdfc\s*card|icici\s*card|axis\s*card|sbi\s*card|"
    r"card\s*bill|card\s*repayment|card\s*due)\b",
    re.IGNORECASE,
)

# Direction-aware bounce patterns — loaded from words.json at runtime via
# _get_bounce_patterns(). Hardcoded fallbacks ensure the module always works.
_OUTWARD_BOUNCE_FALLBACK = [
    "o/w return", "outward return", "outw return", "chq return", "cheque return",
    "cheque dishonour", "dishonoured cheque", "ach return", "ecs return",
    "nach return", "nach ret", "ach ret", "ecs ret", "mandate return",
    "si return", "standing instruction return", "auto debit return",
    "auto pay return", "insufficient funds", "insuff funds",
    "payment returned", "debit return", "o/w chq ret", "outward bounce",
    "rtnchg", "chq rtn", "clg rtn", "bnc chgs", "return unpaid",
    "mandate return unpaid", "si return unpaid", "upi return",
    "debit failed", "payment failed", "transaction failed", "bounce chgs",
    "chq dishonour", "outward chq return", "o/w chq return",
    "nach bounce", "ecs bounce", "ach bounce", "mandate bounce",
    "cheque bounce", "chq bounce",
]
_INWARD_BOUNCE_FALLBACK = [
    "i/w return", "inward return", "inw return", "inw ret", "inward chq ret",
    "i/w chq ret", "chq dep return", "cheque dep return", "cheque deposit return",
    "cheque returned", "returned cheque", "credit return", "deposit return",
    "inward bounce", "inw bounce", "clg return", "clearing return",
    "inward clg ret", "credit reversal",
    "i/w chq return", "inward chq return", "clg rtn", "inw chg ret",
    "cheque dep rtn", "chq dep rtn", "inward chq bounce", "i/w bounce",
    "deposit return chgs", "clearing rtn", "inward return chgs",
]
_BOUNCE_PENALTY_FALLBACK = [
    "return chgs", "return charge", "bounce charge", "dishonour charge",
    "chq return chgs", "cheque return chgs", "ecs return chgs",
    "nach return chgs", "penal charge", "penalty charge",
    "rtnchg", "bnc chgs", "penal chgs", "late chgs",
    "cheque bounce chgs", "ecs bounce chgs", "nach bounce chgs",
    "penalty fee", "dishonor charge", "return unpaid", "bounce chgs",
]

_BOUNCE_INWARD_LABELS = {"Inward Bounce", "INWARD_BOUNCE"}
_BOUNCE_OUTWARD_LABELS = {"Outward Bounce", "OUTWARD_BOUNCE"}
_BOUNCE_LABELS = {"Inward Bounce", "Outward Bounce", "Bounce", "Cheque Bounce",
                  "INWARD_BOUNCE", "OUTWARD_BOUNCE"}


def _get_bounce_patterns() -> Tuple[List[str], List[str], List[str]]:
    """
    Return (outward_patterns, inward_patterns, penalty_patterns) loaded from
    words.json pattern_detection section. Falls back to hardcoded lists.
    """
    words = _load_words_json()
    pd_cfg = words.get("pattern_detection", {})
    out_pats = [p.lower() for p in pd_cfg.get("outward_bounce_patterns", [])] or _OUTWARD_BOUNCE_FALLBACK
    inw_pats = [p.lower() for p in pd_cfg.get("inward_bounce_patterns", [])] or _INWARD_BOUNCE_FALLBACK
    pen_pats = [p.lower() for p in pd_cfg.get("bounce_penalty_patterns", [])] or _BOUNCE_PENALTY_FALLBACK
    return out_pats, inw_pats, pen_pats


@dataclass(frozen=True)
class _TxnView:
    date: Any
    description: str
    debit: float
    credit: float
    balance: float
    category_raw: str
    category_norm: str
    channel: str
    entity: str
    confidence_score: int
    matched_rule: str
    matched_token: str
    is_recurring: bool

    @property
    def amount(self) -> float:
        return self.credit if self.credit > 0 else self.debit

    @property
    def row(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "description": self.description,
            "credit": self.credit,
            "debit": self.debit,
            "balance": self.balance,
            "category": self.category_raw or self.category_norm,
            "normalized_category": self.category_norm,
            "channel": self.channel,
            "entity": self.entity,
            "confidence_score": self.confidence_score,
        }


def _to_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_int_confidence(value: Any) -> int:
    try:
        conf = float(value or 0)
    except (TypeError, ValueError):
        return 0
    if 0 <= conf <= 1:
        conf *= 100
    return int(round(conf))


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _parse_date(value: Any) -> Optional[pd.Timestamp]:
    if value is None or value == "":
        return None
    if isinstance(value, pd.Timestamp):
        return value
    if isinstance(value, datetime):
        return pd.Timestamp(value)
    try:
        return pd.to_datetime(value, errors="coerce", dayfirst=True, format="mixed")
    except Exception:
        return pd.to_datetime(value, errors="coerce", dayfirst=True)


def _month_key(value: pd.Timestamp) -> str:
    return value.to_period("M").strftime("%b-%y")


def _contains_marker(*values: Any, pattern: re.Pattern[str]) -> bool:
    text = " ".join(_as_text(v) for v in values if _as_text(v))
    if not text:
        return False
    return bool(pattern.search(text))


def _category_matches(txn: _TxnView, labels: Iterable[str]) -> bool:
    label_set = set(labels)
    return txn.category_raw in label_set or txn.category_norm in label_set


def _normalize_profile_type(value: Any) -> str:
    text = _as_text(value).lower().replace(" ", "_")
    if text in {"", "unknown", "none", "null"}:
        return "AUTO"
    if text in {"auto", "auto_detect", "auto_detected", "detect", "auto-detect"}:
        return "AUTO"
    if text in {"salaried", "salary"}:
        return "SALARIED"
    if text in {"business"}:
        return "BUSINESS"
    if text in {"mixed"}:
        return "MIXED"
    return text.upper()


def _find_words_json() -> Optional[Path]:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "words.json"
        if candidate.exists():
            return candidate
    return None


def _load_words_json() -> Dict[str, Any]:
    global _WORDS_JSON_CACHE
    if _WORDS_JSON_CACHE is not None:
        return _WORDS_JSON_CACHE

    path = _find_words_json()
    if not path:
        _WORDS_JSON_CACHE = {}
        return _WORDS_JSON_CACHE

    try:
        _WORDS_JSON_CACHE = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _WORDS_JSON_CACHE = {}
    return _WORDS_JSON_CACHE


def _load_profile_keyword_cache() -> Dict[str, set[str]]:
    global _PROFILE_KEYWORD_CACHE
    if _PROFILE_KEYWORD_CACHE is not None:
        return _PROFILE_KEYWORD_CACHE

    data = _load_words_json()
    classification = data.get("classification", {}) if isinstance(data, dict) else {}
    metadata = data.get("metadata", {}) if isinstance(data, dict) else {}

    salary_tokens = {
        str(token).strip().lower()
        for token in classification.get("INCOME_TYPE", {}).get("SALARY", [])
        if str(token).strip()
    }
    business_tokens = {
        str(token).strip().lower()
        for token in metadata.get("business_vendor_patterns", [])
        if str(token).strip()
    }

    for section_name in ("BUSINESS_ENTITIES", "TERMINAL_SETTLEMENTS", "PAYMENT_GATEWAYS", "PAYMENT_PLATFORMS"):
        section = classification.get(section_name, {})
        if isinstance(section, dict):
            for token, value in section.items():
                if token.startswith("_"):
                    continue
                business_tokens.add(str(token).strip().lower())
                if isinstance(value, dict):
                    business_tokens.update(
                        str(child_token).strip().lower()
                        for child_token in value.keys()
                        if str(child_token).strip() and not str(child_token).startswith("_")
                    )

    _PROFILE_KEYWORD_CACHE = {
        "salary": {token for token in salary_tokens if token},
        "business": {token for token in business_tokens if token},
    }
    return _PROFILE_KEYWORD_CACHE


def _keyword_hit(text: str, tokens: Sequence[str]) -> bool:
    if not text or not tokens:
        return False
    lowered = text.lower()
    return any(token in lowered for token in tokens)


def _statement_key(txn: _TxnView) -> str:
    raw = _as_text(txn.entity or txn.matched_token or txn.matched_rule or txn.description)
    raw = re.sub(r"\s+", " ", raw).strip().lower()
    return raw or "unknown"


def _build_account_profile(transactions: Sequence[Mapping[str, Any]] | pd.DataFrame, *, selected_account_type: Optional[str] = None) -> Dict[str, Any]:
    if isinstance(transactions, pd.DataFrame):
        rows = transactions.to_dict("records")
    else:
        rows = list(transactions)

    txns = [_build_txn_view(row) for row in rows]
    txns = [txn for txn in txns if txn is not None]

    selected_type = _normalize_profile_type(selected_account_type)
    if not txns:
        detected = "MIXED" if selected_type == "AUTO" else selected_type or "MIXED"
        return {
            "user_selected_type": selected_type,
            "detected_type": detected,
            "salary_score": 0,
            "business_score": 0,
            "confidence": 0,
            "validation_status": "no_transactions",
            "validation_message": "No transactions were available for profile detection.",
            "salary_months": 0,
            "salary_employer": None,
            "monthly_salary_avg": 0.0,
            "unique_credit_parties": 0,
            "upi_collection_amount": 0.0,
            "salary_detected": False,
            "business_detected": False,
            "mixed_detected": False,
        }

    keyword_cache = _load_profile_keyword_cache()
    salary_tokens = tuple(sorted(keyword_cache.get("salary", set())))
    business_tokens = tuple(sorted(keyword_cache.get("business", set())))

    credit_txns = [txn for txn in txns if txn.credit > 0]
    debit_txns = [txn for txn in txns if txn.debit > 0]
    month_keys = {txn.date.to_period("M").strftime("%b-%y") for txn in txns if txn.date is not None}
    active_days = {txn.date.date() for txn in txns if txn.date is not None}

    credit_parties = [_statement_key(txn) for txn in credit_txns]
    unique_credit_parties = len({party for party in credit_parties if party})
    total_credit_count = len(credit_txns)
    credits_per_day = total_credit_count / max(len(active_days), 1)

    salary_candidates = [
        txn for txn in credit_txns
        if txn.category_norm == "Salary"
        or _keyword_hit(txn.description, salary_tokens)
        or _keyword_hit(_statement_key(txn), salary_tokens)
    ]

    salary_groups: Dict[str, List[_TxnView]] = defaultdict(list)
    for txn in salary_candidates:
        salary_groups[_statement_key(txn)].append(txn)

    recurring_salary_group: List[_TxnView] = []
    for group in salary_groups.values():
        group_months = {txn.date.to_period("M").strftime("%b-%y") for txn in group if txn.date is not None}
        amounts = [txn.credit for txn in group if txn.credit > 0]
        if len(group) >= 2 and len(group_months) >= 2 and amounts:
            avg_amount = sum(amounts) / len(amounts)
            tolerance = avg_amount * 0.10
            if all(abs(amount - avg_amount) <= tolerance for amount in amounts):
                if len(group) > len(recurring_salary_group):
                    recurring_salary_group = group

    salary_score = 0
    if recurring_salary_group:
        salary_score += 40
    if salary_candidates:
        salary_score += 30
    if salary_candidates and len({txn.date.to_period("M").strftime("%b-%y") for txn in salary_candidates if txn.date is not None}) >= 2:
        amounts = [txn.credit for txn in salary_candidates if txn.credit > 0]
        if amounts:
            avg_amount = sum(amounts) / len(amounts)
            tolerance = avg_amount * 0.10
            if all(abs(amount - avg_amount) <= tolerance for amount in amounts):
                salary_score += 15
    if salary_groups:
        top_salary_group = max(salary_groups.items(), key=lambda item: len(item[1]))
        if len(top_salary_group[1]) >= max(2, math.ceil(len(salary_candidates) * 0.6 if salary_candidates else 0)):
            salary_score += 10
        salary_employer = top_salary_group[0]
    else:
        salary_employer = None
    if unique_credit_parties and unique_credit_parties <= 10:
        salary_score += 5
    salary_score = min(int(round(salary_score)), 100)

    business_token_hits = 0
    business_credit_txns = []
    merchant_collection_amount = 0.0
    vendor_marker_re = re.compile(r"\b(gst|supplier|vendor|purchase|wholesale|traders|enterprise|enterprises|solutions|services|company|pvt\.?|ltd\.?|llp|partnership|proprietor|proprietorship)\b", re.IGNORECASE)
    for txn in txns:
        text = f"{txn.description} {txn.entity} {txn.matched_rule} {txn.matched_token} {txn.category_raw} {txn.category_norm}".strip().lower()
        if txn.credit > 0:
            if _keyword_hit(text, business_tokens) or vendor_marker_re.search(text):
                business_token_hits += 1
                business_credit_txns.append(txn)
                merchant_collection_amount += txn.credit
        elif txn.debit > 0 and vendor_marker_re.search(text):
            business_token_hits += 1

    business_score = 0
    if unique_credit_parties >= 50:
        business_score += 30
    elif unique_credit_parties >= 20:
        business_score += 20
    elif unique_credit_parties >= 10:
        business_score += 10

    if credits_per_day >= 10:
        business_score += 25
    elif credits_per_day >= 5:
        business_score += 15
    elif credits_per_day >= 2:
        business_score += 5

    if business_credit_txns:
        business_score += 25

    if business_token_hits and (len(debit_txns) > 0 or merchant_collection_amount > 0):
        business_score += 10

    if total_credit_count >= 100 or len(month_keys) >= 6 and total_credit_count >= 50:
        business_score += 10

    business_score = min(int(round(business_score)), 100)

    if salary_score >= 70 and business_score < 50:
        detected_type = "SALARIED"
    elif business_score >= 70 and salary_score < 50:
        detected_type = "BUSINESS"
    elif salary_score >= 70 and business_score >= 70:
        detected_type = "MIXED"
    else:
        detected_type = "MIXED"

    confidence = int(round(max(salary_score, business_score)))
    if detected_type == "MIXED" and confidence > 0:
        confidence = max(50, min(confidence, 89))

    if selected_type in {"AUTO", ""}:
        validation_status = "auto_detected"
        validation_message = f"Auto-detected profile: {detected_type.title()} ({confidence}%)."
    elif selected_type == detected_type:
        validation_status = "matches_selected_type"
        validation_message = f"Matches selected type: {selected_type.title()} ({confidence}%)."
    else:
        validation_status = "possible_mismatch"
        validation_message = f"Selected {selected_type.title()} but statement behaves more like {detected_type.title()} ({confidence}%)."

    monthly_salary_avg = 0.0
    salary_months = len({txn.date.to_period("M").strftime("%b-%y") for txn in salary_candidates if txn.date is not None})
    salary_source = recurring_salary_group or salary_candidates
    if salary_source:
        salary_monthly_amounts = [txn.credit for txn in salary_source if txn.credit > 0]
        if salary_monthly_amounts:
            monthly_salary_avg = round(sum(salary_monthly_amounts) / len(salary_monthly_amounts), 2)

    upi_collection_amount = round(
        sum(
            txn.credit
            for txn in credit_txns
            if _keyword_hit(f"{txn.description} {txn.entity} {txn.matched_rule} {txn.matched_token}", ("phonepe", "paytm", "bharatpe", "razorpay", "cashfree", "payu", "stripe", "merchant payout", "settlement"))
        ),
        2,
    )

    return {
        "user_selected_type": selected_type,
        "detected_type": detected_type,
        "salary_score": salary_score,
        "business_score": business_score,
        "confidence": confidence,
        "validation_status": validation_status,
        "validation_message": validation_message,
        "salary_months": salary_months,
        "salary_employer": salary_employer,
        "monthly_salary_avg": monthly_salary_avg,
        "unique_credit_parties": unique_credit_parties,
        "upi_collection_amount": upi_collection_amount,
        "salary_detected": detected_type == "SALARIED",
        "business_detected": detected_type == "BUSINESS",
        "mixed_detected": detected_type == "MIXED",
    }


def _is_internal(txn: _TxnView) -> bool:
    if _category_matches(txn, _INTERNAL_LABELS):
        return True
    return _contains_marker(txn.channel, txn.entity, txn.matched_rule, txn.matched_token, txn.description, pattern=_INTERNAL_MARKER_RE)


def _is_ecs_nach(txn: _TxnView) -> bool:
    if _category_matches(txn, _ECS_LABELS):
        return True
    return _contains_marker(txn.channel, txn.entity, txn.matched_rule, txn.matched_token, txn.description, pattern=_ECS_MARKER_RE)


def _desc_matches_any(desc: str, patterns: List[str]) -> bool:
    """Return True if any pattern string appears in normalised description."""
    normed = desc.upper().strip()
    return any(p.upper() in normed for p in patterns)


def _is_inward_bounce(txn: _TxnView) -> bool:
    """Inward bounce: money was supposed to arrive but cheque/credit was returned."""
    if txn.category_norm in _BOUNCE_INWARD_LABELS:
        return True
    _, inw_pats, _ = _get_bounce_patterns()
    if _desc_matches_any(txn.description, inw_pats):
        return True
    return False


def _is_outward_bounce(txn: _TxnView) -> bool:
    """Outward bounce: payment initiated by account holder was returned/failed."""
    if txn.category_norm in _BOUNCE_OUTWARD_LABELS:
        return True
    if txn.category_norm in {"Inward Bounce", "INWARD_BOUNCE"}:
        return False
    out_pats, _, _ = _get_bounce_patterns()
    if _desc_matches_any(txn.description, out_pats):
        if txn.debit > 0:
            return True
        if txn.credit == 0:
            return True
    return False


def _is_bounce(txn: _TxnView) -> bool:
    """Combined: matches either inward or outward bounce."""
    return _is_inward_bounce(txn) or _is_outward_bounce(txn)


def _is_bounce_penalty(txn: _TxnView) -> bool:
    """Matches a bounce penalty/return charge transaction."""
    _, _, pen_pats = _get_bounce_patterns()
    return txn.debit > 0 and _desc_matches_any(txn.description, pen_pats)


def _is_salary(txn: _TxnView) -> bool:
    if _category_matches(txn, _SALARY_LABELS):
        return True
    return _contains_marker(txn.channel, txn.entity, txn.matched_rule, txn.matched_token, txn.description, pattern=_SALARY_MARKER_RE)


def _is_loan_repayment(txn: _TxnView) -> bool:
    if _category_matches(txn, _LOAN_REPAYMENT_LABELS):
        return True
    return txn.debit > 0 and _contains_marker(txn.channel, txn.entity, txn.matched_rule, txn.matched_token, txn.description, pattern=_LOAN_MARKER_RE)


def _is_loan_credit(txn: _TxnView) -> bool:
    if _category_matches(txn, _LOAN_CREDIT_LABELS):
        return True
    if txn.credit <= 0:
        return False
    # Disbursement is almost always a credit event.
    return _contains_marker(txn.channel, txn.entity, txn.matched_rule, txn.matched_token, txn.description, pattern=_LOAN_MARKER_RE)


def _is_cash_deposit(txn: _TxnView) -> bool:
    return _category_matches(txn, _CASH_DEPOSIT_LABELS)


def _is_cheque_deposit(txn: _TxnView) -> bool:
    return _category_matches(txn, _CHEQUE_DEPOSIT_LABELS)


def _is_cash_withdrawal(txn: _TxnView) -> bool:
    return txn.debit > 0 and _category_matches(txn, _CASH_WITHDRAWAL_LABELS)


def _is_cheque_issue(txn: _TxnView) -> bool:
    return txn.debit > 0 and _category_matches(txn, _CHEQUE_ISSUE_LABELS)


def _is_credit_card_payment(txn: _TxnView) -> bool:
    if txn.debit > 0 and _category_matches(txn, _CREDIT_CARD_LABELS):
        return True
    return txn.debit > 0 and _contains_marker(
        txn.channel, txn.entity, txn.matched_rule, txn.matched_token,
        txn.description, pattern=_CREDIT_CARD_MARKER_RE,
    )


def _is_income_credit(txn: _TxnView) -> bool:
    if txn.credit <= 0:
        return False
    if _is_salary(txn):
        return True
    return txn.category_norm in _INCOME_LABELS or txn.category_raw in _INCOME_LABELS


def _build_txn_view(record: Mapping[str, Any]) -> Optional[_TxnView]:
    date_value = record.get("date") or record.get("Date")
    parsed_date = _parse_date(date_value)
    if parsed_date is None or pd.isna(parsed_date):
        return None

    category_raw = _as_text(
        record.get("category")
        or record.get("display_category")
        or record.get("internal_category")
        or record.get("Category")
    )
    debit = _to_float(record.get("debit") or record.get("Debit") or record.get("withdrawal"))
    credit = _to_float(record.get("credit") or record.get("Credit") or record.get("deposit"))
    balance = _to_float(record.get("balance") or record.get("Balance") or record.get("closing_balance"))
    category_norm = normalize_category(category_raw, is_debit=bool(debit > 0 and credit <= 0)) if category_raw else normalize_category("", is_debit=bool(debit > 0 and credit <= 0))
    channel = _as_text(
        record.get("channel")
        or record.get("source")
        or record.get("TransactionMode")
        or record.get("transaction_mode")
        or record.get("mode")
    )
    entity = _as_text(
        record.get("entity")
        or record.get("matched_keyword")
        or record.get("matched_token")
        or record.get("matched_rule")
    )
    confidence_score = _to_int_confidence(record.get("confidence_score") or record.get("confidence"))
    matched_rule = _as_text(record.get("matched_rule"))
    matched_token = _as_text(record.get("matched_token") or record.get("matched_keyword"))
    description = _as_text(record.get("description") or record.get("Description"))
    recurring = record.get("recurring") if "recurring" in record else record.get("is_recurring")
    is_recurring = str(recurring).strip().lower() in {"yes", "true", "1"} or recurring is True

    return _TxnView(
        date=parsed_date,
        description=description,
        debit=debit,
        credit=credit,
        balance=balance,
        category_raw=category_raw,
        category_norm=category_norm,
        channel=channel,
        entity=entity,
        confidence_score=confidence_score,
        matched_rule=matched_rule,
        matched_token=matched_token,
        is_recurring=is_recurring,
    )


def _record_for_group(txn: _TxnView) -> Dict[str, Any]:
    return txn.row


def _aggregate_month(month_df: pd.DataFrame, opening_balance: float) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    txns = [_build_txn_view(rec) for rec in month_df.to_dict("records")]
    txns = [txn for txn in txns if txn is not None]

    if not txns:
        empty_metrics = {key: 0 for key, _, _ in FINBIT_ROWS}
        empty_metrics["balanceOpening"] = opening_balance
        empty_metrics["balanceClosing"] = opening_balance
        empty_metadata = {
            "salaryCreditCount": 0,
            "loanRepaymentCount": 0,
            "loanCreditCount": 0,
            "internalCreditCount": 0,
            "internalDebitCount": 0,
            "ecsNachCount": 0,
            "upiCreditCount": 0,
            "upiDebitCount": 0,
            "cashDepositCount": 0,
            "cashWithdrawalCount": 0,
            "bounceCount": 0,
            "salaryMonthsDetected": False,
            "uniqueSalaryEmployer": [],
            "lowConfidenceCount": 0,
            "highConfidenceCount": 0,
        }
        return empty_metrics, empty_metadata, {
            "salaryCreditsTransactions": [],
            "loanTransactions": [],
            "bounceTransactions": [],
            "internalTransferTransactions": [],
        }, {"salary_detected": False, "loan_detected": False, "bounce_count": 0, "avg_monthly_credit": 0.0, "avg_monthly_debit": 0.0}

    balances = [txn.balance for txn in txns]
    credits = [txn.credit for txn in txns if txn.credit > 0]
    debits = [txn.debit for txn in txns if txn.debit > 0]

    opening = opening_balance if opening_balance is not None else 0.0
    closing = txns[-1].balance

    cash_deposit_txns = [txn for txn in txns if _is_cash_deposit(txn)]
    cheque_deposit_txns = [txn for txn in txns if _is_cheque_deposit(txn)]
    cash_withdrawal_txns = [txn for txn in txns if _is_cash_withdrawal(txn)]
    cheque_issue_txns = [txn for txn in txns if _is_cheque_issue(txn)]
    inward_bounce_txns = [txn for txn in txns if _is_inward_bounce(txn)]
    outward_bounce_txns = [txn for txn in txns if _is_outward_bounce(txn)]
    bounce_txns = inward_bounce_txns + outward_bounce_txns
    bounce_penalty_txns = [txn for txn in txns if _is_bounce_penalty(txn)]
    salary_txns = [txn for txn in txns if _is_salary(txn)]
    loan_repayment_txns = [txn for txn in txns if _is_loan_repayment(txn)]
    loan_credit_txns = [txn for txn in txns if _is_loan_credit(txn)]
    internal_txns = [txn for txn in txns if _is_internal(txn)]
    internal_debit_txns = [txn for txn in internal_txns if txn.debit > 0]
    internal_credit_txns = [txn for txn in internal_txns if txn.credit > 0]
    ecs_txns = [txn for txn in txns if _is_ecs_nach(txn)]
    credit_card_txns = [txn for txn in txns if _is_credit_card_payment(txn)]
    income_txns = [txn for txn in txns if _is_income_credit(txn) and not _is_loan_credit(txn) and not _is_internal(txn) and not _is_cash_deposit(txn)]

    salary_employers = sorted({txn.entity for txn in salary_txns if txn.entity})
    low_confidence_count = sum(1 for txn in txns if txn.confidence_score and txn.confidence_score < 80)
    high_confidence_count = sum(1 for txn in txns if txn.confidence_score >= 80)

    total_credits = sum(credits)
    total_debits = sum(debits)
    cash_deposit = sum(txn.credit for txn in cash_deposit_txns)
    cheque_deposit = sum(txn.credit for txn in cheque_deposit_txns)
    cash_withdrawal = sum(txn.debit for txn in cash_withdrawal_txns)
    cheque_issues = sum(txn.debit for txn in cheque_issue_txns)
    salary = sum(txn.credit for txn in salary_txns)
    loan_repayment = sum(txn.debit for txn in loan_repayment_txns)
    loan_credit = sum(txn.credit for txn in loan_credit_txns)
    internal_debit_amount = sum(txn.debit for txn in internal_debit_txns)
    internal_credit_amount = sum(txn.credit for txn in internal_credit_txns)
    ecs_amount = sum(txn.debit for txn in ecs_txns)
    penalty_amount = sum(txn.debit for txn in txns if txn.category_norm in {"Bank Charges", "Penalty Charges", "Charges"} or _contains_marker(txn.channel, txn.entity, txn.matched_rule, txn.matched_token, txn.description, pattern=re.compile(r"\b(penalty|bounce charge|late fee|minimum balance|non-maintenance|service charge|bank charge)\b", re.IGNORECASE)))
    self_withdraw_amount = sum(txn.debit for txn in txns if txn.debit > 0 and _is_internal(txn))
    self_deposit_amount = sum(txn.credit for txn in txns if txn.credit > 0 and _is_internal(txn))
    non_cash_credit = total_credits - cash_deposit
    non_cash_debit = total_debits - cash_withdrawal
    non_salary_credit = total_credits - salary
    total_net_debit = total_debits - internal_debit_amount
    total_net_credit = total_credits - internal_credit_amount
    min_credit = min(credits) if credits else 0.0
    max_credit = max(credits) if credits else 0.0
    income = sum(txn.credit for txn in income_txns)
    avg_balance = sum(balances) / len(balances) if balances else 0.0
    max_balance = max(balances) if balances else 0.0
    min_balance = min(balances) if balances else 0.0

    monthly_metrics = {
        "monthlyAvgBal": round(avg_balance, 2),
        "maxBalance": round(max_balance, 2),
        "minBalance": round(min_balance, 2),
        "cashDeposit": round(cash_deposit, 2),
        "cashWithdrawals": round(cash_withdrawal, 2),
        "chqDeposit": round(cheque_deposit, 2),
        "chqIssues": round(cheque_issues, 2),
        "nonCashCredit": round(non_cash_credit, 2),
        "nonCashDebit": round(non_cash_debit, 2),
        "credits": round(total_credits, 2),
        "debits": round(total_debits, 2),
        "inwBounce": len(inward_bounce_txns),
        "outwBounce": len(outward_bounce_txns),
        "penaltyCharges": round(penalty_amount, 2),
        "ecsNach": round(ecs_amount, 2),
        "totalNetDebit": round(total_net_debit, 2),
        "totalNetCredit": round(total_net_credit, 2),
        "loanRepayment": round(loan_repayment, 2),
        "loanCredit": round(loan_credit, 2),
        "creditCardPayment": round(sum(txn.debit for txn in credit_card_txns), 2),
        "salary": round(salary, 2),
        "nonSalaryCredit": round(non_salary_credit, 2),
        "selfWithdraw": round(self_withdraw_amount, 2),
        "selfDeposit": round(self_deposit_amount, 2),
        "internalDebitTransactions": round(internal_debit_amount, 2),
        "internalCreditTransactions": round(internal_credit_amount, 2),
        "minCredits": round(min_credit, 2),
        "maxCredits": round(max_credit, 2),
        "balanceOpening": round(opening, 2),
        "balanceClosing": round(closing, 2),
        "income": round(income, 2),
    }

    monthly_metadata = {
        "salaryCreditCount": len(salary_txns),
        "loanRepaymentCount": len(loan_repayment_txns),
        "loanCreditCount": len(loan_credit_txns),
        "internalCreditCount": len(internal_credit_txns),
        "internalDebitCount": len(internal_debit_txns),
        "ecsNachCount": len(ecs_txns),
        "upiCreditCount": sum(1 for txn in txns if txn.credit > 0 and txn.category_norm == "UPI Transfer"),
        "upiDebitCount": sum(1 for txn in txns if txn.debit > 0 and txn.category_norm == "UPI Transfer"),
        "cashDepositCount": len(cash_deposit_txns),
        "cashWithdrawalCount": len(cash_withdrawal_txns),
        "bounceCount": len(bounce_txns),
        "inwardBounceCount": len(inward_bounce_txns),
        "outwardBounceCount": len(outward_bounce_txns),
        "bouncePenaltyCount": len(bounce_penalty_txns),
        "salaryMonthsDetected": bool(salary_txns),
        "uniqueSalaryEmployer": salary_employers,
        "lowConfidenceCount": low_confidence_count,
        "highConfidenceCount": high_confidence_count,
    }

    def _bounce_record(txn: "_TxnView", bounce_type: str) -> Dict[str, Any]:
        r = _record_for_group(txn)
        r["type"] = bounce_type
        r["charge"] = 0.0
        return r

    inward_records = [_bounce_record(t, "INWARD_BOUNCE") for t in inward_bounce_txns]
    outward_records = [_bounce_record(t, "OUTWARD_BOUNCE") for t in outward_bounce_txns]
    bounce_records = inward_records + outward_records

    penalty_debit = sum(t.debit for t in bounce_penalty_txns)
    if bounce_records and penalty_debit > 0:
        share = round(penalty_debit / len(bounce_records), 2)
        for r in bounce_records:
            r["charge"] = share

    grouped = {
        "salaryCreditsTransactions": [_record_for_group(txn) for txn in salary_txns],
        "loanTransactions": [_record_for_group(txn) for txn in loan_repayment_txns + loan_credit_txns],
        "bounceTransactions": bounce_records,
        "inwardBounceTransactions": inward_records,
        "outwardBounceTransactions": outward_records,
        "bouncePenaltyTransactions": [_record_for_group(txn) for txn in bounce_penalty_txns],
        "creditCardTransactions": [_record_for_group(txn) for txn in credit_card_txns],
        "internalTransferTransactions": [_record_for_group(txn) for txn in internal_txns],
    }

    financial_profile = {
        "salary_detected": bool(salary_txns),
        "salary_months": 1 if salary_txns else 0,
        "loan_detected": bool(loan_repayment_txns or loan_credit_txns),
        "bounce_count": len(bounce_txns),
        "inward_bounce_count": len(inward_bounce_txns),
        "outward_bounce_count": len(outward_bounce_txns),
        "avg_monthly_credit": round(total_credits, 2),
        "avg_monthly_debit": round(total_debits, 2),
        "cash_deposit_total": round(cash_deposit, 2),
        "cash_withdrawal_total": round(cash_withdrawal, 2),
        "internal_transfer_total": round(internal_debit_amount + internal_credit_amount, 2),
        "confidence_over_80": high_confidence_count,
        "confidence_under_80": low_confidence_count,
        "unique_salary_employer": salary_employers,
    }

    if salary_txns:
        salary_months = 1
    else:
        salary_months = 0
    financial_profile["salary_months"] = salary_months

    return monthly_metrics, monthly_metadata, grouped, financial_profile


def build_finbit_analytics(
    transactions: Sequence[Mapping[str, Any]] | pd.DataFrame,
    opening_balance: float = 0.0,
    selected_account_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a complete Finbit analytics payload from classified transactions.

    The function intentionally relies on existing transaction metadata first
    (category / channel / entity / confidence) and only falls back to generic
    markers when the metadata is incomplete.
    """

    if isinstance(transactions, pd.DataFrame):
        df = transactions.copy()
    else:
        df = pd.DataFrame(list(transactions))

    if df.empty:
        statement_profile = _build_account_profile(df, selected_account_type=selected_account_type)
        return {
            "month_keys": [],
            "monthly_metrics": OrderedDict(),
            "monthly_metadata": OrderedDict(),
            "transaction_groups": {
                "salaryCreditsTransactions": [],
                "loanTransactions": [],
                "bounceTransactions": [],
                "creditCardTransactions": [],
                "bouncePenaltyTransactions": [],
                "internalTransferTransactions": [],
                "by_month": OrderedDict(),
            },
            "financial_profile": {
                "salary_detected": False,
                "salary_months": 0,
                "loan_detected": False,
                "bounce_count": 0,
                "avg_monthly_credit": 0.0,
                "avg_monthly_debit": 0.0,
                "unique_salary_employer": [],
            },
            "statement_profile": statement_profile,
        }

    if "Date" not in df.columns and "date" in df.columns:
        df = df.rename(columns={"date": "Date"})
    if "Description" not in df.columns and "description" in df.columns:
        df = df.rename(columns={"description": "Description"})
    if "Debit" not in df.columns and "debit" in df.columns:
        df = df.rename(columns={"debit": "Debit"})
    if "Credit" not in df.columns and "credit" in df.columns:
        df = df.rename(columns={"credit": "Credit"})
    if "Balance" not in df.columns and "balance" in df.columns:
        df = df.rename(columns={"balance": "Balance"})
    if "Category" not in df.columns and "category" in df.columns:
        df = df.rename(columns={"category": "Category"})

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True, format="mixed")
    df = df[df["Date"].notna()].copy()
    df.sort_values(["Date", "Description"], kind="stable", inplace=True)
    df.reset_index(drop=True, inplace=True)

    for col in ["Description", "Category", "channel", "entity", "matched_rule", "matched_token", "confidence", "confidence_score", "recurring", "source"]:
        if col not in df.columns:
            df[col] = "" if col not in {"confidence", "confidence_score", "recurring"} else 0

    df["Debit"] = pd.to_numeric(df["Debit"], errors="coerce").fillna(0)
    df["Credit"] = pd.to_numeric(df["Credit"], errors="coerce").fillna(0)
    df["Balance"] = pd.to_numeric(df["Balance"], errors="coerce").fillna(0)
    df["Description"] = df["Description"].fillna("").astype(str)
    df["Category"] = df["Category"].fillna("").astype(str)

    month_periods = df["Date"].dt.to_period("M")
    month_keys = [period.strftime("%b-%y") for period in sorted(month_periods.dropna().unique())]

    monthly_metrics: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    monthly_metadata: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    transaction_groups: Dict[str, Any] = {
        "salaryCreditsTransactions": [],
        "loanTransactions": [],
        "bounceTransactions": [],
        "creditCardTransactions": [],
        "bouncePenaltyTransactions": [],
        "internalTransferTransactions": [],
        "by_month": OrderedDict(),
    }

    if opening_balance:
        running_opening = opening_balance
    else:
        first_txn = _build_txn_view(df.iloc[0].to_dict()) if not df.empty else None
        running_opening = (
            first_txn.balance - first_txn.credit + first_txn.debit
            if first_txn is not None
            else 0.0
        )
    for period in sorted(month_periods.dropna().unique()):
        month_df = df[month_periods == period].copy()
        month_key = period.strftime("%b-%y")
        metrics, metadata, groups, profile = _aggregate_month(month_df, running_opening)
        monthly_metrics[month_key] = metrics
        monthly_metadata[month_key] = metadata
        transaction_groups["by_month"][month_key] = groups
        transaction_groups["salaryCreditsTransactions"].extend(groups["salaryCreditsTransactions"])
        transaction_groups["loanTransactions"].extend(groups["loanTransactions"])
        transaction_groups["bounceTransactions"].extend(groups["bounceTransactions"])
        transaction_groups["creditCardTransactions"].extend(groups.get("creditCardTransactions", []))
        transaction_groups["bouncePenaltyTransactions"].extend(groups.get("bouncePenaltyTransactions", []))
        transaction_groups["internalTransferTransactions"].extend(groups["internalTransferTransactions"])
        running_opening = metrics.get("balanceClosing", running_opening)

        logger.info(
            "Finbit month %s: salary=%s loanRepayment=%s loanCredit=%s internalDr=%s internalCr=%s ecs=%s bounce=%s income=%.2f",
            month_key,
            metadata.get("salaryCreditCount", 0),
            metadata.get("loanRepaymentCount", 0),
            metadata.get("loanCreditCount", 0),
            metadata.get("internalDebitCount", 0),
            metadata.get("internalCreditCount", 0),
            metadata.get("ecsNachCount", 0),
            metadata.get("bounceCount", 0),
            metrics.get("income", 0.0),
        )

    total_salary_months = sum(1 for month_data in monthly_metadata.values() if month_data.get("salaryCreditCount", 0) > 0)
    total_bounces = sum(month_data.get("bounceCount", 0) for month_data in monthly_metadata.values())
    total_credits = [metrics["credits"] for metrics in monthly_metrics.values() if metrics]
    total_debits = [metrics["debits"] for metrics in monthly_metrics.values() if metrics]

    financial_profile = {
        "salary_detected": total_salary_months > 0,
        "salary_months": total_salary_months,
        "loan_detected": any(
            month_data.get("loanRepaymentCount", 0) > 0 or month_data.get("loanCreditCount", 0) > 0
            for month_data in monthly_metadata.values()
        ),
        "bounce_count": total_bounces,
        "avg_monthly_credit": round(sum(total_credits) / len(total_credits), 2) if total_credits else 0.0,
        "avg_monthly_debit": round(sum(total_debits) / len(total_debits), 2) if total_debits else 0.0,
        "unique_salary_employer": sorted(
            {name for month_data in monthly_metadata.values() for name in month_data.get("uniqueSalaryEmployer", [])}
        ),
        "confidence_over_80": sum(month_data.get("highConfidenceCount", 0) for month_data in monthly_metadata.values()),
        "confidence_under_80": sum(month_data.get("lowConfidenceCount", 0) for month_data in monthly_metadata.values()),
    }

    statement_profile = _build_account_profile(df, selected_account_type=selected_account_type)

    return {
        "month_keys": month_keys,
        "monthly_metrics": monthly_metrics,
        "monthly_metadata": monthly_metadata,
        "transaction_groups": transaction_groups,
        "financial_profile": financial_profile,
        "statement_profile": statement_profile,
    }


def compute_finbit_monthly(
    transactions: Sequence[Mapping[str, Any]] | pd.DataFrame,
    opening_balance: float = 0.0,
) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """Backward-compatible Finbit helper used by Excel builders."""

    analytics = build_finbit_analytics(transactions, opening_balance=opening_balance)
    return analytics["month_keys"], analytics["monthly_metrics"]
