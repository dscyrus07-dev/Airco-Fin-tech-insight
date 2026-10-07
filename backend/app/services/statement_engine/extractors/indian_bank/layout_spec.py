"""Indian Bank layout configuration (fingerprint "transaction date | particulars | withdrawals | deposit | balance"; the
date title wraps over two lines, an empty money cell prints "-", balances carry a Cr/Dr suffix). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

INDIAN_BANK_LAYOUT_1 = LayoutSpec(
    layout_id="indianbank_transactiondate_particulars_withdrawals_deposit_balance",
    bank_key="indian_bank",
    bank_markers=("INDIANBANK",),
    merge_statements=True,
    bank_name="Indian Bank",
    columns={
        "date": (("transaction",), ("transactiondate",)),
        "narration": (("particulars",),),
        "debit": (("withdrawals",), ("withdrawal",)),
        "credit": (("deposit",), ("deposits",)),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?:[Cc][Rr]|[Dd][Rr])?$"),
    empty_amount_marker="-",
    period_re=re.compile(r"StatementPeriod:From(\d{2}/\d{2}/\d{4})To(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    row_order="auto",
    dates_monotonic_expected=False,
)
INDIAN_BANK_LAYOUT_1.validate()
