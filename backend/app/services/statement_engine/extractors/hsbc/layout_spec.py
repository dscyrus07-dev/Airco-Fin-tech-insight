"""HSBC layout ("Date | Description | Credit | Debit | Balance" — credit column before debit; "Date Range:
dd/mm/yyyy - dd/mm/yyyy" above the table; narration wraps under the description column). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

HSBC_LAYOUT_1 = LayoutSpec(
    layout_id="hsbc_date_description_credit_debit_balance",
    bank_key="hsbc",
    bank_markers=("HSBC",),
    bank_name="HSBC",
    columns={
        "date": (("date",),),
        "narration": (("description",),),
        "credit": (("credit",),),
        "debit": (("debit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(?i)daterange:?(\d{2}/\d{2}/\d{4})-(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
)
HSBC_LAYOUT_1.validate()
