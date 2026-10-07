"""Canara Bank layout configuration (family F1, dominant fingerprint "date | particulars | deposits | withdrawals |
balance"; credit column printed BEFORE the debit column). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

CANARA_DEP_WD_BAL_ID = "canara_date_particulars_deposits_withdrawals_balance"

CANARA_LAYOUT_1 = LayoutSpec(
    layout_id=CANARA_DEP_WD_BAL_ID,
    bank_key="canara",
    bank_name="Canara Bank",
    columns={
        "date": (("date",),),
        "narration": (("particulars",),),
        "deposits": (("deposits",),),
        "withdrawals": (("withdrawals",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="withdrawals",
    credit_column="deposits",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(?:fortheperiod|between)(\d{2}-[A-Za-z]{3}-\d{4})(?:to|and)(\d{2}-[A-Za-z]{3}-\d{4})"),
    period_date_format="%d-%b-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    dates_monotonic_expected=False,
    period_tolerance_days=3,
    side_flip_policy="review",
    end_markers=("ENDOFSTATEMENT",),
    header_repeats=True,
    opening_balance_re=re.compile(r"OpeningBalance(-?[\d,]+\.\d{2})"),
    closing_balance_re=re.compile(r"^ClosingBalance(-?[\d,]+\.\d{2})$"),
    ignore_line_res=(re.compile(r"^[Pp]age\d+$"),),
)
CANARA_LAYOUT_1.validate()
