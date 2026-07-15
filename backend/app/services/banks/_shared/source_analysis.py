"""
Shared Source Analysis and Category Outcome helper functions
Used across multiple banks for Excel generation
"""

import pandas as pd
from typing import Dict, Any, Tuple, List
from .category_registry import normalize_category


def _detect_transaction_mode(description: str) -> str:
    """Detect transaction mode from description."""
    desc = str(description).upper()
    if any(k in desc for k in ["UPI", "UPI/", "UPI-"]):
        return "UPI"
    elif any(k in desc for k in ["NEFT", "IMPS", "RTGS"]):
        return "NEFT/IMPS/RTGS"
    elif any(k in desc for k in ["ATM", "ATW", "CASH WDL"]):
        return "ATM"
    elif any(k in desc for k in ["CHQ", "CHEQUE", "CLG"]):
        return "CHEQUE"
    elif any(k in desc for k in ["POS", "CARD", "ECOM"]):
        return "CARD"
    elif any(k in desc for k in ["TRF", "TRANSFER"]):
        return "TRANSFER"
    else:
        return "OTHER"


def _extract_source(description: str, mode: str) -> str:
    """Extract source from description based on transaction mode."""
    desc = str(description).upper()
    
    if mode == "UPI":
        # Extract UPI ID or phone number
        for separator in ["@", "-"]:
            if separator in desc:
                parts = desc.split(separator)
                if len(parts) > 1:
                    return parts[0].strip()
        return "UPI"
    elif mode == "ATM":
        # Extract ATM location or ID
        for keyword in ["ATM", "ATW"]:
            if keyword in desc:
                idx = desc.index(keyword)
                return desc[idx:idx+20].strip()
        return "ATM"
    elif mode == "CHEQUE":
        # Extract cheque number
        for word in desc.split():
            if word.isdigit() and len(word) >= 6:
                return word
        return "CHEQUE"
    elif mode == "CARD":
        # Extract merchant name
        for keyword in ["POS", "CARD", "ECOM"]:
            if keyword in desc:
                idx = desc.index(keyword)
                return desc[idx+4:idx+30].strip()
        return "CARD"
    else:
        # For other modes, use first 20 chars
        return desc[:20].strip()


def _map_identified_category(source: str, mode: str, description: str, category: str, is_credit: bool) -> str:
    """Map identified category based on source, mode, and description."""
    desc = str(description).upper()
    cat = str(category).upper()
    
    if is_credit:
        if any(k in desc for k in ["SALARY", "PAYROLL", "WAGES"]):
            return "Salary"
        elif any(k in desc for k in ["REFUND", "REVERSAL"]):
            return "Refund"
        elif any(k in desc for k in ["LOAN", "EMI", "FINANCE"]):
            return "Loan Disbursed"
        else:
            return normalize_category(cat, is_debit=False)
    else:
        if any(k in desc for k in ["EMI", "LOAN REPAY"]):
            return "Loan Payment"
        elif any(k in desc for k in ["CC PAY", "CREDIT CARD"]):
            return "Credit Card Payment"
        elif any(k in desc for k in ["PENALTY", "CHARGE", "FEE"]):
            return "Bank Charges"
        else:
            return normalize_category(cat, is_debit=True)


def _flag_transaction(amount: float, source: str, is_recurring: bool, mode: str) -> str:
    """Flag transaction based on amount, source, and recurring status."""
    if is_recurring:
        return "Recurring"
    elif amount > 100000:
        return "High Value"
    elif mode == "UPI":
        return "UPI"
    elif mode == "ATM":
        return "ATM"
    else:
        return ""


