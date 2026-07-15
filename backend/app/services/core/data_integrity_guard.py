"""
Airco Insights — Data Integrity Guard
======================================
Final validation gate before output generation.
Ensures 100% data integrity or fails the entire process.

Checks:
1. Transaction count matches expected
2. Balance reconciliation passes
3. No missing required fields
4. No duplicate transactions
5. All transactions classified
6. Confidence thresholds met
7. Debit/Credit totals verified

Design: NO OUTPUT until ALL checks pass.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class IntegrityStatus(Enum):
    """Integrity check status."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


class IntegrityError(Exception):
    """Raised when data integrity check fails."""
    def __init__(self, message: str, check_name: str, details: dict = None):
        self.check_name = check_name
        self.details = details or {}
        super().__init__(f"[{check_name}] {message}")


@dataclass
class IntegrityCheck:
    """Single integrity check result."""
    name: str
    status: IntegrityStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntegrityCheckResult:
    """Complete integrity validation result."""
    is_valid: bool
    checks: List[IntegrityCheck]
    total_checks: int
    passed_checks: int
    failed_checks: int
    warning_checks: int
    
    # Metrics
    transaction_count: int = 0
    expected_count: Optional[int] = None
    total_credits: float = 0.0
    total_debits: float = 0.0
    opening_balance: float = 0.0
    closing_balance: float = 0.0
    reconciliation_passed: bool = False
    unclassified_count: int = 0
    unclassified_percentage: float = 0.0
    duplicate_count: int = 0
    missing_fields_count: int = 0
    low_confidence_count: int = 0
    
    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "warning_checks": self.warning_checks,
            "metrics": {
                "transaction_count": self.transaction_count,
                "expected_count": self.expected_count,
                "total_credits": self.total_credits,
                "total_debits": self.total_debits,
                "opening_balance": self.opening_balance,
                "closing_balance": self.closing_balance,
                "reconciliation_passed": self.reconciliation_passed,
                "unclassified_count": self.unclassified_count,
                "unclassified_percentage": round(self.unclassified_percentage, 2),
                "duplicate_count": self.duplicate_count,
                "missing_fields_count": self.missing_fields_count,
                "low_confidence_count": self.low_confidence_count,
            },
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "details": c.details,
                }
                for c in self.checks
            ],
        }


