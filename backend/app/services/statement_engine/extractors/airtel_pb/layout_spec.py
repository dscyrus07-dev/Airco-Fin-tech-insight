"""Airtel Payments Bank statement layout ("Date | Transaction Type | Particulars | Withdrawal | Deposit |
Balance"). Dates dd-mm-yyyy; transaction-type keywords print inside the narration band on wrap lines;
header repeats per page; opening/closing balances print in an account-summary block. Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

AIRTEL_LAYOUT_1 = LayoutSpec(
    layout_id="airtelpb_date_transactiontype_particulars_withdrawal_deposit_balance",
    bank_key="airtel_pb",
    bank_markers=("AIRTELPAYMENTSBANK",),
    bank_name="Airtel Payments Bank",
    columns={
        "date": (("date",),),
        "ref": (("transaction", "id"), ("transactionid",)),
        "narration": (("particulars",),),
        "debit": (("withdrawal",), ("withdrawals",)),
        "credit": (("deposit",), ("deposits",)),
        "balance": (("balance",),),
    },
    text_columns=("date", "ref", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]*\.\d{2}$"),
    period_re=re.compile(r"(?i)period.*?(\d{2}-\d{2}-\d{4}).*?(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    opening_balance_re=re.compile(r"(?i)OpeningBalance(-?[\d,]*\.\d{2})"),
    closing_balance_re=re.compile(r"(?i)ClosingBalance(-?[\d,]*\.\d{2})"),
    anchor_full=True,
    date_left_pad=8.0,
)
AIRTEL_LAYOUT_1.validate()
