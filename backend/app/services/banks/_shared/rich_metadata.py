"""
Shared rich PDF header / statement-summary extraction for all banks.

Fills identity, period, balances, Dr/Cr counts, totals, and KYC/contact
fields using multi-bank patterns. Bank-specific extractors run first;
this module only fills empty fields (non-destructive).
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional, Sequence


# ---------------------------------------------------------------------------
# Amount / int helpers
# ---------------------------------------------------------------------------

def parse_amount(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Strip currency markers and parentheses (Dr)/(Cr)
    text = re.sub(r"(?i)\b(?:rs\.?|inr|cr|dr)\b", "", text)
    text = text.replace("(", "").replace(")", "").replace("₹", "")
    text = text.replace(",", "").strip()
    # trailing sign: 1,234.56- or 1,234.56+
    sign = 1.0
    if text.endswith("-"):
        sign = -1.0
        text = text[:-1]
    elif text.endswith("+"):
        text = text[:-1]
    if text.startswith("-"):
        sign = -1.0
        text = text[1:]
    try:
        return sign * float(text)
    except (ValueError, TypeError):
        return None


def parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(re.sub(r"[^\d]", "", str(value)))
    except (ValueError, TypeError):
        return None


def _first_match(text: str, patterns: Sequence[str], flags: int = re.IGNORECASE) -> Optional[re.Match]:
    for pattern in patterns:
        m = re.search(pattern, text, flags)
        if m:
            return m
    return None


def _first_group(text: str, patterns: Sequence[str], group: int = 1, flags: int = re.IGNORECASE) -> Optional[str]:
    m = _first_match(text, patterns, flags)
    if not m:
        return None
    try:
        val = m.group(group)
    except IndexError:
        return None
    if val is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(val)).strip(" :.-,\t")
    return cleaned or None


def _set_if_empty(obj: Any, field: str, value: Any) -> None:
    if value is None or value == "":
        return
    current = getattr(obj, field, None)
    if current is None or current == "":
        try:
            setattr(obj, field, value)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Pattern libraries (multi-bank)
# ---------------------------------------------------------------------------

ACCOUNT_PATTERNS = [
    r"(?:Account\s*(?:No|Number|Num)|A/?c\s*No|A/?c\s*Number|Axis\s*Account\s*No)\s*[:\.\s]*([Xx\d\-]{8,22})",
    r"Statement\s+(?:of|for)\s+(?:A/?c|Account)\s*[:\.\s]*([Xx\d\-]{8,22})",
    r"Account\s*Number\s+IFSC\s*Code\s+(\d{8,20})",
    r"Statement\s+for\s+A/c\s+(\d{8,20})",
]

HOLDER_PATTERNS = [
    r"(?:Account\s*Holders?'?\s*Name|Account\s*Holder\s*Name|Customer\s*Name|Account\s*Name|Name\s*of\s*(?:the\s*)?Account\s*Holder)\s*[:\.\s]+([A-Za-z0-9 .,&'/\-]{3,80})",
    r"(?:Account\s*Name)\s+Branch\s*Name\s*\n?\s*([A-Za-z0-9 .,&'/\-]{3,80})",
    r"(?m)^\s*((?:MR|MRS|MS|M/S|SMT|SHRI|SHREE)\.?\s+[A-Z][A-Za-z .]{2,60})\s*$",
]

PERIOD_PATTERNS = [
    r"(?:Statement\s*(?:Period|From)|From|Period\s*From|Searched\s*By\s*From|Account\s*Statement\s*from|For\s*period)\s*[:\.\s]*"
    r"(\d{1,2}[\s/\-][A-Za-z]{3}[\s/\-]\d{2,4}|\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}-\d{2}-\d{2})"
    r"\s*(?:to|To|TO|and|-|–)\s*"
    r"(\d{1,2}[\s/\-][A-Za-z]{3}[\s/\-]\d{2,4}|\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}-\d{2}-\d{2})",
    r"Account\s*statement\s*for\s*:\s*(\d{2}\s+[A-Za-z]{3}\s+\d{4})\s+to\s+(\d{2}\s+[A-Za-z]{3}\s+\d{4})",
    r"STATEMENT\s+PERIOD\s*:\s*(\d{4}-\d{2}-\d{2})\s+TO\s+(\d{4}-\d{2}-\d{2})",
    r"Between\s+(\d{2}-\d{2}-\d{4})\s+and\s+(\d{2}-\d{2}-\d{4})",
    r"(\d{2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\s*[-–]\s*"
    r"(\d{2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})",
]

OPENING_PATTERNS = [
    r"Opening\s*Bal(?:ance)?\s*(?:Rs\.?)?\s*[:\.\s]*([+\-]?[\d,]+\.\d{2})",
    r"OPENING\s*BALANCE\s*(?:Rs\.?)?\s*[:\.\s]*([+\-]?[\d,]+\.\d{2})",
    r"Balance\s*(?:B/?F|Brought\s*Forward|as\s*on)\s*[:\.\s]*([+\-]?[\d,]+\.\d{2})",
    r"BROUGHT\s+FORWARD\s+([+\-]?[\d,]+\.\d{2})",
    r"Opening\s+Balance\s+-\s+-\s+([+\-]?[\d,]+\.\d{2})",
]

CLOSING_PATTERNS = [
    r"Closing\s*Bal(?:ance)?\s*(?:Rs\.?)?\s*[:\.\s]*([+\-]?[\d,]+\.\d{2})",
    r"CLOSING\s*BALANCE\s*(?:Rs\.?)?\s*[:\.\s]*([+\-]?[\d,]+\.\d{2})",
    r"Available\s*Balance\s*(?:Rs\.?)?\s*[:\.\s]*([+\-]?[\d,]+\.\d{2})",
    r"Cleared\s*Balance\s*(?:Rs\.?)?\s*[:\.\s]*([+\-]?[\d,]+\.\d{2})",
]

DR_COUNT_PATTERNS = [
    r"(?:Dr|Debit)\s*Count\s*[:\.\s]*(\d+)",
    r"No\.?\s*of\s*Debit\s*Transactions?\s*[:\.\s]*(\d+)",
    r"(?:Total\s*)?Debit\s*Transactions?\s*[:\.\s]*(\d+)",
    r"Number\s*of\s*Withdrawals?\s*[:\.\s]*(\d+)",
    r"Withdrawals?\s*Count\s*[:\.\s]*(\d+)",
    r"Total\s*No\.?\s*of\s*Debits?\s*[:\.\s]*(\d+)",
]

CR_COUNT_PATTERNS = [
    r"(?:Cr|Credit)\s*Count\s*[:\.\s]*(\d+)",
    r"No\.?\s*of\s*Credit\s*Transactions?\s*[:\.\s]*(\d+)",
    r"(?:Total\s*)?Credit\s*Transactions?\s*[:\.\s]*(\d+)",
    r"Number\s*of\s*Deposits?\s*[:\.\s]*(\d+)",
    r"Deposits?\s*Count\s*[:\.\s]*(\d+)",
    r"Total\s*No\.?\s*of\s*Credits?\s*[:\.\s]*(\d+)",
]

TOTAL_TXN_COUNT_PATTERNS = [
    r"Total\s*(?:No\.?\s*of\s*)?Transactions?\s*[:\.\s]*(\d+)",
    r"No\.?\s*of\s*Transactions?\s*[:\.\s]*(\d+)",
]

TOTAL_DEBIT_PATTERNS = [
    r"Total\s*Debits?\s*(?:Amount)?\s*(?:Rs\.?)?\s*[:\.\s]*([+\-]?[\d,]+\.\d{2})",
    r"Debit\s*Total\s*(?:Rs\.?)?\s*[:\.\s]*([+\-]?[\d,]+\.\d{2})",
    r"Total\s*Withdrawals?\s*(?:Rs\.?)?\s*[:\.\s]*([+\-]?[\d,]+\.\d{2})",
    r"TOTAL\s*WITHDRAWAL\s*(?:Rs\.?)?\s*[:\.\s]*([+\-]?[\d,]+\.\d{2})",
    r"Total\s*Debit\s*Amount\s*(?:Rs\.?)?\s*[:\.\s]*([+\-]?[\d,]+\.\d{2})",
]

TOTAL_CREDIT_PATTERNS = [
    r"Total\s*Credits?\s*(?:Amount)?\s*(?:Rs\.?)?\s*[:\.\s]*([+\-]?[\d,]+\.\d{2})",
    r"Credit\s*Total\s*(?:Rs\.?)?\s*[:\.\s]*([+\-]?[\d,]+\.\d{2})",
    r"Total\s*Deposits?\s*(?:Rs\.?)?\s*[:\.\s]*([+\-]?[\d,]+\.\d{2})",
    r"TOTAL\s*DEPOSIT\s*(?:Rs\.?)?\s*[:\.\s]*([+\-]?[\d,]+\.\d{2})",
    r"Total\s*Credit\s*Amount\s*(?:Rs\.?)?\s*[:\.\s]*([+\-]?[\d,]+\.\d{2})",
]

# Compact summary rows: OPENING TOTAL_DEPOSIT TOTAL_WITHDRAWAL CLOSING
COMPACT_SUMMARY_PATTERNS = [
    r"Rs\.?\s*([+\-]?[\d,]+\.\d{2})\s+Rs\.?\s*([+\-]?[\d,]+\.\d{2})\s+Rs\.?\s*([+\-]?[\d,]+\.\d{2})\s+Rs\.?\s*([+\-]?[\d,]+\.\d{2})\s+"
    r"OPENING\s*BALANCE\s+TOTAL\s*DEPOSIT\s+TOTAL\s*WITHDRAWAL\s+CLOSING\s*BALANCE",
    r"Opening\s*Balance\s+Total\s*Debit\s+Total\s*Credit\s+Closing\s*Balance\s+"
    r"([+\-]?[\d,]+\.\d{2})\s+([+\-]?[\d,]+\.\d{2})\s+([+\-]?[\d,]+\.\d{2})\s+([+\-]?[\d,]+\.\d{2})",
    r"OPENING\s*BALANCE\s+TOTAL\s*DEPOSIT\s+TOTAL\s*WITHDRAWAL\s+CLOSING\s*BALANCE\s+"
    r"(?:Rs\.?\s*)?([+\-]?[\d,]+\.\d{2})\s+(?:Rs\.?\s*)?([+\-]?[\d,]+\.\d{2})\s+(?:Rs\.?\s*)?([+\-]?[\d,]+\.\d{2})\s+(?:Rs\.?\s*)?([+\-]?[\d,]+\.\d{2})",
]

IFSC_PATTERNS = [
    r"(?:IFSC|RTGS/?NEFT\s*IFSC|IFSC\s*Code)\s*[:\.\s]*([A-Z]{4}0[A-Z0-9]{6})",
    r"\b([A-Z]{4}0[A-Z0-9]{6})\b",
]

BRANCH_PATTERNS = [
    r"(?:Account\s*)?Branch(?:\s*Name)?\s*[:\.\s]+([A-Za-z0-9 .,&'/\-]{2,60})",
    r"Branch\s*Code\s*[:\.\s]+([A-Za-z0-9 .\-/]{2,40})",
    r"Home\s*Branch\s*[:\.\s]+([A-Za-z0-9 .,&'/\-]{2,60})",
]

EMAIL_PATTERNS = [
    r"(?:Email|E-?mail(?:\s*ID)?|Registered\s*Email)\s*[:\.\s]*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})",
    r"\b([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b",
]

MOBILE_PATTERNS = [
    r"(?:Mobile|Mob(?:ile)?\s*No|Phone(?:\s*No)?|Contact\s*No|Registered\s*Mobile)\s*[:\.\s]*(\+?91[\-\s]?)?([6-9]\d{9})",
    r"(?:Mobile|Phone)\s*[:\.\s]*([6-9]\d{9})",
]

PAN_PATTERNS = [
    r"\bPAN\s*(?:No|Number)?\s*[:\.\s]*([A-Z]{5}\d{4}[A-Z])\b",
    r"\b([A-Z]{5}\d{4}[A-Z])\b",
]

ACCOUNT_TYPE_PATTERNS = [
    r"Account\s*Type\s*[:\.\s]+([A-Za-z0-9 /\-]{3,40})",
    r"(?:Savings|Current|Salary|NRE|NRO)\s*Account",
]

OPEN_DATE_PATTERNS = [
    r"(?:A/?C\s*Open\s*Date|Account\s*Open(?:ing)?\s*Date|Date\s*of\s*Opening)\s*[:\.\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
]

JOINT_PATTERNS = [
    r"JOINT\s*HOLDERS?\s*[:\.\s]*([A-Za-z0-9 .,&'/\-]{2,80})",
    r"Joint\s*Account\s*Holder\s*[:\.\s]*([A-Za-z0-9 .,&'/\-]{2,80})",
]

CUSTOMER_ID_PATTERNS = [
    r"(?:Customer\s*ID|Cust(?:omer)?\s*ID|CustID|CRN|CIF)\s*[:\.\s]*([A-Za-z0-9]{4,20})",
]

MICR_PATTERNS = [
    r"MICR\s*(?:Code)?\s*[:\.\s]*(\d{9})",
]

ADDRESS_PATTERNS = [
    r"(?:Address|Communication\s*Address|Registered\s*Address)\s*[:\.\s]+(.+?)(?=\n\s*(?:City|State|Pin|Email|Phone|Mobile|IFSC|Account|Customer)|$)",
]


# ---------------------------------------------------------------------------
# Core enricher
# ---------------------------------------------------------------------------

RICH_FIELDS = (
    "account_number",
    "account_holder",
    "statement_from",
    "statement_to",
    "opening_balance",
    "closing_balance",
    "dr_count",
    "cr_count",
    "total_debits",
    "total_credits",
    "branch",
    "ifsc",
    "account_type",
    "email",
    "mobile",
    "address",
    "pan",
    "account_open_date",
    "joint_holders",
    "customer_id",
    "micr",
    "crn",
)


def enrich_statement_metadata(
    metadata: Any,
    full_text: str,
    header_text: str = "",
    *,
    ifsc_prefix: Optional[str] = None,
) -> Any:
    """
    Fill empty metadata fields from PDF text using multi-bank patterns.
    Never overwrites non-empty values already set by bank-specific extractors.
    """
    if metadata is None:
        return metadata

    text = "\n".join(
        part for part in (header_text or "", full_text or "") if part
    )
    if not text.strip():
        return metadata

    # Account number
    if not getattr(metadata, "account_number", None):
        acct = _first_group(text, ACCOUNT_PATTERNS)
        if acct:
            _set_if_empty(metadata, "account_number", acct)

    # Holder
    if not getattr(metadata, "account_holder", None):
        holder = _first_group(text, HOLDER_PATTERNS)
        if holder:
            holder = re.split(
                r"\b(?:Account|Address|City|State|Email|Phone|Branch|IFSC|Customer|Cust)\b",
                holder,
                maxsplit=1,
            )[0].strip(" :,-")
            if len(holder) >= 3 and "BANK" not in holder.upper():
                _set_if_empty(metadata, "account_holder", holder)

    # Period
    if not getattr(metadata, "statement_from", None) or not getattr(metadata, "statement_to", None):
        m = _first_match(text, PERIOD_PATTERNS)
        if m and m.lastindex and m.lastindex >= 2:
            _set_if_empty(metadata, "statement_from", m.group(1).strip())
            _set_if_empty(metadata, "statement_to", m.group(2).strip())

    # Compact 4-value summary block (open, deposit/credit, withdraw/debit, close)
    # OR (open, debit, credit, close) depending on pattern order
    if (
        not getattr(metadata, "opening_balance", None)
        or not getattr(metadata, "closing_balance", None)
        or not getattr(metadata, "total_debits", None)
        or not getattr(metadata, "total_credits", None)
    ):
        for pattern in COMPACT_SUMMARY_PATTERNS:
            m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if not m:
                continue
            a, b, c, d = (parse_amount(m.group(i)) for i in range(1, 5))
            # Pattern 1 (Paytm style): open, deposit, withdraw, close
            if "TOTAL DEPOSIT" in pattern.upper() or "TOTAL\\s*DEPOSIT" in pattern.upper() or "TOTAL DEPOSIT" in m.group(0).upper():
                _set_if_empty(metadata, "opening_balance", a)
                _set_if_empty(metadata, "total_credits", b)
                _set_if_empty(metadata, "total_debits", c)
                _set_if_empty(metadata, "closing_balance", d)
            # Pattern 2 (IDFC style): open, debit, credit, close
            else:
                _set_if_empty(metadata, "opening_balance", a)
                _set_if_empty(metadata, "total_debits", b)
                _set_if_empty(metadata, "total_credits", c)
                _set_if_empty(metadata, "closing_balance", d)
            break

    # Opening / closing
    if not getattr(metadata, "opening_balance", None):
        raw = _first_group(text, OPENING_PATTERNS)
        _set_if_empty(metadata, "opening_balance", parse_amount(raw))

    if not getattr(metadata, "closing_balance", None):
        raw = _first_group(text, CLOSING_PATTERNS)
        _set_if_empty(metadata, "closing_balance", parse_amount(raw))

    # Dr / Cr counts
    if not getattr(metadata, "dr_count", None):
        raw = _first_group(text, DR_COUNT_PATTERNS)
        _set_if_empty(metadata, "dr_count", parse_int(raw))

    if not getattr(metadata, "cr_count", None):
        raw = _first_group(text, CR_COUNT_PATTERNS)
        _set_if_empty(metadata, "cr_count", parse_int(raw))

    # Fallback: total transactions split if only total present
    if getattr(metadata, "dr_count", None) is None and getattr(metadata, "cr_count", None) is None:
        total_raw = _first_group(text, TOTAL_TXN_COUNT_PATTERNS)
        total = parse_int(total_raw)
        if total is not None and total > 0:
            # Keep total on both as best-effort signal only if one side missing later
            # Prefer storing half/half only when totals also absent — skip half split
            # Store total as dr_count only if bank printed single total (BOB style handled bank-side)
            pass

    # Totals
    if not getattr(metadata, "total_debits", None):
        raw = _first_group(text, TOTAL_DEBIT_PATTERNS)
        _set_if_empty(metadata, "total_debits", parse_amount(raw))

    if not getattr(metadata, "total_credits", None):
        raw = _first_group(text, TOTAL_CREDIT_PATTERNS)
        _set_if_empty(metadata, "total_credits", parse_amount(raw))

    # IFSC
    if not getattr(metadata, "ifsc", None):
        ifsc = _first_group(text, IFSC_PATTERNS)
        if ifsc:
            ifsc = ifsc.upper()
            if not ifsc_prefix or ifsc.startswith(ifsc_prefix.upper()):
                _set_if_empty(metadata, "ifsc", ifsc)

    # Branch
    if not getattr(metadata, "branch", None):
        branch = _first_group(text, BRANCH_PATTERNS)
        if branch:
            branch = re.split(
                r"\b(?:Address|City|State|Email|Phone|IFSC|Account|Customer)\b",
                branch,
                maxsplit=1,
            )[0].strip(" :,-")
            if branch and "BANK LIMITED" not in branch.upper():
                _set_if_empty(metadata, "branch", branch)

    # Email
    if not getattr(metadata, "email", None):
        email = _first_group(text, EMAIL_PATTERNS)
        if email and "@" in email:
            _set_if_empty(metadata, "email", email.lower())

    # Mobile
    if not getattr(metadata, "mobile", None):
        m = _first_match(text, MOBILE_PATTERNS)
        if m:
            # last capturing group is the 10-digit number in our patterns
            digits = re.sub(r"\D", "", m.group(m.lastindex or 1))
            if digits.startswith("91") and len(digits) == 12:
                digits = digits[2:]
            if len(digits) == 10 and not digits.startswith("1800"):
                _set_if_empty(metadata, "mobile", digits)

    # PAN
    if not getattr(metadata, "pan", None):
        pan = _first_group(text, PAN_PATTERNS)
        if pan and re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", pan.upper()):
            _set_if_empty(metadata, "pan", pan.upper())

    # Account type
    if not getattr(metadata, "account_type", None):
        at = _first_group(text, ACCOUNT_TYPE_PATTERNS)
        if at:
            # If pattern matched whole "Savings Account" without group content issues
            if re.fullmatch(r"(?:Savings|Current|Salary|NRE|NRO)\s*Account", at, re.IGNORECASE):
                _set_if_empty(metadata, "account_type", at.title())
            else:
                at = re.split(r"\b(?:Account|IFSC|Branch|Customer)\b", at, maxsplit=1)[0].strip(" :,-")
                if at:
                    _set_if_empty(metadata, "account_type", at)

    # Account open date
    if not getattr(metadata, "account_open_date", None):
        _set_if_empty(metadata, "account_open_date", _first_group(text, OPEN_DATE_PATTERNS))

    # Joint holders
    if not getattr(metadata, "joint_holders", None):
        joint = _first_group(text, JOINT_PATTERNS)
        if joint and joint.upper() not in {"NA", "N/A", "NONE", "NIL", "-"}:
            _set_if_empty(metadata, "joint_holders", joint)

    # Customer ID / CRN
    if not getattr(metadata, "customer_id", None):
        cid = _first_group(text, CUSTOMER_ID_PATTERNS)
        if cid:
            _set_if_empty(metadata, "customer_id", cid)
            if hasattr(metadata, "crn") and not getattr(metadata, "crn", None):
                _set_if_empty(metadata, "crn", cid)
    if hasattr(metadata, "crn") and not getattr(metadata, "crn", None):
        crn = _first_group(text, [r"\bCRN\s*[:\.\s]*([A-Za-z0-9xX]{4,20})"])
        _set_if_empty(metadata, "crn", crn)

    # MICR
    if not getattr(metadata, "micr", None):
        _set_if_empty(metadata, "micr", _first_group(text, MICR_PATTERNS))

    # Address
    if not getattr(metadata, "address", None):
        addr = _first_group(text, ADDRESS_PATTERNS, flags=re.IGNORECASE | re.DOTALL)
        if addr:
            lines = []
            for line in re.split(r"[\n\r]+", addr):
                line = re.sub(r"\s+", " ", line).strip(" ,")
                if not line:
                    continue
                if re.match(r"^(?:MR|MRS|MS|M/S|SMT|SHRI)\b", line, re.IGNORECASE):
                    continue
                lines.append(line)
            if lines:
                address = ", ".join(lines)[:300]
                _set_if_empty(metadata, "address", address)

    return metadata


def metadata_to_rich_dict(metadata: Any) -> dict:
    """Serialize any metadata object to the full rich field set."""
    out = {}
    for field in RICH_FIELDS:
        out[field] = getattr(metadata, field, None)
    # expected count convenience
    dr = out.get("dr_count")
    cr = out.get("cr_count")
    if dr is not None and cr is not None:
        try:
            out["expected_transaction_count"] = int(dr) + int(cr)
        except (TypeError, ValueError):
            out["expected_transaction_count"] = None
    else:
        out["expected_transaction_count"] = None
    return out


def ensure_rich_fields(metadata: Any) -> Any:
    """Ensure object has rich attributes (for dataclasses missing fields)."""
    for field in RICH_FIELDS:
        if not hasattr(metadata, field):
            try:
                setattr(metadata, field, None)
            except Exception:
                pass
    return metadata
