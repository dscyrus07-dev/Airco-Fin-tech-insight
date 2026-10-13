"""CSB Bank layout ("Date | Value | Transaction | Debit | Credit | Balance").
Dates dd/mm/yyyy; separate debit/credit columns; an undated "Opening Balance" line prints the opening
figure in the balance column; balance right-aligned; header repeats per page. Note: part of the corpus
folder is mislabelled Federal Bank exports which correctly route to the federal layouts. Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

CSB_LAYOUT_1 = LayoutSpec(
    layout_id="csb_date_value_transaction_debit_credit_balance",
    bank_key="csb",
    bank_markers=("CSBBANK",),
    merge_statements=True,
    bank_name="CSB Bank",
    columns={
        "date": (("date",),),
        "value_date": (("value",), ("valuedate",), ("value", "date")),
        "narration": (("transaction",), ("particulars",)),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$"),
    date_format="%d-%b-%Y",
    amount_re=re.compile(r"^-?[\d,]*\.\d{2}(?i:(?:cr|dr))?$"),
    period_re=re.compile(r"(?i)period(\d{2}[-/.]\d{2}[-/.]\d{4})to(\d{2}[-/.]\d{2}[-/.]\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    secondary_date_column="value_date",
    header_repeats=True,
    opening_balance_re=re.compile(r"(?i)OpeningBalance(-?[\d,]*\.\d{2})"),
    anchor_full=True,
    date_left_pad=10.0,
)
CSB_LAYOUT_1.validate()
