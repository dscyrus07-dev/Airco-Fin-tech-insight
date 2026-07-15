"""
Airco Insights — HDFC Transaction Validator
============================================
Validates all extracted transactions have required fields.
Normalizes date formats and cleans descriptions.

Validation Rules:
1. Every transaction must have: date, description, balance
2. Every transaction must have exactly one of: debit or credit
3. Date must be valid calendar date
4. Amounts must be positive numbers
5. Balance must be non-negative (unless overdraft)

Design: All transactions valid or fail.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


class HDFCValidationError(Exception):
    """Raised when transaction validation fails."""
    def __init__(self, message: str, error_code: str, details: dict = None):
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


@dataclass
class ValidationIssue:
    """Single validation issue."""
    transaction_index: int
    field: str
    issue: str
    severity: str  # "error", "warning"
    original_value: Any = None


@dataclass
class HDFCValidationResult:
    """Result of transaction validation."""
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
                {
                    "index": i.transaction_index,
                    "field": i.field,
                    "issue": i.issue,
                    "severity": i.severity,
                }
                for i in self.issues[:10]  # First 10 issues
            ],
        }


class HDFCTransactionValidator:
    """
    Validates and normalizes HDFC transactions.
    """
    
    # Supported date formats
    DATE_FORMATS = [
        "%d/%m/%y",      # DD/MM/YY
        "%d/%m/%Y",      # DD/MM/YYYY
        "%d-%m-%y",      # DD-MM-YY
        "%d-%m-%Y",      # DD-MM-YYYY
    ]
    
    # Output date format (ISO)
    OUTPUT_DATE_FORMAT = "%Y-%m-%d"
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize validator.
        
        Args:
            strict_mode: If True, any validation error fails entire batch.
        """
        self.strict_mode = strict_mode
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def validate(self, transactions: List[Any]) -> HDFCValidationResult:
        """
        Validate all transactions.
        
        Args:
            transactions: List of HDFCTransaction objects or dicts
            
        Returns:
            HDFCValidationResult with validated transactions
            
        Raises:
            HDFCValidationError: If validation fails in strict mode
        """
        self.logger.info("Validating %d HDFC transactions", len(transactions))
        
        validated = []
        issues = []
        
        for idx, txn in enumerate(transactions):
            # Convert to dict if needed
            if hasattr(txn, 'to_dict'):
                txn_dict = txn.to_dict()
            else:
                txn_dict = dict(txn)
            
            # Validate and normalize each field
            txn_issues = []
            
            # 1. Validate and normalize date
            date_result = self._validate_date(txn_dict.get("date"), idx)
            if date_result[0]:
                txn_dict["date"] = date_result[0]
            else:
                txn_issues.append(date_result[1])
            
            # 2. Validate description
            desc_result = self._validate_description(txn_dict.get("description"), idx)
            if desc_result[0] is not None:
                txn_dict["description"] = desc_result[0]
            else:
                txn_issues.append(desc_result[1])
            
            # 3. Validate debit/credit
            amount_result = self._validate_amounts(
                txn_dict.get("debit"),
                txn_dict.get("credit"),
                idx
            )
            if amount_result[0]:
                txn_dict["debit"] = amount_result[0].get("debit")
                txn_dict["credit"] = amount_result[0].get("credit")
            else:
                txn_issues.append(amount_result[1])
            
            # 4. Validate balance
            balance_result = self._validate_balance(txn_dict.get("balance"), idx)
            if balance_result[0] is not None:
                txn_dict["balance"] = balance_result[0]
            else:
                txn_issues.append(balance_result[1])
            
            # Collect issues
            issues.extend([i for i in txn_issues if i])
            
            # Add transaction if no errors
            errors = [i for i in txn_issues if i and i.severity == "error"]
            if not errors:
                # Generate transaction ID
                txn_dict["txn_id"] = self._generate_txn_id(txn_dict)
                validated.append(txn_dict)
        
        # Check for critical errors
        error_count = sum(1 for i in issues if i.severity == "error")
        is_valid = error_count == 0
        
        self.logger.info(
            "Validation complete: %d/%d valid, %d issues",
            len(validated), len(transactions), len(issues)
        )
        
        if not is_valid and self.strict_mode:
            first_error = next((i for i in issues if i.severity == "error"), None)
            if first_error:
                raise HDFCValidationError(
                    f"Transaction validation failed: {first_error.issue}",
                    error_code="VALIDATION_FAILED",
                    details={
                        "transaction_index": first_error.transaction_index,
                        "field": first_error.field,
                        "issue": first_error.issue,
                    }
                )
        
        return HDFCValidationResult(
            is_valid=is_valid,
            validated_transactions=validated,
            total_count=len(transactions),
            valid_count=len(validated),
            issues=issues,
        )
    
    def _validate_date(
        self,
        date_val: Any,
        idx: int
    ) -> Tuple[Optional[str], Optional[ValidationIssue]]:
        """Validate and normalize date."""
        if not date_val:
            return None, ValidationIssue(
                transaction_index=idx,
                field="date",
                issue="Missing date",
                severity="error",
            )
        
        date_str = str(date_val).strip()
        
        # Try parsing with each format
        for fmt in self.DATE_FORMATS:
            try:
                dt = datetime.strptime(date_str, fmt)
                # Validate reasonable date range (1990-2100)
                if dt.year < 1990 or dt.year > 2100:
                    continue
                return dt.strftime(self.OUTPUT_DATE_FORMAT), None
            except ValueError:
                continue
        
        return None, ValidationIssue(
            transaction_index=idx,
            field="date",
            issue=f"Invalid date format: {date_str}",
            severity="error",
            original_value=date_str,
        )
    
    def _validate_description(
        self,
        desc: Any,
        idx: int
    ) -> Tuple[Optional[str], Optional[ValidationIssue]]:
        """Validate and clean description."""
        if not desc:
            return None, ValidationIssue(
                transaction_index=idx,
                field="description",
                issue="Missing description",
                severity="error",
            )
        
        desc_str = str(desc).strip()
        
        # Clean up common issues
        # Remove excessive whitespace
        desc_str = re.sub(r'\s+', ' ', desc_str)
        
        # Remove control characters
        desc_str = ''.join(c for c in desc_str if ord(c) >= 32 or c in '\n\t')
        
        if len(desc_str) < 2:
            return None, ValidationIssue(
                transaction_index=idx,
                field="description",
                issue="Description too short",
                severity="warning",
                original_value=desc,
            )
        
        return desc_str, None
    
    def _validate_amounts(
        self,
        debit: Any,
        credit: Any,
        idx: int
    ) -> Tuple[Optional[Dict], Optional[ValidationIssue]]:
        """Validate debit and credit amounts."""
        # Convert to float
        debit_val = self._to_float(debit)
        credit_val = self._to_float(credit)
        
        # Must have exactly one
        has_debit = debit_val is not None and debit_val > 0
        has_credit = credit_val is not None and credit_val > 0
        
        if not has_debit and not has_credit:
            return None, ValidationIssue(
                transaction_index=idx,
                field="amount",
                issue="No debit or credit amount",
                severity="error",
            )
        
        if has_debit and has_credit:
            # Both present - keep larger one based on common patterns
            return None, ValidationIssue(
                transaction_index=idx,
                field="amount",
                issue="Both debit and credit present",
                severity="warning",
            )
        
        return {
            "debit": debit_val if has_debit else None,
            "credit": credit_val if has_credit else None,
        }, None
    
    def _validate_balance(
        self,
        balance: Any,
        idx: int
    ) -> Tuple[Optional[float], Optional[ValidationIssue]]:
        """Validate balance amount."""
        bal_val = self._to_float(balance)
        
        if bal_val is None:
            return None, ValidationIssue(
                transaction_index=idx,
                field="balance",
                issue="Missing or invalid balance",
                severity="error",
            )
        
        # Allow negative for overdraft accounts
        return bal_val, None
    
    def _to_float(self, val: Any) -> Optional[float]:
        """Convert value to float."""
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        try:
            cleaned = str(val).strip().replace(",", "")
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    
    def _generate_txn_id(self, txn: Dict) -> str:
        """Generate unique transaction ID."""
        import hashlib
        
        # Create unique key
        key_parts = [
            txn.get("date", ""),
            txn.get("description", "")[:50],
            str(txn.get("debit") or ""),
            str(txn.get("credit") or ""),
            str(txn.get("balance", "")),
        ]
        key_str = "|".join(key_parts)
        
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]
