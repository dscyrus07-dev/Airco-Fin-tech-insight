"""
Airco Insights Lite — shared metrics for the 9-sheet Excel export.

Computes Summary statistics and Monthly Analysis metrics from categorized
transactions. Category mapping reuses existing canonical categories from
category_registry / rule engines; mode detection uses description tokens
(same approach as the legacy report generator).
"""

from __future__ import annotations

import re
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.services.banks._shared.category_registry import normalize_category
from app.services.banks._shared.date_normalizer import normalize_date_value

# Canonical display categories → Lite metric keys (where a direct map exists).
# Metrics without a clean category (cash/cheque/bounce/ECS) use description mode.
LITE_CATEGORY_MAP = {
    "Salary": "salaryCredits",
    "ATM Withdrawal": "cashWithdrawals",
    "Loan Payment": "loanRepayment",
    "Credit Card Payment": "creditCardPayment",
    "Bank Charges": "bankCharges",
    "Cash Deposit": "cashDeposit",
}

# Flagged in task notes: no dedicated canonical categories for these —
# they are derived from description/mode tokens instead of category alone.
# - cashDeposit / cashWithdrawals (partially ATM Withdrawal)
# - chequeDeposit / chequeIssued
# - inwBounce / owtBounce
# - ecsNach
# - penaltyCharges

# Prefer multi-word / explicit cheque modes. Avoid bare "chq"/"clg" which
# false-positive on EMI refs like "EMI...CHQS..." and clearing codes.
CHEQUE_TOKENS = (
    "clg chq",
    "chq dep",
    "cheque deposit",
    "cheque issued",
    "chq paid",
    "chq no",
    "cheque no",
    "by chq",
    "by cheque",
    "cheque",
    " chq ",
    " chq.",
    " chq/",
    "chq/",
    "clg/",
    " clearing ",
)

BOUNCE_INW_TOKENS = (
    "inward bounce",
    "inw bounce",
    "i/w bounce",
    "cheque bounce",
    "chq bounce",
    "clg return",
    "chq return",
    "return chq",
    "cheque return",
    "ecs return",
    "nach return",
    "bounce",
)

BOUNCE_OWT_TOKENS = (
    "outward bounce",
    "owt bounce",
    "o/w bounce",
    "outward return",
)

PENALTY_TOKENS = (
    "penal",
    "penalty",
    "late fee",
    "late charge",
    "overdue charge",
    "bounce charge",
    "return charge",
)

CASH_DEPOSIT_TOKENS = (
    "cash deposit",
    "cash dep",
    "cdm",
    "cashdep",
    "dep by cash",
    "by cash",
    "cash credited",
)

CASH_WITHDRAWAL_TOKENS = (
    "cash withdrawal",
    "cash wdl",
    "cash w/d",
    "cashwithdrawal",
    "atm",
    "atw",
    "atm wdl",
    "atm withdrawal",
    "nfs atm",
)

ECS_NACH_TOKENS = (
    "ecs",
    "nach",
    "ach d",
    "ach dr",
    "e-mandate",
    "emandate",
    "autopay",
)

MONTHLY_METRIC_KEYS = (
    "monthlyAvgBal",
    "maxBalance",
    "minBalance",
    "creditCount",
    "creditValue",
    "debitCount",
    "debitValue",
    "cashDeposit",
    "cashWithdrawals",
    "chequeDeposit",
    "chequeIssued",
    "nonCashCredit",
    "inwBounce",
    "owtBounce",
    "ECS/NACH",
    "loanRepayment",
    "creditCardPayment",
    "salaryCredits",
    "penaltyCharges",
    "nonSalaryCredits",
    "bankCharges",
)