def build_source_analysis_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Build source analysis frame from transaction data."""
    frame = df.copy()
    frame["TransactionMode"] = frame["Description"].apply(_detect_transaction_mode)
    frame["Source"] = [
        _extract_source(desc, mode)
        for desc, mode in zip(frame["Description"], frame["TransactionMode"])
    ]
    frame["IsCredit"] = frame["Credit"].fillna(0) > 0
    frame["Category"] = [
        normalize_category(
            cat,
            is_debit=bool(debit) and not bool(credit),
        )
        for cat, debit, credit in zip(
            frame["Category"].fillna(""),
            frame["Debit"].fillna(0),
            frame["Credit"].fillna(0),
        )
    ]
    frame["TxnAmount"] = frame["Credit"].where(frame["Credit"].fillna(0) > 0, frame["Debit"].fillna(0))

    recurring_keys = set()
    source_groups = frame.groupby(frame["Source"].str.lower().fillna("unknown"))
    for key, group in source_groups:
        if key == "unknown" or len(group) < 3:
            continue
        month_count = group["Date"].dt.to_period("M").nunique() if "Date" in group else 0
        if month_count >= 2:
            recurring_keys.add(key)

    frame["IsRecurring"] = frame["Source"].str.lower().fillna("unknown").isin(recurring_keys)
    frame["IdentifiedCategory"] = [
        normalize_category(
            _map_identified_category(source, mode, desc, cat, is_credit),
            is_debit=not is_credit,
        )
        for source, mode, desc, cat, is_credit in zip(
            frame["Source"],
            frame["TransactionMode"],
            frame["Description"],
            frame["Category"],
            frame["IsCredit"],
        )
    ]
    frame["Flag"] = [
        _flag_transaction(amount, source, recurring, mode)
        for amount, source, recurring, mode in zip(
            frame["TxnAmount"].fillna(0),
            frame["Source"],
            frame["IsRecurring"],
            frame["TransactionMode"],
        )
    ]
    frame["Month"] = frame["Date"].dt.to_period("M").astype(str)
    return frame


def build_category_outcome_tables(source_frame: pd.DataFrame) -> Dict[str, Any]:
    """Build category outcome tables from source analysis frame."""
    frame = source_frame.copy()

    if "IdentifiedCategory" not in frame.columns:
        frame["IdentifiedCategory"] = "Others"

    frame["Category"] = [
        normalize_category(cat, is_debit=False)
        for cat in frame["IdentifiedCategory"].fillna("").astype(str)
    ]
    frame.loc[frame["Category"] == "", "Category"] = "Others"
    frame["Source"] = frame["Source"].fillna("").astype(str).str.strip()
    frame.loc[frame["Source"] == "", "Source"] = "Unknown"
    frame["Month"] = frame["Month"].fillna("").astype(str).str.strip()
    frame["Credit"] = pd.to_numeric(frame["Credit"], errors="coerce").fillna(0)
    frame["Debit"] = pd.to_numeric(frame["Debit"], errors="coerce").fillna(0)
    frame["Flag"] = frame.get("Flag", "")
    frame["Flag"] = frame["Flag"].fillna("").astype(str).str.strip()

    month_dt = pd.to_datetime(frame["Month"], errors="coerce")
    frame["MonthKey"] = month_dt.dt.to_period("M").astype(str)
    month_periods = []
    for period in month_dt.dropna().dt.to_period("M").tolist():
        if period not in month_periods:
            month_periods.append(period)
    month_periods = sorted(month_periods)[:6]
    month_keys = [period.strftime("%Y-%m") for period in month_periods]
    month_labels = [period.strftime("%B %Y") for period in month_periods]
    month_lookup = dict(zip(month_keys, month_labels))

    def _pivot_metric(value_col: str, filter_mask: pd.Series, agg_kind: str) -> pd.DataFrame:
        base = frame.loc[filter_mask, ["Category", "Source", "MonthKey", value_col]].copy()
        if base.empty:
            return pd.DataFrame(columns=["Category", "Source", *month_labels])

        if agg_kind == "count":
            base["MetricValue"] = 1
        else:
            base["MetricValue"] = base[value_col]

        grouped = (
            base.groupby(["Category", "Source", "MonthKey"], dropna=False)["MetricValue"]
            .sum()
            .reset_index()
        )
        pivot = grouped.pivot_table(
            index=["Category", "Source"],
            columns="MonthKey",
            values="MetricValue",
            aggfunc="sum",
            fill_value=0,
        )

        pivot = pivot.reindex(columns=month_keys, fill_value=0).reset_index()
        pivot = pivot.rename(columns=month_lookup)
        for label in month_labels:
            if label not in pivot.columns:
                pivot[label] = 0
        return pivot[["Category", "Source", *month_labels]]

    regular_categories = frame["Category"].ne("Flag")
    credit_rows = frame["Credit"] > 0
    debit_rows = frame["Debit"] > 0
    flagged_rows = frame["Flag"].ne("")

    credit_count = _pivot_metric("Credit", regular_categories & credit_rows, "count")
    debit_count = _pivot_metric("Debit", regular_categories & debit_rows, "count")
    credit_amount = _pivot_metric("Credit", regular_categories & credit_rows, "sum")
    debit_amount = _pivot_metric("Debit", regular_categories & debit_rows, "sum")

    flag_rows = frame.loc[flagged_rows, ["MonthKey", "Credit", "Debit"]].copy()
    if not flag_rows.empty:
        flag_agg = flag_rows.groupby("MonthKey", dropna=False).agg(
            CreditCount=("Credit", lambda s: int((s.fillna(0) > 0).sum())),
            DebitCount=("Debit", lambda s: int((s.fillna(0) > 0).sum())),
            CreditAmount=("Credit", lambda s: float(s.fillna(0).sum())),
            DebitAmount=("Debit", lambda s: float(s.fillna(0).sum())),
        )
        flag_row_count = {"Category": "Flag", "Source": ""}
        flag_row_debit_count = {"Category": "Flag", "Source": ""}
        flag_row_credit_amt = {"Category": "Flag", "Source": ""}
        flag_row_debit_amt = {"Category": "Flag", "Source": ""}
        for month_key, label in month_lookup.items():
            flag_row_count[label] = int(flag_agg.loc[month_key, "CreditCount"]) if month_key in flag_agg.index else 0
            flag_row_debit_count[label] = int(flag_agg.loc[month_key, "DebitCount"]) if month_key in flag_agg.index else 0
            flag_row_credit_amt[label] = float(flag_agg.loc[month_key, "CreditAmount"]) if month_key in flag_agg.index else 0
            flag_row_debit_amt[label] = float(flag_agg.loc[month_key, "DebitAmount"]) if month_key in flag_agg.index else 0

        flag_credit_count = pd.DataFrame([flag_row_count])
        flag_debit_count = pd.DataFrame([flag_row_debit_count])
        flag_credit_amount = pd.DataFrame([flag_row_credit_amt])
        flag_debit_amount = pd.DataFrame([flag_row_debit_amt])

        def _append_flag_row(table: pd.DataFrame) -> pd.DataFrame:
            table = table.copy()
            for label in month_labels:
                if label not in table.columns:
                    table[label] = 0
            ordered = table[["Category", "Source", *month_labels]] if not table.empty else pd.DataFrame(columns=["Category", "Source", *month_labels])
            return ordered

        credit_count = pd.concat([_append_flag_row(credit_count), flag_credit_count], ignore_index=True, sort=False)
        debit_count = pd.concat([_append_flag_row(debit_count), flag_debit_count], ignore_index=True, sort=False)
        credit_amount = pd.concat([_append_flag_row(credit_amount), flag_credit_amount], ignore_index=True, sort=False)
        debit_amount = pd.concat([_append_flag_row(debit_amount), flag_debit_amount], ignore_index=True, sort=False)

    def _sort_table(table: pd.DataFrame) -> pd.DataFrame:
        if table.empty:
            return table

        table = table.copy()
        table["_rank"] = table["Category"].map(lambda value: 2 if value == "Flag" else (1 if value == "Others" else 0))
        table["_source_sort"] = table["Source"].fillna("").astype(str)
        table = table.sort_values(["_rank", "Category", "_source_sort"], kind="stable").drop(columns=["_rank", "_source_sort"])
        return table.reset_index(drop=True)

    return {
        "month_keys": month_keys,
        "month_labels": month_labels,
        "credit_count": _sort_table(credit_count),
        "debit_count": _sort_table(debit_count),
        "credit_amount": _sort_table(credit_amount),
        "debit_amount": _sort_table(debit_amount),
    }
