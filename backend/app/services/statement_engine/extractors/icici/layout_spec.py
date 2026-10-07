"""ICICI Bank layout configuration (fingerprint "s no | value date | transaction date | cheque number | transaction remarks |
withdrawal amount (INR) | deposit amount (INR) | balance (INR)"; both money cells always print, a zero marks the empty side).
Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

ICICI_LAYOUT_1 = LayoutSpec(
    layout_id="icici_sno_valuedate_transactiondate_chequenumber_remarks_withdrawal_deposit_balance",
    bank_key="icici",
    bank_markers=("ICICIBANK",),
    merge_statements=True,
    bank_name="ICICI Bank",
    columns={
        "date": (("transactiondate",), ("transaction", "date")),
        "ref": (("chequenumber",), ("cheque", "number")),
        "narration": (("transactionremarks",), ("transaction", "remarks")),
        "debit": (("withdrawalamount",), ("withdrawal", "amount")),
        "credit": (("depositamount",), ("deposit", "amount")),
        "balance": (("balanceinr",), ("balance", "inr"), ("balance",)),
    },
    text_columns=("date", "ref", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{1,2}$"),
    period_re=re.compile(r"^NOPERIOD(\d)(\d)$"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    zero_amount_is_empty=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
ICICI_LAYOUT_1.validate()

ICICI_LAYOUT_2 = LayoutSpec(     # older ICICI layout (previously mis-filed under Canara): "date | mode | particulars | deposits | withdrawals | balance" with a dated B/F opening row
    layout_id="icici_date_mode_particulars_deposits_withdrawals_balance",
    bank_key="icici",
    bank_markers=("ICICIBANK",),
    merge_statements=True,
    bank_name="ICICI Bank",
    columns={
        "date": (("date",),),
        "mode": (("mode",),),
        "narration": (("particulars",),),
        "deposits": (("deposits",),),
        "withdrawals": (("withdrawals",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "mode", "narration"),
    debit_column="withdrawals",
    credit_column="deposits",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"theperiod([A-Za-z]+\d{2},\d{4})-([A-Za-z]+\d{2},\d{4})"),
    period_date_format="%B%d,%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    dates_monotonic_expected=False,
    period_tolerance_days=3,
    side_flip_policy="review",
    end_markers=("ENDOFSTATEMENT",),
    header_repeats=True,
    opening_row_marker="B/F",
)
ICICI_LAYOUT_2.validate()