SUMMARY_STAT_KEYS = (
    "Total Credit Count",
    "Total Credit Amount",
    "Total Debit Count",
    "Total Debit Amount",
    "Avg Balance",
    "Min Balance",
    "Max Balance",
    "Start of Month Balance",
    "End of Month Balance",
    "Total Cheque",
    "Top 5 Credit Amt",
    "Top 5 Credit %",
    "Top 5 Debit Amt",
    "Top 5 Debit %",
    "Cnt of Cheque Bounces",
    "Min EOD Balance",
    "Max EOD Balance",
    "Average EOD Balance",
    "Balance on 1st",
    "Balance on 5th",
    "Balance on 10th",
    "Balance on 15th",
    "Balance on 20th",
    "Balance on 25th",
    "Balance on Last Day",
)

ACCOUNT_INFO_KEYS = (
    "accountName",
    "jointHolderName",
    "accountNumber",
    "bankName",
    "accountType",
    "IFSC",
    "statementUpload",
    "mobile",
    "email",
    "pan",
    "currentBalance",
    "address",
    "relationshipWithBank",
)


def _to_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").replace("₹", "").strip()
    if not text or text in {"-", "—", "NA", "N/A"}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _parse_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    result = normalize_date_value(value)
    iso = getattr(result, "iso_date", None) if result else None
    if iso:
        try:
            return datetime.fromisoformat(str(iso)[:10]).date()
        except Exception:
            pass
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(text[:20], fmt).date()
        except Exception:
            continue
    return None


def _norm_desc(description: Any) -> str:
    return re.sub(r"\s+", " ", str(description or "").strip().lower())


def _contains_any(text: str, tokens: Sequence[str]) -> bool:
    return any(token in text for token in tokens)


def _is_cheque(description: str) -> bool:
    # Pad so boundary-style tokens like " chq " work on edge positions.
    padded = f" {description} "
    if _contains_any(padded, CHEQUE_TOKENS):
        # Exclude EMI/loan refs that embed CHQS as instrument number, not mode
        if "emi" in description and "chq" in description and "cheque" not in description:
            return False
        return True
    return False


def _is_inw_bounce(description: str, category: str = "") -> bool:
    cat = (category or "").lower()
    if "outward" in cat and "bounce" in cat:
        return False
    if "inward" in cat and "bounce" in cat:
        return True
    if _contains_any(description, BOUNCE_OWT_TOKENS):
        return False
    if _contains_any(description, BOUNCE_INW_TOKENS):
        return True
    # Generic bounce category without direction → treat as inward
    return "bounce" in cat


def _is_owt_bounce(description: str, category: str = "") -> bool:
    cat = (category or "").lower()
    if "outward" in cat and "bounce" in cat:
        return True
    return _contains_any(description, BOUNCE_OWT_TOKENS)


def _is_penalty(description: str, category: str) -> bool:
    cat = (category or "").lower()
    if "penal" in cat or "penalty" in cat or "late fee" in cat:
        return True
    if _contains_any(description, PENALTY_TOKENS):
        return True
    return category in {"Bank Charges"} and _contains_any(description, ("bounce", "return", "penal"))


def _is_salary(description: str, category: str, credit: float) -> bool:
    if credit <= 0:
        return False
    if category == "Salary":
        return True
    cat = (category or "").lower()
    if "salary" in cat or "payroll" in cat:
        return True
    return _contains_any(description, ("salary", "payroll", "sal cr", "salary credit"))


def _is_loan_repayment(description: str, category: str, debit: float) -> bool:
    if debit <= 0:
        return False
    if category == "Loan Payment":
        return True
    cat = (category or "").lower()
    if "loan" in cat and ("emi" in cat or "repay" in cat or "payment" in cat):
        return True
    # Description heuristics — avoid blanket ACHD (many non-loan ACH debits)
    return _contains_any(
        description,
        (
            "emi",
            "loan repayment",
            "loan emi",
            "loan instal",
            "loan install",
            "home loan",
            "personal loan",
            "auto loan",
        ),
    )


