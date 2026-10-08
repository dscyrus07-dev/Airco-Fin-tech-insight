"""Citibank layout configuration (fingerprint "date | transaction details | withdrawals | deposits | balance";
e-statement, "Opening Balance: n" and "For the period dd-mm-yyyy to dd-mm-yyyy" above the table, "-" in an empty money
cell, narration wraps, header repeats each page). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

CITIBANK_LAYOUT_1 = LayoutSpec(
    layout_id="citibank_date_transactiondetails_withdrawals_deposits_balance",
    bank_key="citibank",
    bank_markers=("CITIBANK",),
    bank_name="Citibank",
    columns={
        "date": (("date",),),
        "narration": (("transaction", "details"), ("transactiondetails",)),
        "debit": (("withdrawals",), ("withdrawals", "inr")),
        "credit": (("deposits",), ("deposits", "inr")),
        "balance": (("balance",), ("balance", "inr")),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(?i)fortheperiod(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    opening_balance_re=re.compile(r"(?i)openingbalance:?([\d,]+\.\d{2})"),
    header_repeats=True,
    continuation_start="top",
    empty_amount_marker="-",
    dates_monotonic_expected=False,
)
CITIBANK_LAYOUT_1.validate()
