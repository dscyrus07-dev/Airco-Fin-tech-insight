"""
Convert bank-specific parse outputs into NormalizedTransaction[].

Does not modify parsers — call after parse/validate with raw dicts or objects.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.services.banks._shared.date_normalizer import normalize_date_value

from .models import NormalizedTransaction

# Fields that map onto NormalizedTransaction core attributes.
_CORE_KEYS = {
    "date",
    "description",
    "narration",
    "particulars",
    "debit",
    "withdrawal",
    "credit",
    "deposit",
    "balance",
    "closing_balance",
    "ref_no",
    "refNo",
    "cheque_no",
    "value_date",
    "valueDate",
    "is_recurring",
    "isRecurring",
    "recurring_type",
    "recurringType",
    "recurring_frequency",
    "recurringFrequency",
    "category",
    "display_category",
    "confidence",
    "confidence_score",
    "source",
    "classification_source",
    "extras",
}


def _as_mapping(item: Any) -> Dict[str, Any]:
    if isinstance(item, NormalizedTransaction):
        return item.to_dict()
    if isinstance(item, dict):
        return dict(item)
    if hasattr(item, "to_dict") and callable(item.to_dict):
        payload = item.to_dict()
        if isinstance(payload, dict):
            return payload
    # dataclass / simple object
    data: Dict[str, Any] = {}
    for key in (
        "date",
        "description",
        "narration",
        "debit",
        "credit",
        "balance",
        "ref_no",
        "value_date",
        "txn_time",
        "category",
        "confidence",
        "is_recurring",
        "recurring_type",
        "recurring_frequency",
        "source",
    ):
        if hasattr(item, key):
            data[key] = getattr(item, key)
    return data


def _iso_date(raw: Any, bank_key: str = "") -> str:
    if raw is None or raw == "":
        return ""
    if hasattr(raw, "isoformat"):
        try:
            return raw.isoformat()[:10]
        except Exception:
            pass
    text = str(raw).strip()
    # Already ISO
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    try:
        result = normalize_date_value(text, bank_name=bank_key or None)
        iso = getattr(result, "iso_date", None)
        if iso:
            return str(iso)[:10]
        if isinstance(result, dict):
            iso = result.get("iso") or result.get("normalized") or result.get("date")
            if iso:
                return str(iso)[:10]
        if isinstance(result, str) and result:
            return result[:10]
    except Exception:
        pass
    # Best-effort: leave as-is (tests / golden may still compare counts)
    return text


def _pick_amount(data: Dict[str, Any], keys: Sequence[str]) -> Optional[Decimal]:
    for key in keys:
        if key not in data:
            continue
        val = data.get(key)
        if val in (None, "", 0, 0.0, "0", "0.0", "0.00"):
            continue
        try:
            dec = Decimal(str(val).replace(",", "").strip())
            if dec == 0:
                continue
            return dec
        except Exception:
            continue
    return None


def to_normalized(
    raw_transactions: Iterable[Any],
    *,
    bank_key: str = "",
) -> List[NormalizedTransaction]:
    """
    Convert a sequence of bank-specific transactions into NormalizedTransaction[].

    Bank-only fields (txn_time, raw_line, etc.) land in extras.
    Dates are coerced toward ISO via date_normalizer when possible.
    """
    out: List[NormalizedTransaction] = []
    for item in raw_transactions or []:
        data = _as_mapping(item)
        if not data:
            continue

        debit = _pick_amount(data, ("debit", "withdrawal", "Debit", "Withdrawal"))
        credit = _pick_amount(data, ("credit", "deposit", "Credit", "Deposit"))
        # Exactly one side preferred; if both missing leave both None
        if debit is not None and credit is not None:
            # Keep both only if both non-zero (rare); prefer larger magnitude side nulling zeros already done
            pass

        balance_raw = data.get("balance", data.get("closing_balance", data.get("Balance")))
        try:
            balance = Decimal(str(balance_raw).replace(",", "").strip()) if balance_raw not in (None, "") else Decimal("0")
        except Exception:
            balance = Decimal("0")

        conf = data.get("confidence", data.get("confidence_score", 0.0))
        try:
            conf_f = float(conf or 0.0)
            if conf_f > 1.0:
                conf_f = conf_f / 100.0
        except Exception:
            conf_f = 0.0

        extras = dict(data.get("extras") or {})
        for key, value in data.items():
            if key in _CORE_KEYS:
                continue
            if value is None or value == "":
                continue
            extras.setdefault(key, value)

        # Preserve known bank oddities under stable names
        for odd_key in ("txn_time", "raw_line", "line_number", "page", "parse_method"):
            if odd_key in data and data[odd_key] not in (None, ""):
                extras.setdefault(odd_key, data[odd_key])

        description = str(
            data.get("description")
            or data.get("narration")
            or data.get("particulars")
            or ""
        ).strip()
        description = " ".join(description.split())

        date_iso = _iso_date(data.get("date") or data.get("Date"), bank_key=bank_key)
        value_date_raw = data.get("value_date") or data.get("valueDate")
        value_date = _iso_date(value_date_raw, bank_key=bank_key) if value_date_raw else None

        category = str(
            data.get("category") or data.get("display_category") or "Others Debit"
        )
        if debit is not None and credit is None and category == "Others":
            category = "Others Debit"
        if credit is not None and debit is None and category == "Others":
            category = "Others Credit"

        out.append(
            NormalizedTransaction(
                date=date_iso,
                description=description,
                debit=debit,
                credit=credit,
                balance=balance,
                ref_no=str(data.get("ref_no") or data.get("refNo") or data.get("cheque_no") or ""),
                value_date=value_date or None,
                is_recurring=bool(data.get("is_recurring") or data.get("isRecurring") or False),
                recurring_type=data.get("recurring_type") or data.get("recurringType"),
                recurring_frequency=data.get("recurring_frequency") or data.get("recurringFrequency"),
                category=category,
                confidence=conf_f,
                source=str(data.get("source") or data.get("classification_source") or "rule"),
                extras=extras,
            )
        )
    return out


def transactions_to_dicts(
    transactions: Sequence[NormalizedTransaction],
) -> List[Dict[str, Any]]:
    """Adapter for existing Lite metrics / Excel that expect dict rows."""
    return [t.to_dict() for t in transactions]
