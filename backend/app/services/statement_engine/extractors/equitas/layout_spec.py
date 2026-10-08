"""Equitas Small Finance Bank layout ("Date | Reference No/Cheque No | Narration | Withdrawal | Deposit |
Closing Balance" with an "INR" sub-label line under the money columns). Dates are ISO yyyy-mm-dd; the
narration column wraps into single-word continuation lines; the statement period line reads
"Statement for the period from dd-Mmm-yyyy to dd-Mmm-yyyy"; the table ends at "END OF THE STATEMENT".
Brand "EQUITAS SMALL FINANCE BANK LIMITED" prints in the page footer. Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

EQUITAS_LAYOUT_1 = LayoutSpec(
    layout_id="equitas_date_referencenochequeno_narration_withdrawal_deposit_closingbalance",
    bank_key="equitas_sfb",
    bank_name="Equitas Small Finance Bank",
    bank_markers=("EQUITASSMALLFINANCEBANK",),
    columns={
        "date": (("date",),),
        "ref": (("referencenochequeno",),),
        "narration": (("narration",),),
        "debit": (("withdrawal",),),
        "credit": (("deposit",),),
        "balance": (("closingbalance",),),
    },
    text_columns=("date", "ref", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{4}-\d{2}-\d{2}$|^\d{2}-[A-Za-z]{3}-\d{4}$"),
    date_format="%Y-%m-%d|%d-%b-%Y",
    amount_re=re.compile(r"^-?[\d,]+(?:\.\d{2})?$"),
    period_re=re.compile(r"(\d{2}-[A-Za-z]{3}-\d{4})to(\d{2}-[A-Za-z]{3}-\d{4})"),
    period_date_format="%d-%b-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    merge_statements=True,
    end_markers=("ENDOFTHESTATEMENT",),
    continuation_start="top",
    row_order="auto",
)
EQUITAS_LAYOUT_1.validate()
