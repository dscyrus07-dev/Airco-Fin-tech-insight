"""
Airco Insights — Axis Bank Transaction Validator
=================================================
Validates all extracted transactions have required fields.
Normalizes date formats (DD-MM-YYYY → YYYY-MM-DD) and cleans descriptions.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


class AxisValidationError(Exception):
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
class AxisValidationResult:
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
        }


class AxisTransactionValidator:
    """Validates and normalizes Axis Bank transactions."""

    # Axis date formats (matches HDFC robustness)
    DATE_FORMATS = [
        "%d/%m/%y",      # DD/MM/YY
        "%d/%m/%Y",      # DD/MM/YYYY
        "%d-%m-%y",      # DD-MM-YY
        "%d-%m-%Y",      # DD-MM/YYYY
        "%d %b %Y",      # DD Mon YYYY
        "%d-%b-%Y",      # DD-Mon-YYYY
        "%d/%b/%Y",      # DD/Mon/YYYY
        "%Y-%m-%d",      # YYYY-MM-DD
    ]

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate(self, transactions) -> AxisValidationResult:
        """Validate and normalize all transactions."""
        if not transactions:
            raise AxisValidationError(
                "No transactions to validate",
                error_code="NO_TRANSACTIONS"
            )

        validated = []
        issues = []

        for i, txn in enumerate(transactions):
            txn_dict = txn.to_dict() if hasattr(txn, "to_dict") else dict(txn)

            # Normalize date
            date_str = txn_dict.get("date", "")
            normalized_date = self._normalize_date(date_str)
            if normalized_date:
                txn_dict["date"] = normalized_date
            else:
                issues.append(ValidationIssue(
                    transaction_index=i,
                    field="date",
                    issue=f"Invalid date format: {date_str}",
                    severity="error",
                    original_value=date_str,
                ))
                if self.strict_mode:
                    continue

            # Validate description
            desc = str(txn_dict.get("description") or "").strip()
            if not desc:
                txn_dict["description"] = f"Transaction {i+1}"
                issues.append(ValidationIssue(
                    transaction_index=i,
                    field="description",
                    issue="Empty description",
                    severity="warning",
                ))

            # Clean amounts
            debit = self._clean_amount(txn_dict.get("debit"))
            credit = self._clean_amount(txn_dict.get("credit"))
            balance = self._clean_amount(txn_dict.get("balance"))

            # Balance can be negative (overdraft accounts)
            # Only validate that balance is a valid number
            txn_dict["debit"] = debit
            txn_dict["credit"] = credit
            txn_dict["balance"] = balance if balance is not None else 0.0

            # Ensure exactly one of debit/credit
            if debit and credit:
                if debit > credit:
                    txn_dict["credit"] = None
                else:
                    txn_dict["debit"] = None

            # Clean ref_no
            txn_dict["ref_no"] = str(txn_dict.get("ref_no") or "").strip()

            validated.append(txn_dict)

        valid_count = len(validated)
        self.logger.info("Validated %d/%d transactions", valid_count, len(transactions))

        return AxisValidationResult(
            is_valid=len(issues) == 0 or not self.strict_mode,
            validated_transactions=validated,
            total_count=len(transactions),
            valid_count=valid_count,
            issues=issues,
        )

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalize date to YYYY-MM-DD."""
        if not date_str:
            return None
        for fmt in self.DATE_FORMATS:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def _clean_amount(self, value) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value) if float(value) > 0 else None
        try:
            cleaned = str(value).replace(",", "").strip()
            result = float(cleaned)
            return result if result > 0 else None
        except (ValueError, TypeError):
            return None
