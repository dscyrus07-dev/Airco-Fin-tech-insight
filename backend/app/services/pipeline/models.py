"""
Canonical pipeline models — hard boundary between bank-specific parsing
and shared downstream processing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional


def _to_decimal(value: Any, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", "").strip())
    except Exception:
        return Decimal(default)


@dataclass
class NormalizedTransaction:
    """Bank-agnostic transaction after parse + normalize."""

    date: str  # ISO 8601 YYYY-MM-DD
    description: str
    debit: Optional[Decimal] = None
    credit: Optional[Decimal] = None
    balance: Decimal = Decimal("0")
    ref_no: str = ""
    value_date: Optional[str] = None
    is_recurring: bool = False
    recurring_type: Optional[str] = None
    recurring_frequency: Optional[str] = None
    category: str = "Others Debit"
    confidence: float = 0.0
    source: str = "rule"  # rule | ai | fallback
    extras: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Dict form compatible with existing Lite metrics / Excel paths."""
        return {
            "date": self.date,
            "description": self.description,
            "debit": float(self.debit) if self.debit is not None else None,
            "credit": float(self.credit) if self.credit is not None else None,
            "balance": float(self.balance),
            "ref_no": self.ref_no,
            "value_date": self.value_date,
            "is_recurring": self.is_recurring,
            "recurring_type": self.recurring_type,
            "recurring_frequency": self.recurring_frequency,
            "category": self.category,
            "confidence": self.confidence,
            "source": self.source,
            "extras": dict(self.extras or {}),
        }

    @classmethod
    def from_mapping(cls, data: Dict[str, Any]) -> "NormalizedTransaction":
        debit_raw = data.get("debit")
        credit_raw = data.get("credit")
        debit = None if debit_raw in (None, "", 0, 0.0, "0", "0.0") else _to_decimal(debit_raw)
        credit = None if credit_raw in (None, "", 0, 0.0, "0", "0.0") else _to_decimal(credit_raw)
        # Prefer non-zero side when both present
        if debit is not None and credit is not None:
            if debit == 0 and credit != 0:
                debit = None
            elif credit == 0 and debit != 0:
                credit = None
            elif debit == 0 and credit == 0:
                debit = None
                credit = None
        conf = data.get("confidence", data.get("confidence_score", 0.0))
        try:
            conf_f = float(conf or 0.0)
            if conf_f > 1.0:
                conf_f = conf_f / 100.0
        except Exception:
            conf_f = 0.0
        return cls(
            date=str(data.get("date") or ""),
            description=str(data.get("description") or data.get("narration") or "").strip(),
            debit=debit,
            credit=credit,
            balance=_to_decimal(data.get("balance")),
            ref_no=str(data.get("ref_no") or data.get("refNo") or data.get("cheque_no") or ""),
            value_date=(
                str(data["value_date"])
                if data.get("value_date") not in (None, "")
                else (str(data["valueDate"]) if data.get("valueDate") not in (None, "") else None)
            ),
            is_recurring=bool(data.get("is_recurring") or data.get("isRecurring") or False),
            recurring_type=data.get("recurring_type") or data.get("recurringType"),
            recurring_frequency=data.get("recurring_frequency") or data.get("recurringFrequency"),
            category=str(data.get("category") or data.get("display_category") or "Others Debit"),
            confidence=conf_f,
            source=str(data.get("source") or data.get("classification_source") or "rule"),
            extras=dict(data.get("extras") or {}),
        )


@dataclass
class StatementMetadata:
    bank_name: str
    bank_key: str
    account_number: str = ""
    account_holder: str = ""
    account_type: str = ""
    opening_balance: Decimal = Decimal("0")
    closing_balance: Decimal = Decimal("0")
    statement_from: str = ""
    statement_to: str = ""
    extras: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "bank_name": self.bank_name,
            "bank_key": self.bank_key,
            "account_number": self.account_number,
            "account_holder": self.account_holder,
            "account_type": self.account_type,
            "opening_balance": float(self.opening_balance),
            "closing_balance": float(self.closing_balance),
            "statement_from": self.statement_from,
            "statement_to": self.statement_to,
            "name": self.account_holder,
            "account_no": self.account_number,
        }
        payload.update(self.extras or {})
        return payload

    @classmethod
    def from_mapping(
        cls,
        data: Optional[Dict[str, Any]] = None,
        *,
        bank_name: str = "",
        bank_key: str = "",
    ) -> "StatementMetadata":
        data = dict(data or {})
        return cls(
            bank_name=str(data.get("bank_name") or bank_name or ""),
            bank_key=str(data.get("bank_key") or bank_key or ""),
            account_number=str(
                data.get("account_number")
                or data.get("account_no")
                or data.get("accountNumber")
                or ""
            ),
            account_holder=str(
                data.get("account_holder")
                or data.get("full_name")
                or data.get("name")
                or data.get("accountName")
                or ""
            ),
            account_type=str(data.get("account_type") or data.get("accountType") or ""),
            opening_balance=_to_decimal(
                data.get("opening_balance", data.get("openingBalance"))
            ),
            closing_balance=_to_decimal(
                data.get("closing_balance", data.get("closingBalance"))
            ),
            statement_from=str(
                data.get("statement_from") or data.get("statementFrom") or ""
            ),
            statement_to=str(data.get("statement_to") or data.get("statementTo") or ""),
            extras={
                k: v
                for k, v in data.items()
                if k
                not in {
                    "bank_name",
                    "bank_key",
                    "account_number",
                    "account_no",
                    "accountNumber",
                    "account_holder",
                    "full_name",
                    "name",
                    "accountName",
                    "account_type",
                    "accountType",
                    "opening_balance",
                    "openingBalance",
                    "closing_balance",
                    "closingBalance",
                    "statement_from",
                    "statementFrom",
                    "statement_to",
                    "statementTo",
                }
            },
        )


@dataclass
class PipelineResult:
    transactions: List[NormalizedTransaction]
    metadata: StatementMetadata
    reconciliation: Dict[str, Any] = field(default_factory=dict)
    aggregation: Dict[str, Any] = field(default_factory=dict)
    excel_path: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transactions": [t.to_dict() for t in self.transactions],
            "metadata": self.metadata.to_dict(),
            "reconciliation": dict(self.reconciliation or {}),
            "aggregation": dict(self.aggregation or {}),
            "excel_path": self.excel_path,
            "metrics": dict(self.metrics or {}),
        }
