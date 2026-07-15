"""
Airco Insights — Karnataka Bank Transaction Validator
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class KarnatakaValidationError(Exception):
    def __init__(self, message: str, error_code: str, details: dict = None):
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


@dataclass
class ValidationIssue:
    transaction_index: int
    field: str
    issue: str
    severity: str
    original_value: Any = None


@dataclass
class KarnatakaValidationResult:
    is_valid: bool
    validated_transactions: List[Dict[str, Any]]
    total_count: int
    valid_count: int
    issues: List[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid, "total_count": self.total_count,
            "valid_count": self.valid_count, "issue_count": len(self.issues),
            "issues": [{"index": i.transaction_index, "field": i.field,
                        "issue": i.issue, "severity": i.severity} for i in self.issues[:10]],
        }


class KarnatakaTransactionValidator:
    DATE_FORMATS = [
        "%d-%b-%Y", "%d-%b-%y", "%d/%m/%Y", "%d/%m/%y",
        "%d-%m-%Y", "%d-%m-%y", "%Y-%m-%d", "%d.%m.%Y",
    ]
    OUTPUT_DATE_FORMAT = "%Y-%m-%d"

    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate(self, transactions: List[Any]) -> Tuple[List[Dict[str, Any]], KarnatakaValidationResult]:
        self.logger.info("Validating %d Karnataka transactions", len(transactions))
        validated, issues = [], []
        for idx, txn in enumerate(transactions):
            txn_dict = txn.to_dict() if hasattr(txn, "to_dict") else dict(txn)
            txn_issues = []
            date_val, di = self._validate_date(txn_dict.get("date"), idx)
            if date_val:
                txn_dict["date"] = date_val
            else:
                txn_issues.append(di)
            desc_val, ddi = self._validate_description(txn_dict.get("description"), idx)
            if desc_val is not None:
                txn_dict["description"] = desc_val
            else:
                txn_issues.append(ddi)
            amt_val, ai = self._validate_amounts(txn_dict.get("debit"), txn_dict.get("credit"), idx)
            if amt_val:
                txn_dict["debit"] = amt_val.get("debit")
                txn_dict["credit"] = amt_val.get("credit")
            else:
                txn_issues.append(ai)
            bal_val, bi = self._validate_balance(txn_dict.get("balance"), idx)
            if bal_val is not None:
                txn_dict["balance"] = bal_val
            else:
                txn_issues.append(bi)
            real = [i for i in txn_issues if i]
            issues.extend(real)
            if not [i for i in real if i.severity == "error"] or not self.strict_mode:
                txn_dict["txn_id"] = self._gen_id(txn_dict)
                validated.append(txn_dict)
        result = KarnatakaValidationResult(
            is_valid=not any(i.severity == "error" for i in issues),
            validated_transactions=validated,
            total_count=len(transactions), valid_count=len(validated), issues=issues,
        )
        return validated, result

    def _validate_date(self, v: Any, idx: int) -> Tuple[Optional[str], Optional[ValidationIssue]]:
        if not v:
            return None, ValidationIssue(idx, "date", "Missing date", "error")
        s = str(v).strip()
        for fmt in self.DATE_FORMATS:
            try:
                dt = datetime.strptime(s, fmt)
                if 1990 <= dt.year <= 2100:
                    return dt.strftime(self.OUTPUT_DATE_FORMAT), None
            except ValueError:
                pass
        return None, ValidationIssue(idx, "date", f"Invalid date: {s}", "error", v)

    def _validate_description(self, v: Any, idx: int) -> Tuple[Optional[str], Optional[ValidationIssue]]:
        if not v:
            return None, ValidationIssue(idx, "description", "Missing description", "error")
        s = re.sub(r"\s+", " ", str(v).strip())
        return (s, None) if len(s) >= 2 else (None, ValidationIssue(idx, "description", "Too short", "warning", v))

    def _validate_amounts(self, debit: Any, credit: Any, idx: int) -> Tuple[Optional[Dict], Optional[ValidationIssue]]:
        def to_f(x):
            if x is None: return None
            try: return float(str(x).replace(",", "").strip())
            except: return None
        dv, cv = to_f(debit), to_f(credit)
        hd = dv is not None and dv > 0
        hc = cv is not None and cv > 0
        if not hd and not hc:
            return None, ValidationIssue(idx, "amount", "No debit or credit", "error")
        return {"debit": dv if hd else None, "credit": cv if hc else None}, None

    def _validate_balance(self, v: Any, idx: int) -> Tuple[Optional[float], Optional[ValidationIssue]]:
        if v is None:
            return None, ValidationIssue(idx, "balance", "Missing balance", "error")
        try: return float(str(v).replace(",", "").strip()), None
        except: return None, ValidationIssue(idx, "balance", f"Invalid balance: {v}", "error", v)

    def _gen_id(self, t: Dict) -> str:
        k = "|".join([t.get("date", ""), str(t.get("description", ""))[:50],
                      str(t.get("debit") or ""), str(t.get("credit") or ""), str(t.get("balance", ""))])
        return hashlib.sha256(k.encode()).hexdigest()[:16]


__all__ = ["KarnatakaValidationError", "ValidationIssue", "KarnatakaValidationResult", "KarnatakaTransactionValidator"]