def _is_credit_card_payment(description: str, category: str, debit: float) -> bool:
    if debit <= 0:
        return False
    if category == "Credit Card Payment":
        return True
    cat = (category or "").lower()
    if "credit card" in cat:
        return True
    return _contains_any(
        description,
        (
            "cc payment",
            "credit card",
            "cc000",
            "autopaysi",
            "card payment",
            "cc pay",
            "creditcard",
        ),
    )


def _is_cash_deposit(description: str, category: str, credit: float) -> bool:
    if credit <= 0:
        return False
    if category == "Cash Deposit":
        return True
    return _contains_any(description, CASH_DEPOSIT_TOKENS)


def _is_cash_withdrawal(description: str, category: str, debit: float) -> bool:
    if debit <= 0:
        return False
    if category == "ATM Withdrawal":
        return True
    return _contains_any(description, CASH_WITHDRAWAL_TOKENS)


def _is_ecs_nach(description: str, debit: float) -> bool:
    return debit > 0 and _contains_any(description, ECS_NACH_TOKENS)


def _month_key(d: date) -> str:
    return d.strftime("%b-%Y")


def _month_sort_key(label: str) -> Tuple[int, int]:
    try:
        return (datetime.strptime(label, "%b-%Y").year, datetime.strptime(label, "%b-%Y").month)
    except Exception:
        return (9999, 12)


def _format_dd_mmm_yyyy(d: Optional[date]) -> str:
    if not d:
        return ""
    return d.strftime("%d-%b-%Y")


def _format_relationship(open_date: Optional[date], as_of: Optional[date]) -> str:
    """Human tenure string, e.g. '9 years and 5 months' (blank if open date unknown)."""
    if not open_date or not as_of or open_date > as_of:
        return ""
    years = as_of.year - open_date.year
    months = as_of.month - open_date.month
    if as_of.day < open_date.day:
        months -= 1
    if months < 0:
        years -= 1
        months += 12
    if years < 0:
        return ""
    # Spec example uses singular forms; keep plural for multi-unit accuracy.
    year_label = "year" if years == 1 else "years"
    month_label = "month" if months == 1 else "months"
    if years == 0:
        return f"{months} {month_label}"
    if months == 0:
        return f"{years} {year_label}"
    return f"{years} {year_label} and {months} {month_label}"


def _join_joint_holders(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v).strip() for v in value if str(v).strip())
    return str(value).strip()


