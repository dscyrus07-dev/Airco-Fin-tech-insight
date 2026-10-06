"""Verification v1 data models (observe-only).

Pure stdlib. Nothing here imports the rest of the app, so it can be unit-tested
without the FastAPI / pdfplumber stack.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Literal, Optional, Tuple

CheckStatus = Literal["pass", "fail", "skip"]
VerificationState = Literal["VERIFIED", "REVIEW", "FAILED"]

# Check names (stable identifiers used in reports and CSVs).
BALANCE_CHECK = "balance_check"
OPENING_CLOSING_CHECK = "opening_closing_check"
PRINTED_TOTALS_CHECK = "printed_totals_check"
DUPLICATE_CHECK = "duplicate_check"
SCHEMA_CHECK = "schema_check"
HEADER_PERIOD_CHECK = "header_period_check"

# Checks whose failure means the extracted numbers cannot be trusted.
HARD_CHECKS = (BALANCE_CHECK, OPENING_CLOSING_CHECK, PRINTED_TOTALS_CHECK)


@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


@dataclass
class PrintedTotals:
    """Totals the bank itself prints on the statement (when it prints them)."""

    debit_count: Optional[int] = None
    credit_count: Optional[int] = None
    total_debits: Optional[float] = None
    total_credits: Optional[float] = None

    def is_empty(self) -> bool:
        return (
            self.debit_count is None
            and self.credit_count is None
            and self.total_debits is None
            and self.total_credits is None
        )


@dataclass
class VerificationReport:
    state: VerificationState
    checks: List[CheckResult]
    # Counts taken from the raw parser rows (before any repair).
    raw_transaction_count: int = 0
    raw_debit_count: int = 0
    raw_credit_count: int = 0
    raw_total_debits: float = 0.0
    raw_total_credits: float = 0.0
    # What repair_transaction_sides did afterwards. Recorded, never used for the state.
    repairs: Dict[str, int] = field(default_factory=dict)
    # Rows after the bank's transaction_validator (step 4), for drop detection.
    validated_transaction_count: Optional[int] = None
    # Why the state is not VERIFIED (stable machine-readable codes). Empty when VERIFIED.
    reasons: List[str] = field(default_factory=list)
    # Informational: evidence that was unavailable but did not change the state on its own.
    notes: List[str] = field(default_factory=list)
    # ROWS_SUSPECT | REFERENCE_MISMATCH_ONLY | DATA_QUALITY | INSUFFICIENT_EVIDENCE | None
    failure_class: Optional[str] = None

    @property
    def failures(self) -> List[str]:
        return [c.name for c in self.checks if c.status == "fail"]

    @property
    def repair_masks_balance_failure(self) -> bool:
        """True when the RAW balance chain failed and repair_transaction_sides then changed rows.

        This is the diagnostic the slice exists for: after repair the chain balances by
        construction, so the existing pipeline would report a clean reconciliation.
        """
        bc = self.check(BALANCE_CHECK)
        changed = int(self.repairs.get("swap", 0) or 0) + int(self.repairs.get("delta_repair", 0) or 0)
        return bool(bc and bc.status == "fail" and changed > 0)

    def check(self, name: str) -> Optional[CheckResult]:
        for c in self.checks:
            if c.name == name:
                return c
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": "v1",
            "observe_only": True,
            "state": self.state,
            "failures": self.failures,
            "reasons": list(self.reasons),
            "notes": list(self.notes),
            "failure_class": self.failure_class,
            "repair_masks_balance_failure": self.repair_masks_balance_failure,
            "raw_transaction_count": self.raw_transaction_count,
            "raw_debit_count": self.raw_debit_count,
            "raw_credit_count": self.raw_credit_count,
            "raw_total_debits": self.raw_total_debits,
            "raw_total_credits": self.raw_total_credits,
            "validated_transaction_count": self.validated_transaction_count,
            "repairs": dict(self.repairs),
            "checks": {c.name: c.to_dict() for c in self.checks},
        }


HeaderPeriod = Tuple[Optional[Any], Optional[Any]]  # (from, to): str | date | None
__all__ = [
    "BALANCE_CHECK",
    "OPENING_CLOSING_CHECK",
    "PRINTED_TOTALS_CHECK",
    "DUPLICATE_CHECK",
    "SCHEMA_CHECK",
    "HEADER_PERIOD_CHECK",
    "HARD_CHECKS",
    "CheckResult",
    "PrintedTotals",
    "VerificationReport",
    "HeaderPeriod",
    "date",
]
