"""Yes Bank layouts. L1: "Transaction | Value Date | Cheque No/Reference No | Description | Withdrawals |
Deposits | Running Balance" (the "Date" half of the first title prints on the next line). The brand never
prints as a standalone token (only inside IFSC codes / narration strings) -> routing relies on the detector.
Dates are `dd Mmm yyyy`, `dd/mm/yyyy`, or `dd-Mmm-yyyy`. Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

YES_LAYOUT_1 = LayoutSpec(
    layout_id="yes_transaction_valuedate_chequenoreferenceno_description_withdrawals_deposits_runningbalance",
    bank_key="yes",
    bank_name="Yes Bank",
    bank_markers=(),
    merge_statements=True,
    columns={
        "date": (("transaction", "date"), ("transaction",), ("transactiondate",)),
        "value_date": (("value", "date"), ("valuedate",)),
        "ref": (("chequenoreferenceno",), ("cheque", "no", "reference", "no"), ("chequeno", "referenceno"), ("cheque",), ("chequeno",), ("cheque", "no")),
        "narration": (("description",),),
        "debit": (("withdrawals",),),
        "credit": (("deposits",),),
        "balance": (("running", "balance"), ("runningbalance",), ("balance",)),
    },
    text_columns=("date", "value_date", "ref", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    secondary_date_column="value_date",
    date_re=re.compile(r"^\d{2} [A-Za-z]{3} \d{4}$|^\d{2}/\d{2}/\d{4}$|^\d{2}-[A-Za-z]{3}-\d{4}$"),
    date_format="%d %b %Y|%d/%m/%Y|%d-%b-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
)
YES_LAYOUT_1.validate()
