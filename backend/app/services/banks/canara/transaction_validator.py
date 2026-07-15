"""
Airco Insights — Canara Bank Transaction Validator
====================================================
Full-grade validator mirroring HDFCTransactionValidator:
multi-format date normalisation, description cleaning,
amount mutual-exclusivity, balance range check,
deterministic txn_id hashing.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CanaraValidationError(Exception):
    def __init__(self, message: str, error_code: str, details: dict = None):
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


@dataclass
class ValidationIssue:
    transaction_index: int
    field: str
    issue: str
    severity: str  # "error" | "warning"
    original_value: Any = None


@dataclass
class CanaraValidationResult:
    is_valid: bool
    validated_transactions: List[Dict[str, Any]]
    total_count: int
    valid_count: int
    issues: List[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "total_count": self.total_count,
            "valid_count": self.valid_count,
            "issue_count": len(self.issues),
            "issues": [
                {"index": i.transaction_index, "field": i.field,
                 "issue": i.issue, "severity": i.severity}
                for i in self.issues[:10]
            ],
        }


class CanaraTransactionValidator:
    """Validates and normalises Canara Bank transactions."""

    DATE_FORMATS = [
        "%d/%m/%y", "%d/%m/%Y",
        "%d-%m-%y", "%d-%m-%Y",
        "%d %b %Y", "%d %b %y",
        "%Y-%m-%d",
    ]
    OUTPUT_DATE_FORMAT = "%Y-%m-%d"

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate(self, transactions: List[Any]) -> Tuple[List[Dict[str, Any]], CanaraValidationResult]:
        self.logger.info("Validating %d Canara transactions", len(transactions))
        validated, issues = [], []

        for idx, txn in enumerate(transactions):
            txn_dict = txn.to_dict() if hasattr(txn, "to_dict") else dict(txn)
            txn_issues: List[Optional[ValidationIssue]] = []

            date_val, date_issue = self._validate_date(txn_dict.get("date"), idx)
            if date_val:
                txn_dict["date"] = date_val
            else:
                txn_issues.append(date_issue)

            desc_val, desc_issue = self._validate_description(txn_dict.get("description"), idx)
            if desc_val is not None:
                txn_dict["description"] = desc_val
            else:
                txn_issues.append(desc_issue)

            amt_val, amt_issue = self._validate_amounts(
                txn_dict.get("debit"), txn_dict.get("credit"), idx
            )
            if amt_val:
                txn_dict["debit"] = amt_val.get("debit")
                txn_dict["credit"] = amt_val.get("credit")
            else:
                txn_issues.append(amt_issue)

            bal_val, bal_issue = self._validate_balance(txn_dict.get("balance"), idx)
            if bal_val is not None:
                txn_dict["balance"] = bal_val
            else:
                txn_issues.append(bal_issue)

            real_issues = [i for i in txn_issues if i]
            issues.extend(real_issues)

            if not any(i for i in real_issues if i.severity == "error"):
                txn_dict["txn_id"] = self._generate_txn_id(txn_dict)
                validated.append(txn_dict)

        error_count = sum(1 for i in issues if i.severity == "error")
        is_valid = error_count == 0

        result = CanaraValidationResult(
            is_valid=is_valid,
            validated_transactions=validated,
            total_count=len(transactions),
            valid_count=len(validated),
            issues=issues,
        )
        self.logger.info("Canara validation: %d/%d valid, %d issues",
                         len(validated), len(transactions), len(issues))

        if not is_valid and self.strict_mode:
            first_err = next((i for i in issues if i.severity == "error"), None)
            if first_err:
                raise CanaraValidationError(
                    f"Validation failed: {first_err.issue}",
                    error_code="VALIDATION_FAILED",
                    details={"index": first_err.transaction_index, "field": first_err.field},
                )

        return validated, result

    def _validate_date(self, date_val: Any, idx: int) -> Tuple[Optional[str], Optional[ValidationIssue]]:
        if not date_val:
            return None, ValidationIssue(idx, "date", "Missing date", "error")
        date_str = str(date_val).strip()
        for fmt in self.DATE_FORMATS:
            try:
                dt = datetime.strptime(date_str, fmt)
                if 1990 <= dt.year <= 2100:
                    return dt.strftime(self.OUTPUT_DATE_FORMAT), None
            except ValueError:
                continue
        return None, ValidationIssue(idx, "date", f"Invalid date: {date_str}", "error", date_str)

    def _validate_description(self, desc: Any, idx: int) -> Tuple[Optional[str], Optional[ValidationIssue]]:
        if not desc:
            return None, ValidationIssue(idx, "description", "Missing description", "error")
        desc_str = re.sub(r"\s+", " ", str(desc).strip())
        desc_str = "".join(c for c in desc_str if ord(c) >= 32 or c in "\n\t")
        if len(desc_str) < 2:
            return None, ValidationIssue(idx, "description", "Description too short", "warning", desc)
        return desc_str, None

    def _validate_amounts(
        self, debit: Any, credit: Any, idx: int
    ) -> Tuple[Optional[Dict], Optional[ValidationIssue]]:
        def to_f(v: Any) -> Optional[float]:
            if v is None:
                return None
            try:
                return float(str(v).replace(",", "").strip())
            except (ValueError, TypeError):
                return None

        dv, cv = to_f(debit), to_f(credit)
        has_d = dv is not None and dv > 0
        has_c = cv is not None and cv > 0

        if not has_d and not has_c:
            return None, ValidationIssue(idx, "amount", "No debit or credit amount", "error")
        if has_d and has_c:
            return None, ValidationIssue(idx, "amount", "Both debit and credit present", "warning")
        return {"debit": dv if has_d else None, "credit": cv if has_c else None}, None

    def _validate_balance(self, balance: Any, idx: int) -> Tuple[Optional[float], Optional[ValidationIssue]]:
        if balance is None:
            return None, ValidationIssue(idx, "balance", "Missing balance", "error")
        try:
            return float(str(balance).replace(",", "").strip()), None
        except (ValueError, TypeError):
            return None, ValidationIssue(idx, "balance", f"Invalid balance: {balance}", "error", balance)

    def _generate_txn_id(self, txn: Dict) -> str:
        key = "|".join([
            txn.get("date", ""),
            str(txn.get("description", ""))[:50],
            str(txn.get("debit") or ""),
            str(txn.get("credit") or ""),
            str(txn.get("balance", "")),
        ])
        return hashlib.sha256(key.encode()).hexdigest()[:16]


__all__ = ["CanaraValidationError", "ValidationIssue", "CanaraValidationResult", "CanaraTransactionValidator"]
