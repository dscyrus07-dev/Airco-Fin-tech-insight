"""Karnataka Bank layout configuration (fingerprint "date | particulars | instrument no | withdrawals | deposits | balance";
printed "Opening Balance" line above the table, period "between dd-mm-yyyy and dd-mm-yyyy"). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

KARNATAKA_LAYOUT_1 = LayoutSpec(
    layout_id="karnataka_date_particulars_instrumentno_withdrawals_deposits_balance",
    bank_key="karnataka",
    bank_markers=("KARNATAKABANK",),
    merge_statements=True,
    bank_name="Karnataka Bank",
    columns={
        "date": (("date",),),
        "narration": (("particulars",),),
        "ref": (("instrument", "no"), ("instrumentno",)),
        "debit": (("withdrawals",), ("withdrawal",)),
        "credit": (("deposits",), ("deposit",)),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(\d{2}-\d{2}-\d{4})and(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    opening_balance_re=re.compile(r"OpeningBalance:?([\d,]+\.\d{2})"),
    header_repeats=True,
    row_order="auto",
    dates_monotonic_expected=False,
)
KARNATAKA_LAYOUT_1.validate()
