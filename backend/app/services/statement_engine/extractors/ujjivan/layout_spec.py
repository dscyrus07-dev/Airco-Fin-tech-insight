"""Ujjivan Small Finance Bank layout ("Date | Particular | Chq Ref No | Withdrawal | Deposit | Balance
Amount"). Dates are dd-mm-yy; narration is a fused token that wraps into continuation lines; the period
line reads "Statement of Account from MonthDDYYYYtoMonthDDYYYY"; brand "Ujjivan Small Finance Bank"
prints in the closing-page footer. Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

UJJIVAN_LAYOUT_1 = LayoutSpec(
    layout_id="ujjivan_date_particular_chqrefno_withdrawal_deposit_balanceamount",
    bank_key="ujjivan_sfb",
    bank_name="Ujjivan Small Finance Bank",
    bank_markers=("UJJIVANSMALLFINANCEBANK",),
    columns={
        "date": (("date",),),
        "narration": (("particular",),),
        "ref": (("chqrefno",),),
        "debit": (("withdrawal",),),
        "credit": (("deposit",),),
        "balance": (("balanceamount",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{2}$"),
    date_format="%d-%m-%y",
    amount_re=re.compile(r"^-?[\d,]+(?:\.\d{2})?$"),
    period_re=re.compile(r"from([A-Za-z]+\d{2}\d{4})to([A-Za-z]+\d{2}\d{4})"),
    period_date_format="%B%d%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    merge_statements=True,
    row_order="auto",
)
UJJIVAN_LAYOUT_1.validate()