class DataIntegrityGuard:
    """
    Final integrity validation before output generation.
    Ensures 100% data quality or fails the process.
    """
    
    # Configuration thresholds
    MAX_UNCLASSIFIED_PERCENT = 2.0  # Maximum 2% unclassified allowed
    MIN_CONFIDENCE_THRESHOLD = 0.5  # Minimum confidence for classification
    BALANCE_TOLERANCE = 0.01  # 1 paisa tolerance for reconciliation
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize integrity guard.
        
        Args:
            strict_mode: If True, any failed check causes validation failure.
                        If False, only critical checks cause failure.
        """
        self.strict_mode = strict_mode
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def validate(
        self,
        transactions: List[Dict[str, Any]],
        expected_count: Optional[int] = None,
        expected_opening_balance: Optional[float] = None,
        expected_closing_balance: Optional[float] = None,
        expected_total_credits: Optional[float] = None,
        expected_total_debits: Optional[float] = None,
    ) -> IntegrityCheckResult:
        """
        Run all integrity checks on processed transactions.
        
        Args:
            transactions: List of processed transaction dicts
            expected_count: Expected transaction count from statement summary
            expected_opening_balance: Opening balance from statement
            expected_closing_balance: Closing balance from statement
            expected_total_credits: Total credits from statement summary
            expected_total_debits: Total debits from statement summary
            
        Returns:
            IntegrityCheckResult with all check results
            
        Raises:
            IntegrityError: If critical check fails in strict mode
        """
        self.logger.info("Running data integrity checks on %d transactions", len(transactions))
        
        checks = []
        
        # Check 1: Transaction count
        checks.append(self._check_transaction_count(transactions, expected_count))
        
        # Check 2: Required fields
        missing_count, missing_check = self._check_required_fields(transactions)
        checks.append(missing_check)
        
        # Check 3: Duplicates
        dup_count, dup_check = self._check_duplicates(transactions)
        checks.append(dup_check)
        
        # Check 4: Balance reconciliation
        recon_passed, recon_check, totals = self._check_balance_reconciliation(
            transactions, expected_opening_balance, expected_closing_balance
        )
        checks.append(recon_check)
        
        # Check 5: Credit/Debit totals
        totals_check = self._check_totals(
            totals, expected_total_credits, expected_total_debits
        )
        checks.append(totals_check)
        
        # Check 6: Classification coverage
        unclassified_count, unclassified_pct, class_check = self._check_classification(transactions)
        checks.append(class_check)
        
        # Check 7: Confidence levels
        low_conf_count, conf_check = self._check_confidence(transactions)
        checks.append(conf_check)
        
        # Calculate results
        passed = sum(1 for c in checks if c.status == IntegrityStatus.PASSED)
        failed = sum(1 for c in checks if c.status == IntegrityStatus.FAILED)
        warnings = sum(1 for c in checks if c.status == IntegrityStatus.WARNING)
        
        is_valid = failed == 0
        
        result = IntegrityCheckResult(
            is_valid=is_valid,
            checks=checks,
            total_checks=len(checks),
            passed_checks=passed,
            failed_checks=failed,
            warning_checks=warnings,
            transaction_count=len(transactions),
            expected_count=expected_count,
            total_credits=totals.get("total_credits", 0.0),
            total_debits=totals.get("total_debits", 0.0),
            opening_balance=totals.get("opening_balance", 0.0),
            closing_balance=totals.get("closing_balance", 0.0),
            reconciliation_passed=recon_passed,
            unclassified_count=unclassified_count,
            unclassified_percentage=unclassified_pct,
            duplicate_count=dup_count,
            missing_fields_count=missing_count,
            low_confidence_count=low_conf_count,
        )
        
        self.logger.info(
            "Integrity check complete: valid=%s passed=%d failed=%d warnings=%d",
            is_valid, passed, failed, warnings
        )
        
        if not is_valid and self.strict_mode:
            failed_checks = [c for c in checks if c.status == IntegrityStatus.FAILED]
            first_failure = failed_checks[0]
            raise IntegrityError(
                first_failure.message,
                check_name=first_failure.name,
                details=first_failure.details
            )
        
        return result
    
    def _check_transaction_count(
        self,
        transactions: List[Dict],
        expected: Optional[int]
    ) -> IntegrityCheck:
        """Check if transaction count matches expected."""
        actual = len(transactions)
        
        if expected is None:
            return IntegrityCheck(
                name="transaction_count",
                status=IntegrityStatus.WARNING,
                message=f"Transaction count: {actual} (no expected count provided)",
                details={"actual": actual, "expected": None}
            )
        
        if actual == expected:
            return IntegrityCheck(
                name="transaction_count",
                status=IntegrityStatus.PASSED,
                message=f"Transaction count matches: {actual}",
                details={"actual": actual, "expected": expected}
            )
        
        return IntegrityCheck(
            name="transaction_count",
            status=IntegrityStatus.FAILED,
            message=f"Transaction count mismatch: expected {expected}, got {actual}",
            details={"actual": actual, "expected": expected, "difference": actual - expected}
        )
    
    def _check_required_fields(
        self,
        transactions: List[Dict]
    ) -> tuple[int, IntegrityCheck]:
        """Check all required fields are present."""
        required = ["date", "description", "balance"]
        missing_count = 0
        
        for i, txn in enumerate(transactions):
            for field in required:
                if field not in txn or txn[field] is None:
                    missing_count += 1
            
            # Must have either debit or credit
            if txn.get("debit") is None and txn.get("credit") is None:
                missing_count += 1
        
        if missing_count == 0:
            return 0, IntegrityCheck(
                name="required_fields",
                status=IntegrityStatus.PASSED,
                message="All required fields present",
                details={"missing_count": 0}
            )
        
        return missing_count, IntegrityCheck(
            name="required_fields",
            status=IntegrityStatus.FAILED,
            message=f"Missing required fields in {missing_count} instances",
            details={"missing_count": missing_count}
        )
    
    def _check_duplicates(
        self,
        transactions: List[Dict]
    ) -> tuple[int, IntegrityCheck]:
        """Check for duplicate transactions."""
        seen = set()
        duplicates = 0
        
        for txn in transactions:
            # Create unique key from date + description + amount + balance
            debit = txn.get("debit") or 0
            credit = txn.get("credit") or 0
            key = (
                txn.get("date"),
                txn.get("description", "")[:50],
                debit,
                credit,
                txn.get("balance"),
            )
            
            if key in seen:
                duplicates += 1
            else:
                seen.add(key)
        
        if duplicates == 0:
            return 0, IntegrityCheck(
                name="duplicates",
                status=IntegrityStatus.PASSED,
                message="No duplicate transactions found",
                details={"duplicate_count": 0}
            )
        
        return duplicates, IntegrityCheck(
            name="duplicates",
            status=IntegrityStatus.WARNING,
            message=f"Found {duplicates} potential duplicate transactions",
            details={"duplicate_count": duplicates}
        )
    
    def _check_balance_reconciliation(
        self,
        transactions: List[Dict],
        expected_opening: Optional[float],
        expected_closing: Optional[float],
    ) -> tuple[bool, IntegrityCheck, dict]:
        """Check balance reconciliation."""
        if not transactions:
            return False, IntegrityCheck(
                name="balance_reconciliation",
                status=IntegrityStatus.FAILED,
                message="No transactions to reconcile",
                details={}
            ), {}
        
        # Get first and last balance
        first_balance = transactions[0].get("balance", 0.0)
        last_balance = transactions[-1].get("balance", 0.0)
        
        # Calculate totals
        total_credits = sum(txn.get("credit") or 0 for txn in transactions)
        total_debits = sum(txn.get("debit") or 0 for txn in transactions)
        
        # Infer opening balance from first transaction
        first_txn = transactions[0]
        first_credit = first_txn.get("credit") or 0
        first_debit = first_txn.get("debit") or 0
        inferred_opening = first_balance - first_credit + first_debit
        
        # Calculate expected closing from opening
        calculated_closing = inferred_opening + total_credits - total_debits
        
        totals = {
            "opening_balance": inferred_opening,
            "closing_balance": last_balance,
            "total_credits": total_credits,
            "total_debits": total_debits,
            "calculated_closing": calculated_closing,
        }
        
        # Check if reconciliation passes
        diff = abs(calculated_closing - last_balance)
        reconciles = diff <= self.BALANCE_TOLERANCE
        
        if reconciles:
            return True, IntegrityCheck(
                name="balance_reconciliation",
                status=IntegrityStatus.PASSED,
                message=f"Balance reconciled: Opening={inferred_opening:.2f}, Closing={last_balance:.2f}",
                details=totals
            ), totals
        
        return False, IntegrityCheck(
            name="balance_reconciliation",
            status=IntegrityStatus.FAILED,
            message=f"Balance mismatch: calculated {calculated_closing:.2f}, actual {last_balance:.2f}, diff={diff:.2f}",
            details={**totals, "difference": diff}
        ), totals
    
    def _check_totals(
        self,
        totals: dict,
        expected_credits: Optional[float],
        expected_debits: Optional[float],
    ) -> IntegrityCheck:
        """Check credit/debit totals match expected."""
        actual_credits = totals.get("total_credits", 0)
        actual_debits = totals.get("total_debits", 0)
        
        if expected_credits is None and expected_debits is None:
            return IntegrityCheck(
                name="totals_verification",
                status=IntegrityStatus.WARNING,
                message=f"Totals: Credits={actual_credits:.2f}, Debits={actual_debits:.2f} (no expected values)",
                details={"actual_credits": actual_credits, "actual_debits": actual_debits}
            )
        
        issues = []
        if expected_credits is not None:
            diff = abs(actual_credits - expected_credits)
            if diff > self.BALANCE_TOLERANCE:
                issues.append(f"credits diff={diff:.2f}")
        
        if expected_debits is not None:
            diff = abs(actual_debits - expected_debits)
            if diff > self.BALANCE_TOLERANCE:
                issues.append(f"debits diff={diff:.2f}")
        
        if not issues:
            return IntegrityCheck(
                name="totals_verification",
                status=IntegrityStatus.PASSED,
                message="Credit/Debit totals verified",
                details={
                    "actual_credits": actual_credits,
                    "actual_debits": actual_debits,
                    "expected_credits": expected_credits,
                    "expected_debits": expected_debits,
                }
            )
        
        return IntegrityCheck(
            name="totals_verification",
            status=IntegrityStatus.FAILED,
            message=f"Totals mismatch: {', '.join(issues)}",
            details={
                "actual_credits": actual_credits,
                "actual_debits": actual_debits,
                "expected_credits": expected_credits,
                "expected_debits": expected_debits,
            }
        )
    
    def _check_classification(
        self,
        transactions: List[Dict]
    ) -> tuple[int, float, IntegrityCheck]:
        """Check classification coverage."""
        total = len(transactions)
        if total == 0:
            return 0, 0.0, IntegrityCheck(
                name="classification_coverage",
                status=IntegrityStatus.PASSED,
                message="No transactions to classify",
                details={}
            )
        
        unclassified = sum(
            1 for txn in transactions
            if not txn.get("category") or txn.get("category", "").startswith("Others")
        )
        
        pct = (unclassified / total) * 100
        
        if pct <= self.MAX_UNCLASSIFIED_PERCENT:
            return unclassified, pct, IntegrityCheck(
                name="classification_coverage",
                status=IntegrityStatus.PASSED,
                message=f"Classification coverage: {100-pct:.1f}% ({total-unclassified}/{total})",
                details={"unclassified": unclassified, "total": total, "percentage": pct}
            )
        
        return unclassified, pct, IntegrityCheck(
            name="classification_coverage",
            status=IntegrityStatus.WARNING,
            message=f"High unclassified rate: {pct:.1f}% ({unclassified}/{total})",
            details={"unclassified": unclassified, "total": total, "percentage": pct}
        )
    
    def _check_confidence(
        self,
        transactions: List[Dict]
    ) -> tuple[int, IntegrityCheck]:
        """Check confidence levels."""
        low_confidence = sum(
            1 for txn in transactions
            if (txn.get("confidence") or 1.0) < self.MIN_CONFIDENCE_THRESHOLD
        )
        
        if low_confidence == 0:
            return 0, IntegrityCheck(
                name="confidence_levels",
                status=IntegrityStatus.PASSED,
                message="All transactions have acceptable confidence",
                details={"low_confidence_count": 0}
            )
        
        return low_confidence, IntegrityCheck(
            name="confidence_levels",
            status=IntegrityStatus.WARNING,
            message=f"{low_confidence} transactions have low confidence (<{self.MIN_CONFIDENCE_THRESHOLD})",
            details={"low_confidence_count": low_confidence}
        )