def normalize_transactions(transactions: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize pipeline transactions into a stable Lite shape.

    Preserves input order (statement order) so the Transactions sheet stays complete
    and sequential. EOD series sorts a dated copy internally.
    """
    rows: List[Dict[str, Any]] = []
    for idx, raw in enumerate(transactions or []):
        debit = _to_float(raw.get("debit") if raw.get("debit") is not None else raw.get("Debit"))
        credit = _to_float(raw.get("credit") if raw.get("credit") is not None else raw.get("Credit"))
        balance = _to_float(raw.get("balance") if raw.get("balance") is not None else raw.get("Balance"))
        description = str(
            raw.get("description")
            or raw.get("Description")
            or raw.get("narration")
            or raw.get("particulars")
            or ""
        ).strip()
        category_raw = raw.get("category") or raw.get("Category") or raw.get("display_category") or ""
        is_debit = debit > 0 and credit <= 0
        category = normalize_category(str(category_raw), is_debit=is_debit)
        txn_date = _parse_date(raw.get("date") or raw.get("Date") or raw.get("value_date"))
        ref = str(
            raw.get("ref_no")
            or raw.get("RefNo")
            or raw.get("chq_no")
            or raw.get("cheque_no")
            or raw.get("reference_number")
            or raw.get("reference")
            or ""
        ).strip()
        desc_norm = _norm_desc(description)
        is_penalty = _is_penalty(desc_norm, category)
        rows.append(
            {
                "date": txn_date,
                "date_display": _format_dd_mmm_yyyy(txn_date),
                "description": description,
                "ref_no": ref,
                "debit": round(debit, 2),
                "credit": round(credit, 2),
                "balance": round(balance, 2),
                "category": category,
                "month": _month_key(txn_date) if txn_date else "",
                "seq": idx,
                "is_cheque": _is_cheque(desc_norm),
                "is_inw_bounce": _is_inw_bounce(desc_norm, category),
                "is_owt_bounce": _is_owt_bounce(desc_norm, category),
                "is_penalty": is_penalty,
                "is_cash_deposit": _is_cash_deposit(desc_norm, category, credit),
                "is_cash_withdrawal": _is_cash_withdrawal(desc_norm, category, debit),
                "is_ecs_nach": _is_ecs_nach(desc_norm, debit),
                "is_salary": _is_salary(desc_norm, category, credit),
                "is_loan_repayment": _is_loan_repayment(desc_norm, category, debit),
                "is_credit_card_payment": _is_credit_card_payment(desc_norm, category, debit),
                "is_bank_charge": category == "Bank Charges" and debit > 0 and not is_penalty,
            }
        )
    return rows


def build_eod_series(
    transactions: Sequence[Dict[str, Any]],
    statement_from: Optional[date] = None,
    statement_to: Optional[date] = None,
    opening_balance: Optional[float] = None,
) -> Dict[date, float]:
    """
    Day-by-day EOD balance ledger.
    Days without transactions carry forward the previous EOD balance.
    """
    # Sort by date then original sequence so multi-txn days keep statement order.
    rows = sorted(
        [r for r in transactions if r.get("date")],
        key=lambda r: (r["date"], r.get("seq", 0)),
    )
    if not rows and opening_balance is None:
        return {}

    start = statement_from or (rows[0]["date"] if rows else None)
    end = statement_to or (rows[-1]["date"] if rows else None)
    if not start or not end:
        return {}
    if start > end:
        start, end = end, start

    # Infer opening if not provided: first balance - credit + debit
    if opening_balance is None and rows:
        first = rows[0]
        opening_balance = first["balance"] - first["credit"] + first["debit"]
    opening_balance = float(opening_balance or 0.0)

    by_day: Dict[date, List[Dict[str, Any]]] = {}
    for row in rows:
        by_day.setdefault(row["date"], []).append(row)

    eod: Dict[date, float] = {}
    running = opening_balance
    current = start
    while current <= end:
        day_txns = by_day.get(current, [])
        if day_txns:
            # Prefer last posted balance on that day (statement order within day)
            running = day_txns[-1]["balance"]
        eod[current] = round(float(running), 2)
        current += timedelta(days=1)
    return eod


def _month_labels(eod: Dict[date, float], transactions: Sequence[Dict[str, Any]]) -> List[str]:
    labels = set()
    for d in eod.keys():
        labels.add(_month_key(d))
    for row in transactions:
        if row.get("month"):
            labels.add(row["month"])
    return sorted(labels, key=_month_sort_key)


def _days_in_month(year: int, month: int) -> int:
    return monthrange(year, month)[1]


def _avg(values: Iterable[float]) -> float:
    vals = list(values)
    if not vals:
        return 0.0
    return round(sum(vals) / len(vals), 2)


def compute_account_info(
    metadata: Optional[Dict[str, Any]],
    transactions: Sequence[Dict[str, Any]],
) -> Dict[str, str]:
    meta = dict(metadata or {})
    rows = list(transactions)
    start = _parse_date(meta.get("statement_from") or meta.get("statementFrom"))
    end = _parse_date(meta.get("statement_to") or meta.get("statementTo"))
    if not start and rows:
        start = rows[0].get("date")
    if not end and rows:
        end = rows[-1].get("date")

    joint = _join_joint_holders(
        meta.get("jointHolderName")
        or meta.get("joint_holder_name")
        or meta.get("joint_holders")
        or meta.get("jointHolders")
        or []
    )
    current_balance = meta.get("currentBalance") or meta.get("closing_balance") or meta.get("closingBalance")
    if current_balance in (None, "") and rows:
        current_balance = rows[-1].get("balance", "")

    open_date = _parse_date(
        meta.get("account_open_date")
        or meta.get("accountOpenDate")
        or meta.get("opening_date")
        or meta.get("relationship_start")
    )
    relationship = meta.get("relationshipWithBank") or meta.get("relationship_with_bank") or ""
    if not relationship:
        relationship = _format_relationship(open_date, end)

    statement_upload = ""
    if start and end:
        statement_upload = f"{_format_dd_mmm_yyyy(start)} to {_format_dd_mmm_yyyy(end)}"
    elif meta.get("statementUpload"):
        statement_upload = str(meta.get("statementUpload"))

    info = {
        "accountName": str(
            meta.get("accountName")
            or meta.get("account_holder")
            or meta.get("name")
            or meta.get("full_name")
            or ""
        ).strip(),
        "jointHolderName": joint,
        "accountNumber": str(
            meta.get("accountNumber")
            or meta.get("account_no")
            or meta.get("account_number")
            or ""
        ).strip(),
        "bankName": str(meta.get("bankName") or meta.get("bank_name") or "").strip(),
        "accountType": str(meta.get("accountType") or meta.get("account_type") or "").strip(),
        "IFSC": str(meta.get("IFSC") or meta.get("ifsc") or "").strip(),
        "statementUpload": statement_upload,
        "mobile": str(meta.get("mobile") or meta.get("phone") or "").strip(),
        "email": str(meta.get("email") or "").strip(),
        "pan": str(meta.get("pan") or meta.get("PAN") or "").strip(),
        "currentBalance": (
            f"{_to_float(current_balance):.2f}" if current_balance not in (None, "") else ""
        ),
        "address": str(meta.get("address") or "").strip(),
        "relationshipWithBank": str(relationship or "").strip(),
    }
    # Never omit keys
    return {key: info.get(key, "") for key in ACCOUNT_INFO_KEYS}


def compute_summary_stats(
    transactions: Sequence[Dict[str, Any]],
    eod: Dict[date, float],
    month_labels: Sequence[str],
) -> Dict[str, Any]:
    """
    Summary statistics — every metric is a per-month map so the Summary sheet
    can render one column per month (matching the reference multi-month layout).
    """
    # Per-month maps for multi-column summary rows
    per_month: Dict[str, Dict[str, float]] = {}
    for label in month_labels:
        try:
            month_dt = datetime.strptime(label, "%b-%Y")
            year, month = month_dt.year, month_dt.month
        except Exception:
            continue

        month_rows = [
            r
            for r in transactions
            if r.get("date") and r["date"].year == year and r["date"].month == month
        ]
        month_credits = [r for r in month_rows if r["credit"] > 0]
        month_debits = [r for r in month_rows if r["debit"] > 0]
        credit_amt = round(sum(r["credit"] for r in month_credits), 2)
        debit_amt = round(sum(r["debit"] for r in month_debits), 2)
        top5_credit_amt = round(
            sum(r["credit"] for r in sorted(month_credits, key=lambda x: x["credit"], reverse=True)[:5]),
            2,
        )
        top5_debit_amt = round(
            sum(r["debit"] for r in sorted(month_debits, key=lambda x: x["debit"], reverse=True)[:5]),
            2,
        )
        balances = [r["balance"] for r in month_rows]
        month_eod = {d: bal for d, bal in eod.items() if d.year == year and d.month == month}

        if not month_eod:
            per_month[label] = {
                "credit_count": float(len(month_credits)),
                "credit_amt": credit_amt,
                "debit_count": float(len(month_debits)),
                "debit_amt": debit_amt,
                "avg_bal": _avg(balances),
                "min_bal": min(balances) if balances else 0.0,
                "max_bal": max(balances) if balances else 0.0,
                "start": 0.0,
                "end": 0.0,
                "cheque": float(sum(1 for r in month_rows if r["is_cheque"])),
                "top5_credit_amt": top5_credit_amt,
                "top5_credit_pct": round((top5_credit_amt / credit_amt * 100) if credit_amt else 0.0, 2),
                "top5_debit_amt": top5_debit_amt,
                "top5_debit_pct": round((top5_debit_amt / debit_amt * 100) if debit_amt else 0.0, 2),
                "bounce": float(sum(1 for r in month_rows if r["is_inw_bounce"] or r["is_owt_bounce"])),
                "min_eod": 0.0,
                "max_eod": 0.0,
                "avg_eod": 0.0,
                "d1": 0.0,
                "d5": 0.0,
                "d10": 0.0,
                "d15": 0.0,
                "d20": 0.0,
                "d25": 0.0,
                "dlast": 0.0,
            }
            continue

        days = sorted(month_eod.keys())
        last_day = days[-1]
        first_calendar = date(year, month, 1)
        # Start of month = EOD of day before month start (opening of day 1).
        # Falls back to first available EOD in the month when prior day is out of range.
        prev_day = first_calendar - timedelta(days=1)
        start_of_month = eod.get(prev_day, month_eod[days[0]])

        def _anchor(day_num: int) -> float:
            if day_num > _days_in_month(year, month):
                return month_eod[last_day]
            target = date(year, month, day_num)
            if target in month_eod:
                return month_eod[target]
            # Closest available day in-month (statement may start mid-month)
            return month_eod[min(days, key=lambda d: abs(d.day - day_num))]

        eod_vals = list(month_eod.values())
        per_month[label] = {
            "credit_count": float(len(month_credits)),
            "credit_amt": credit_amt,
            "debit_count": float(len(month_debits)),
            "debit_amt": debit_amt,
            "avg_bal": _avg(balances) if balances else _avg(eod_vals),
            "min_bal": min(balances) if balances else min(eod_vals),
            "max_bal": max(balances) if balances else max(eod_vals),
            "start": start_of_month,
            "end": month_eod[last_day],
            "cheque": float(sum(1 for r in month_rows if r["is_cheque"])),
            "top5_credit_amt": top5_credit_amt,
            "top5_credit_pct": round((top5_credit_amt / credit_amt * 100) if credit_amt else 0.0, 2),
            "top5_debit_amt": top5_debit_amt,
            "top5_debit_pct": round((top5_debit_amt / debit_amt * 100) if debit_amt else 0.0, 2),
            "bounce": float(sum(1 for r in month_rows if r["is_inw_bounce"] or r["is_owt_bounce"])),
            "min_eod": min(eod_vals),
            "max_eod": max(eod_vals),
            "avg_eod": _avg(eod_vals),
            "d1": _anchor(1),
            "d5": _anchor(5),
            "d10": _anchor(10),
            "d15": _anchor(15),
            "d20": _anchor(20),
            "d25": _anchor(25),
            "dlast": month_eod[last_day],
        }

    def _col(key: str) -> Dict[str, float]:
        return {m: per_month[m][key] for m in month_labels if m in per_month}

    return {
        "Total Credit Count": _col("credit_count"),
        "Total Credit Amount": _col("credit_amt"),
        "Total Debit Count": _col("debit_count"),
        "Total Debit Amount": _col("debit_amt"),
        "Avg Balance": _col("avg_bal"),
        "Min Balance": _col("min_bal"),
        "Max Balance": _col("max_bal"),
        "Start of Month Balance": _col("start"),
        "End of Month Balance": _col("end"),
        "Total Cheque": _col("cheque"),
        "Top 5 Credit Amt": _col("top5_credit_amt"),
        "Top 5 Credit %": _col("top5_credit_pct"),
        "Top 5 Debit Amt": _col("top5_debit_amt"),
        "Top 5 Debit %": _col("top5_debit_pct"),
        "Cnt of Cheque Bounces": _col("bounce"),
        "Min EOD Balance": _col("min_eod"),
        "Max EOD Balance": _col("max_eod"),
        "Average EOD Balance": _col("avg_eod"),
        "Balance on 1st": _col("d1"),
        "Balance on 5th": _col("d5"),
        "Balance on 10th": _col("d10"),
        "Balance on 15th": _col("d15"),
        "Balance on 20th": _col("d20"),
        "Balance on 25th": _col("d25"),
        "Balance on Last Day": _col("dlast"),
        "_per_month": per_month,
    }


def compute_monthly_analysis(
    transactions: Sequence[Dict[str, Any]],
    eod: Dict[date, float],
    month_labels: Sequence[str],
) -> Dict[str, Dict[str, float]]:
    """
    One value per metric per month.
    inwBounce / owtBounce are COUNTS (matches legacy bounce aggregation style).
    """
    result: Dict[str, Dict[str, float]] = {key: {} for key in MONTHLY_METRIC_KEYS}

    for label in month_labels:
        try:
            month_dt = datetime.strptime(label, "%b-%Y")
            year, month = month_dt.year, month_dt.month
        except Exception:
            for key in MONTHLY_METRIC_KEYS:
                result[key][label] = 0.0
            continue

        month_rows = [r for r in transactions if r.get("date") and r["date"].year == year and r["date"].month == month]
        month_eod = [bal for d, bal in eod.items() if d.year == year and d.month == month]

        credit_value = round(sum(r["credit"] for r in month_rows if r["credit"] > 0), 2)
        debit_value = round(sum(r["debit"] for r in month_rows if r["debit"] > 0), 2)
        cash_deposit = round(sum(r["credit"] for r in month_rows if r["is_cash_deposit"]), 2)
        cash_withdrawals = round(sum(r["debit"] for r in month_rows if r["is_cash_withdrawal"]), 2)
        cheque_deposit = round(sum(r["credit"] for r in month_rows if r["is_cheque"] and r["credit"] > 0), 2)
        cheque_issued = round(sum(r["debit"] for r in month_rows if r["is_cheque"] and r["debit"] > 0), 2)
        salary_credits = round(sum(r["credit"] for r in month_rows if r["is_salary"]), 2)
        loan_repayment = round(sum(r["debit"] for r in month_rows if r["is_loan_repayment"]), 2)
        cc_payment = round(sum(r["debit"] for r in month_rows if r["is_credit_card_payment"]), 2)
        penalty = round(sum(r["debit"] for r in month_rows if r["is_penalty"] and r["debit"] > 0), 2)
        bank_charges = round(sum(r["debit"] for r in month_rows if r["is_bank_charge"]), 2)
        ecs_nach = round(sum(r["debit"] for r in month_rows if r["is_ecs_nach"]), 2)
        inw = float(sum(1 for r in month_rows if r["is_inw_bounce"]))
        owt = float(sum(1 for r in month_rows if r["is_owt_bounce"]))

        values = {
            "monthlyAvgBal": _avg(month_eod),
            "maxBalance": max(month_eod) if month_eod else 0.0,
            "minBalance": min(month_eod) if month_eod else 0.0,
            "creditCount": float(sum(1 for r in month_rows if r["credit"] > 0)),
            "creditValue": credit_value,
            "debitCount": float(sum(1 for r in month_rows if r["debit"] > 0)),
            "debitValue": debit_value,
            "cashDeposit": cash_deposit,
            "cashWithdrawals": cash_withdrawals,
            "chequeDeposit": cheque_deposit,
            "chequeIssued": cheque_issued,
            "nonCashCredit": round(credit_value - cash_deposit, 2),
            "inwBounce": inw,
            "owtBounce": owt,
            "ECS/NACH": ecs_nach,
            "loanRepayment": loan_repayment,
            "creditCardPayment": cc_payment,
            "salaryCredits": salary_credits,
            "penaltyCharges": penalty,
            "nonSalaryCredits": round(credit_value - salary_credits, 2),
            "bankCharges": bank_charges,
        }
        for key in MONTHLY_METRIC_KEYS:
            result[key][label] = values[key]
    return result


def top_n_transactions(
    transactions: Sequence[Dict[str, Any]],
    *,
    side: str,
    n: int = 5,
) -> List[Dict[str, Any]]:
    if side == "credit":
        pool = [r for r in transactions if r["credit"] > 0]
        pool = sorted(pool, key=lambda r: r["credit"], reverse=True)[:n]
    else:
        pool = [r for r in transactions if r["debit"] > 0]
        pool = sorted(pool, key=lambda r: r["debit"], reverse=True)[:n]
    return pool


def filter_transactions(
    transactions: Sequence[Dict[str, Any]],
    kind: str,
) -> List[Dict[str, Any]]:
    kind = kind.lower()
    if kind == "bounce_penal":
        return [r for r in transactions if r["is_inw_bounce"] or r["is_owt_bounce"] or r["is_penalty"]]
    if kind == "salary":
        return [r for r in transactions if r["is_salary"]]
    if kind == "loan":
        return [r for r in transactions if r["is_loan_repayment"]]
    if kind == "credit_card":
        return [r for r in transactions if r["is_credit_card_payment"]]
    return list(transactions)


def _coerce_txn_dicts(transactions: Sequence[Any]) -> List[Dict[str, Any]]:
    """Accept dict rows or NormalizedTransaction-like objects."""
    out: List[Dict[str, Any]] = []
    for item in transactions or []:
        if isinstance(item, dict):
            out.append(item)
            continue
        if hasattr(item, "to_dict") and callable(item.to_dict):
            payload = item.to_dict()
            if isinstance(payload, dict):
                out.append(payload)
                continue
        # Minimal attribute fallback
        out.append(
            {
                "date": getattr(item, "date", ""),
                "description": getattr(item, "description", ""),
                "debit": getattr(item, "debit", None),
                "credit": getattr(item, "credit", None),
                "balance": getattr(item, "balance", 0),
                "category": getattr(item, "category", ""),
                "ref_no": getattr(item, "ref_no", ""),
            }
        )
    return out


def build_lite_report_model(
    transactions: Sequence[Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Full Lite report model used by the Excel generator.

    Accepts dict rows (legacy) or NormalizedTransaction objects (Phase 1+).
    """
    meta = dict(metadata or {})
    rows = normalize_transactions(_coerce_txn_dicts(transactions))
    start = _parse_date(meta.get("statement_from") or meta.get("statementFrom"))
    end = _parse_date(meta.get("statement_to") or meta.get("statementTo"))
    if not start and rows:
        start = rows[0]["date"]
    if not end and rows:
        end = rows[-1]["date"]
    opening = meta.get("opening_balance")
    if opening is None:
        opening = meta.get("openingBalance")
    eod = build_eod_series(rows, statement_from=start, statement_to=end, opening_balance=opening)
    months = _month_labels(eod, rows)
    account_info = compute_account_info(meta, rows)
    summary = compute_summary_stats(rows, eod, months)
    monthly = compute_monthly_analysis(rows, eod, months)
    return {
        "account_info": account_info,
        "summary_stats": summary,
        "monthly_analysis": monthly,
        "month_labels": months,
        "transactions": rows,
        "top5_credits": top_n_transactions(rows, side="credit", n=5),
        "top5_debits": top_n_transactions(rows, side="debit", n=5),
        "bounce_penal": filter_transactions(rows, "bounce_penal"),
        "salary": filter_transactions(rows, "salary"),
        "loan": filter_transactions(rows, "loan"),
        "credit_card": filter_transactions(rows, "credit_card"),
        "eod": eod,
    }
