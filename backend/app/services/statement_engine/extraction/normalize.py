"""Normalization of raw rows into the existing canonical NormalizedTransaction (RAW stage: no repair)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from app.services.pipeline.models import NormalizedTransaction

from .layout_spec import LayoutSpec
from .rows import RawRow


class NormalizeError(ValueError):
    pass


def parse_amount(text: str) -> Optional[Decimal]:
    """Decimal from a printed amount ("1,234.50", "-20,000.00"); None for empty text."""
    t = (text or "").strip()
    if not t:
        return None
    t = t.replace(",", "")
    negative = t.startswith("(") and t.endswith(")")     # accounting style: (1234.50) is -1234.50
    if negative:
        t = t[1:-1]
    try:
        return -Decimal(t) if negative else Decimal(t)
    except InvalidOperation as exc:
        raise NormalizeError(f"bad amount {text!r}") from exc


def parse_date(text: str, fmt: str) -> str:
    """ISO date from a printed date; an impossible calendar date is an error, never coerced."""
    try:
        return datetime.strptime(text.strip(), fmt).date().isoformat()
    except ValueError as exc:
        raise NormalizeError(f"bad date {text!r}") from exc


@dataclass
class NormalizedRow:
    txn: NormalizedTransaction
    page: int
    printed_side: str            # role of the printed money column: the spec's debit or credit column
    reversal: bool               # printed as a negative amount
    row_warnings: List[str] = field(default_factory=list)
    printed_kind: str = "debit"  # "debit" | "credit": which side of the statement the printed column belongs to


def normalize_rows(rows: List[RawRow], spec: LayoutSpec) -> Tuple[List[NormalizedRow], List[str]]:
    """Returns (rows, errors). Rows that cannot be normalized are reported in errors and omitted."""
    out: List[NormalizedRow] = []
    errors: List[str] = []
    for i, r in enumerate(rows):
        try:
            date = parse_date(r.date, spec.date_format)
            value_date = parse_date(r.value_date, spec.date_format) if r.value_date.strip() else None
            wd = parse_amount(r.amounts.get(spec.debit_column, ""))
            dp = parse_amount(r.amounts.get(spec.credit_column, ""))
            bal = parse_amount(r.amounts.get(spec.balance_column, ""))
            if bal is None:
                raise NormalizeError("missing balance")
            if (wd is None) == (dp is None):
                raise NormalizeError("row must carry exactly one of the debit/credit columns")
            if wd is not None:
                side, amount = spec.debit_column, wd
            else:
                side, amount = spec.credit_column, dp  # type: ignore[assignment]
            reversal = amount < 0
            magnitude = abs(amount)
            # canonical debit/credit are non-negative and consistent with the balance move: a negative debit-column amount
            # (reversal of a debit) is a credit, a negative credit-column amount is a debit
            is_debit = (side == spec.debit_column) != reversal
            txn = NormalizedTransaction(
                date=date,
                description=r.narration,
                debit=magnitude if is_debit else None,
                credit=None if is_debit else magnitude,
                balance=bal,
                ref_no=r.ref,
                value_date=value_date,
                extras={"page": r.page, "printed_side": side, "reversal": reversal},
            )
            out.append(NormalizedRow(txn=txn, page=r.page, printed_side=side, reversal=reversal, row_warnings=list(r.warnings),
                                    printed_kind="debit" if side == spec.debit_column else "credit"))
        except NormalizeError as exc:
            errors.append(f"row{i + 1}(page{r.page}): {exc}")
    return out, errors
