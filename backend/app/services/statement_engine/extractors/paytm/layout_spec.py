"""Paytm Payments Bank layout configuration (fingerprint "date & time | transaction details | amount | available
balance"): one amount column printed "+ Rs.2,318.00" / "- Rs.100.00", balance "Rs.2,399.56". Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

PAYTM_LAYOUT_1 = LayoutSpec(
    layout_id="paytm_datetime_transactiondetails_amount_availablebalance",
    bank_key="paytm",
    merge_statements=True,
    bank_name="Paytm Payments Bank",
    columns={
        "date": (("datetime",), ("date", "time")),
        "narration": (("transaction", "details"), ("transactiondetails",)),
        "amount": (("amount",),),
        "balance": (("available", "balance"), ("availablebalance",)),
    },
    text_columns=("date", "narration"),
    debit_column="amount_dr",
    credit_column="amount_cr",
    single_amount_column="amount",
    balance_column="balance",
    amount_prefix="Rs.|₹",
    merge_sign_prefix=True,
    date_re=re.compile(r"^\d{1,2} [A-Za-z]{3} \d{4}$"),
    date_format="%d %b %Y",
    amount_re=re.compile(r"^[+-]?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"^NOPERIOD(\d)(\d)$"),
    period_date_format="%d %b %Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    end_markers=("^ACTIVEFIXEDDEPOSITS",),
    dated_rows_after_end_ok=True,
    header_repeats=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
PAYTM_LAYOUT_1.validate()
