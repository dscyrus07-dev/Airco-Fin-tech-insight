"""
Airco Insights — Statement Metadata Extractor
==============================================
Builds the per-statement metadata object that goes on top of the
classified transactions and the bank parser header.

This is a stateless, deterministic extractor. It does NOT classify —
it consumes already-classified transactions produced by the bank-specific
rule engine + words.json classifier and rolls them up into one summary
row per statement.

Channel detection (UPI / NEFT / IMPS / NETBANKING / CASH / OTHER) is
performed here by description regex, and the resolved channel is
written back onto each transaction in-place so downstream Excel /
storage stays consistent.

Produces the metadata schema used by the `statement_metadata` Supabase
table; see `audit_models.StatementMetadata`.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.services.banks._shared.date_normalizer import analyze_statement_dates, normalize_date_value

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Channel detection — single source of truth
# ---------------------------------------------------------------------------

# Order matters: most specific first.
_CHANNEL_PATTERNS: List[Tuple[str, re.Pattern]] = [
    # UPI — handle suffixes + UPI/ prefixes
    ("UPI", re.compile(
        r"(?:\bUPI[/\-:]|/UPI/|@(?:ybl|okaxis|okhdfcbank|oksbi|okicici|paytm|ibl|axl|axisb|hdfcbank|sbi|upi)\b|\bVPA\b|\bBHIM\b)",
        re.IGNORECASE,
    )),
    # RTGS / NEFT / IMPS — wire transfers
    ("NEFT_IMPS", re.compile(
        r"\b(?:NEFT|IMPS|RTGS)\b",
        re.IGNORECASE,
    )),
    # Net Banking (must come AFTER NEFT to avoid stealing "NET")
    ("NETBANKING", re.compile(
        r"\b(?:I[\- ]?NET|INET|IBANKING|NET\s*BANKING|NETBANKING|ONLINE\s*TRANSFER|NETBK|NET\s*TXN)\b",
        re.IGNORECASE,
    )),
    # Cash — deposit + withdrawal
    ("CASH", re.compile(
        r"\b(?:CASH\s*DEP(?:OSIT)?|CDM|BY\s*CASH|BRANCH\s*CASH|ATM\s*WDL|ATM\s*CASH|ATM[\-\s]*\d|CASH\s*W/?D|CASH\s*WITHDRAWAL|ATW[\-\s]?\d)\b",
        re.IGNORECASE,
    )),
    # Cheque
    ("CHEQUE", re.compile(
        r"\b(?:CHQ|CHEQUE|CHQPAID|CTSS|MICRCTS|CLG)\b",
        re.IGNORECASE,
    )),
]

# Cash sub-classification (deposit vs withdrawal). Used to keep ATM out of
# "cash deposits". When direction == credit we treat as deposit; when debit
# we treat as withdrawal. Falls back to keyword check.
_CASH_DEPOSIT_RE = re.compile(
    r"\b(?:CASH\s*DEP(?:OSIT)?|CDM|BY\s*CASH|CASHDEPOSITBY)\b", re.IGNORECASE
)
_CASH_WITHDRAW_RE = re.compile(
    r"\b(?:ATM|ATW|WDL|CASH\s*W/?D|CASH\s*WITHDRAWAL)\b", re.IGNORECASE
)

# Salary keywords (independent of bank-specific category labels)
# NOTE: No leading \b on SALARY — it often appears mid-string in NEFT descriptions
# e.g. "NEFTCR-UTI...SSALARYTHINKLAB..." or "...679SSALARYJAN2023..."
_SALARY_TOKENS_RE = re.compile(
    r"(?:SALARY|PAYROLL|SAL\s*CR(?:EDIT)?|MONTHLY[\s_]SALARY|WAGES|STIPEND|"
    r"BY\s*SAL(?:\b|[A-Z])|NEFT\s*CR[-/]?.*SAL)",
    re.IGNORECASE,
)

# Loan category labels that may appear in the classified transactions.
# Kept generous because each bank rule engine uses slightly different labels.
_LOAN_REPAY_CATEGORIES = {
    "loan payments", "loan payment", "emi", "loan emi",
    "loan repayment", "emi_payment",
}
_LOAN_CREDIT_CATEGORIES = {
    "loan", "loan disbursed", "loan_disbursed", "loan credit", "loan_credit",
}

_OUTWARD_BOUNCE_CATEGORIES = {"outward bounce", "outward_bounce", "chq return", "ach return", "ecs return", "nach return"}
_INWARD_BOUNCE_CATEGORIES = {"inward bounce", "inward_bounce", "chq dep return", "cheque returned"}
_OUTWARD_BOUNCE_RE = re.compile(
    r"(o/w return|outward return|outw return|chq return|cheque return|cheque dishonour|"
    r"dishonoured cheque|ach return|ecs return|nach return|nach ret|ach ret|ecs ret|"
    r"mandate return|si return|standing instruction return|auto debit return|"
    r"auto pay return|insufficient funds|insuff funds|payment returned|debit return|"
    r"o/w chq ret|outward chq ret)",
    re.IGNORECASE,
)
_INWARD_BOUNCE_RE = re.compile(
    r"(i/w return|inward return|inw return|inw ret|inward chq ret|i/w chq ret|"
    r"chq dep return|cheque dep return|cheque deposit return|cheque returned|"
    r"returned cheque|credit return|deposit return|inward bounce|inw bounce|"
    r"clg return|clearing return|inward clg ret|credit reversal)",
    re.IGNORECASE,
)
_BOUNCE_PENALTY_RE = re.compile(
    r"(return chgs|return charge|bounce charge|dishonour charge|chq return chgs|"
    r"cheque return chgs|ecs return chgs|nach return chgs|penal charge|penalty charge)",
    re.IGNORECASE,
)


def detect_channel(description: str) -> str:
    """Return one of UPI / NEFT_IMPS / NETBANKING / CASH / CHEQUE / OTHER."""
    if not description:
        return "OTHER"
    for name, pattern in _CHANNEL_PATTERNS:
        if pattern.search(description):
            return name
    return "OTHER"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class StatementMetadataResult:
    # Header
    userid: Optional[str] = None
    chitid: Optional[str] = None
    filename: Optional[str] = None
    bankname: Optional[str] = None
    accountno: Optional[str] = None
    formatidentify: Optional[str] = None
    startdate: Optional[str] = None
    enddate: Optional[str] = None
    nooftransactions: int = 0

    # Salary
    havesalary: bool = False
    noofsalarycredit: int = 0
    amtofsalarycredit: float = 0.0

    # Loan repayment (debit)
    hasloanrepayment: bool = False
    noofloanrepayments: int = 0
    amtofloanrepayments: float = 0.0

    # Loan credit (disbursement)
    loancredit: bool = False
    noofloancredits: int = 0
    amtofloancredits: float = 0.0

    # Credit metrics
    noofcredits: int = 0
    amtofcredits: float = 0.0
    noofcashdeposits: int = 0
    amtofcashdeposits: float = 0.0
    noofupicredits: int = 0
    amtofupicredits: float = 0.0
    noofneft_imps_credits: int = 0
    amtofneft_imps_credits: float = 0.0
    noofnetbanking_credits: int = 0
    amtofnetbanking_credits: float = 0.0

    # Debit metrics
    noofdebits: int = 0
    amtofdebits: float = 0.0
    noofcashwithdrawals: int = 0
    amtofcashwithdrawals: float = 0.0
    noofupidebits: int = 0
    amtofupidebits: float = 0.0
    noofneft_imps_debits: int = 0
    amtofneft_imps_debits: float = 0.0
    noofnetbanking_debits: int = 0
    amtofnetbanking_debits: float = 0.0

    # Free-form extra (e.g. salary recurrence stats)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class StatementMetadataExtractor:
    """
    Stateless metadata extractor. Construct once per process; call
    `extract(...)` per statement.
    """

    SALARY_MIN_OCCURRENCES = 2          # >=2 similar credits to be 'recurring salary'
    SALARY_AMOUNT_TOLERANCE = 0.60      # +/- 60% — salaries vary (partial month, arrears, advance)

    def __init__(self, logger_: Optional[logging.Logger] = None):
        self.logger = logger_ or logger

    # ---- public API --------------------------------------------------------

    def extract(
        self,
        transactions: List[Dict[str, Any]],
        *,
        header: Optional[Dict[str, Any]] = None,
        write_channel_back: bool = True,
    ) -> StatementMetadataResult:
        """
        Compute statement metadata from already-classified transactions.

        Args:
            transactions: list of transaction dicts with at minimum
                {date, description, debit, credit, category}
            header: optional dict with {userid, chitid, filename, bankname,
                accountno, formatidentify}
            write_channel_back: if True, sets txn['channel'] in-place.

        Returns:
            StatementMetadataResult
        """
        header = header or {}
        result = StatementMetadataResult(
            userid=header.get("userid"),
            chitid=header.get("chitid") or header.get("job_id"),
            filename=header.get("filename"),
            bankname=header.get("bankname"),
            accountno=self._mask_account(header.get("accountno")),
            formatidentify=header.get("formatidentify"),
        )

        date_audit = analyze_statement_dates(
            transactions,
            bank_name=header.get("bankname"),
            header_start=header.get("statement_from") or header.get("startdate"),
            header_end=header.get("statement_to") or header.get("enddate"),
            header_text=header.get("header_text") or header.get("raw_header_text"),
        )

        result.startdate = date_audit.startdate
        result.enddate = date_audit.enddate
        result.extra["date_audit"] = date_audit.to_dict()
        result.extra["detected_date_format"] = date_audit.detected_date_format
        result.extra["date_confidence"] = date_audit.date_confidence
        result.extra["header_date_range"] = {
            "start": date_audit.header_startdate,
            "end": date_audit.header_enddate,
        }
        result.extra["parsed_date_range"] = {
            "start": date_audit.parsed_startdate,
            "end": date_audit.parsed_enddate,
        }
        result.extra["date_validation_status"] = date_audit.status
        result.extra["date_validation_warnings"] = list(date_audit.warnings)

        if not transactions:
            result.nooftransactions = 0
            return result

        # Annotate channel + extract dates
        dates: List[str] = []
        for txn in transactions:
            ch = detect_channel(str(txn.get("description") or txn.get("narration") or ""))
            if write_channel_back:
                txn["channel"] = ch
            d = txn.get("date")
            if d:
                dates.append(str(d))

        result.nooftransactions = len(transactions)
        if dates and not result.startdate and not result.enddate:
            try:
                iso_dates = [self._to_iso_date(d) for d in dates]
                iso_dates = [d for d in iso_dates if d]
                if iso_dates:
                    result.startdate = min(iso_dates)
                    result.enddate = max(iso_dates)
            except Exception:
                result.startdate = dates[0]
                result.enddate = dates[-1]

        # Roll up credit / debit metrics
        self._aggregate_credit_debit(transactions, result)

        # Salary
        salary_txns = self._detect_salary(transactions)
        result.havesalary = len(salary_txns) > 0
        result.noofsalarycredit = len(salary_txns)
        result.amtofsalarycredit = round(sum(self._credit(t) for t in salary_txns), 2)
        if salary_txns:
            result.extra["salary_avg"] = round(mean(self._credit(t) for t in salary_txns), 2)
            result.extra["salary_months"] = sorted({
                str(t.get("date", ""))[:7] for t in salary_txns if t.get("date")
            })

        # Loans
        loan_repay = [t for t in transactions if self._is_loan_repayment(t)]
        loan_cred  = [t for t in transactions if self._is_loan_credit(t)]
        result.hasloanrepayment   = len(loan_repay) > 0
        result.noofloanrepayments = len(loan_repay)
        result.amtofloanrepayments = round(sum(self._debit(t) for t in loan_repay), 2)
        result.loancredit         = len(loan_cred) > 0
        result.noofloancredits    = len(loan_cred)
        result.amtofloancredits   = round(sum(self._credit(t) for t in loan_cred), 2)

        # Bounces
        outward_bounces = [t for t in transactions if self._is_outward_bounce(t)]
        inward_bounces  = [t for t in transactions if self._is_inward_bounce(t)]
        penalty_txns    = [t for t in transactions if self._is_bounce_penalty(t)]
        if outward_bounces or inward_bounces:
            result.extra["outward_bounce_count"] = len(outward_bounces)
            result.extra["inward_bounce_count"]  = len(inward_bounces)
            result.extra["bounce_penalty_count"] = len(penalty_txns)
            result.extra["bounce_penalty_amount"] = round(sum(self._debit(t) for t in penalty_txns), 2)

        return result

    # ---- internal helpers --------------------------------------------------

    @staticmethod
    def _to_iso_date(date_val: str) -> Optional[str]:
        """
        Convert any of these formats to YYYY-MM-DD for safe min/max comparison:
          DD/MM/YYYY  e.g. 09/10/2023
          DD/MM/YY    e.g. 09/10/23
          YYYY-MM-DD  e.g. 2023-10-09  (already ISO — pass through)
        Returns None if unparseable.
        """
        parsed = normalize_date_value(date_val)
        return parsed.iso_date

    @staticmethod
    def _credit(t: Dict[str, Any]) -> float:
        try:
            return float(t.get("credit") or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _debit(t: Dict[str, Any]) -> float:
        try:
            return float(t.get("debit") or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _category(t: Dict[str, Any]) -> str:
        return str(t.get("category") or "").strip().lower()

    @staticmethod
    def _mask_account(acct: Optional[str]) -> Optional[str]:
        if not acct:
            return None
        s = str(acct).strip()
        if len(s) <= 4:
            return s
        return "X" * (len(s) - 4) + s[-4:]

    def _aggregate_credit_debit(
        self,
        transactions: List[Dict[str, Any]],
        r: StatementMetadataResult,
    ) -> None:
        for t in transactions:
            credit = self._credit(t)
            debit = self._debit(t)
            channel = t.get("channel") or detect_channel(
                str(t.get("description") or t.get("narration") or "")
            )
            desc = str(t.get("description") or t.get("narration") or "")

            if credit > 0:
                r.noofcredits += 1
                r.amtofcredits += credit

                if channel == "UPI":
                    r.noofupicredits += 1
                    r.amtofupicredits += credit
                elif channel == "NEFT_IMPS":
                    r.noofneft_imps_credits += 1
                    r.amtofneft_imps_credits += credit
                elif channel == "NETBANKING":
                    r.noofnetbanking_credits += 1
                    r.amtofnetbanking_credits += credit
                elif channel == "CASH" or _CASH_DEPOSIT_RE.search(desc):
                    r.noofcashdeposits += 1
                    r.amtofcashdeposits += credit

            elif debit > 0:
                r.noofdebits += 1
                r.amtofdebits += debit

                if channel == "UPI":
                    r.noofupidebits += 1
                    r.amtofupidebits += debit
                elif channel == "NEFT_IMPS":
                    r.noofneft_imps_debits += 1
                    r.amtofneft_imps_debits += debit
                elif channel == "NETBANKING":
                    r.noofnetbanking_debits += 1
                    r.amtofnetbanking_debits += debit
                elif channel == "CASH" or _CASH_WITHDRAW_RE.search(desc):
                    r.noofcashwithdrawals += 1
                    r.amtofcashwithdrawals += debit

        # round amounts
        for k in (
            "amtofcredits", "amtofdebits",
            "amtofupicredits", "amtofneft_imps_credits", "amtofnetbanking_credits", "amtofcashdeposits",
            "amtofupidebits", "amtofneft_imps_debits", "amtofnetbanking_debits", "amtofcashwithdrawals",
        ):
            setattr(r, k, round(getattr(r, k), 2))

    # ---- salary detection -------------------------------------------------

    def _detect_salary(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Three-rule salary detection:
          1. Category == 'Salary*' OR description matches salary tokens
          2. Recurring (>= SALARY_MIN_OCCURRENCES from similar payer)
          3. Amount stability (within ±15% of mean)
        """
        candidates: List[Dict[str, Any]] = []
        for t in transactions:
            credit = self._credit(t)
            if credit <= 0:
                continue
            cat = self._category(t)
            desc = str(t.get("description") or t.get("narration") or "")
            is_salary_cat = "salary" in cat or "payroll" in cat
            is_salary_kw  = bool(_SALARY_TOKENS_RE.search(desc))
            if is_salary_cat or is_salary_kw:
                candidates.append(t)

        if len(candidates) < self.SALARY_MIN_OCCURRENCES:
            return candidates  # keep weak signal; still surface count

        # Amount-stability filter: keep only those within tolerance of the mean
        amts = [self._credit(t) for t in candidates]
        avg = mean(amts) if amts else 0.0
        if avg <= 0:
            return candidates
        tol = self.SALARY_AMOUNT_TOLERANCE * avg
        stable = [t for t in candidates if abs(self._credit(t) - avg) <= tol]
        # Only enforce stability if it doesn't wipe out the signal
        return stable if len(stable) >= self.SALARY_MIN_OCCURRENCES else candidates

    def _is_loan_repayment(self, t: Dict[str, Any]) -> bool:
        if self._debit(t) <= 0:
            return False
        cat = self._category(t)
        if cat in _LOAN_REPAY_CATEGORIES:
            return True
        if "loan" in cat and "emi" in cat:
            return True
        if "emi" in cat:
            return True
        # Last-resort keyword
        desc = str(t.get("description") or "").upper()
        return any(k in desc for k in ("EMI", "LOAN REPAY", "LOAN PMT", "ACHD-"))

    def _is_loan_credit(self, t: Dict[str, Any]) -> bool:
        if self._credit(t) <= 0:
            return False
        cat = self._category(t)
        if cat in _LOAN_CREDIT_CATEGORIES:
            return True
        if "loan" in cat and "disburs" in cat:
            return True
        return False

    def _is_outward_bounce(self, t: Dict[str, Any]) -> bool:
        """Outward bounce: debit-side failed payment (ACH/ECS/NACH/cheque returned)."""
        cat = self._category(t)
        if cat in _OUTWARD_BOUNCE_CATEGORIES:
            return True
        if cat in _INWARD_BOUNCE_CATEGORIES:
            return False
        desc = str(t.get("description") or t.get("narration") or "")
        if not _OUTWARD_BOUNCE_RE.search(desc):
            return False
        return self._debit(t) > 0 or self._credit(t) == 0

    def _is_inward_bounce(self, t: Dict[str, Any]) -> bool:
        """Inward bounce: credit-side cheque deposit returned."""
        cat = self._category(t)
        if cat in _INWARD_BOUNCE_CATEGORIES:
            return True
        desc = str(t.get("description") or t.get("narration") or "")
        return bool(_INWARD_BOUNCE_RE.search(desc))

    def _is_bounce_penalty(self, t: Dict[str, Any]) -> bool:
        """Return-charge / bounce-fee transaction (debit side)."""
        if self._debit(t) <= 0:
            return False
        desc = str(t.get("description") or t.get("narration") or "")
        return bool(_BOUNCE_PENALTY_RE.search(desc))
