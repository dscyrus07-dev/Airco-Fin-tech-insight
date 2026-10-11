"""DCB Bank layout ("Date* | Transaction Details | Cheque Number | Withdrawals | Deposits | Balance").
Dates are dd-mm-yyyy; money cells carry leading padding spaces; an undated "Opening Balance" line
prints the opening figure in the balance column; the statement period prints as
"Statement Period dd-mm-yyyy to dd-mm-yyyy" on the account-header line. Brand "DCB Bank" prints.
Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

DCB_LAYOUT_1 = LayoutSpec(
    layout_id="dcb_date_transactiondetails_chequenumber_withdrawals_deposits_balance",
    bank_key="dcb",
    bank_name="DCB Bank",
    bank_markers=("DCBBANK",),
    columns={
        "date": (("date",),),
        "narration": (("transactiondetails",),),
        "cheque": (("cheque",), ("chequenumber",)),
        "withdrawals": (("withdrawals",),),
        "deposits": (("deposits",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "cheque"),
    debit_column="withdrawals",
    credit_column="deposits",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^[+-]?\s?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(?i)statementperiod(\d{8})to(\d{8})"),
    period_date_format="%d%m%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    left_aligned_amounts=True,
    amount_sign_gap=True,
    continuation_start="top",
    opening_balance_re=re.compile(r"(?i)OpeningBalance(-?[\d,]+(?:\.\d{1,2})?)"),
    closing_balance_re=re.compile(r"(?i)ClosingBalance(-?[\d,]+(?:\.\d{1,2})?)"),
    anchor_full=True,
    opening_row_balance_only=True,
    row_order="auto",
)
DCB_LAYOUT_1.validate()
