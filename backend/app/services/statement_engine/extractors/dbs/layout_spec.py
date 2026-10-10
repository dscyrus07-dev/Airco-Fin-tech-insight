"""DBS Bank layout configuration (fingerprint "transaction date | value date | details of transaction | debit | credit |
balance"; e-statement, opening "Opening Balance" row, "Statement Period: dd-Mon-yyyy to dd-Mon-yyyy" above the table,
"***End of Statement***" footer, header repeats each page). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

DBS_LAYOUT_1 = LayoutSpec(
    layout_id="dbs_transactiondate_valuedate_detailsoftransaction_debit_credit_balance",
    bank_key="dbs",
    bank_markers=("DBSBANK",),
    bank_name="DBS Bank",
    columns={
        "date": (("transaction", "date"), ("transactiondate",)),
        "value_date": (("value", "date"), ("valuedate",)),
        "narration": (("details", "of", "transaction"), ("detailsoftransaction",)),
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
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(?i)statementperiod:?(\d{2}-[a-z]{3}-\d{4})to(\d{2}-[a-z]{3}-\d{4})"),
    period_date_format="%d-%b-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    secondary_date_column="value_date",
    header_repeats=True,
    opening_row_marker="OPENINGBALANCE",
    closing_balance_re=re.compile(r"(?i)^closingbalance:?(-?[\d,]+\.\d{2})$"),
    anchor_full=True,
    end_markers=("***ENDOFSTATEMENT",),
    account_label="ACCOUNTNO",
    merge_statements=True,
    row_order="auto",
    dates_monotonic_expected=False,
)
DBS_LAYOUT_1.validate()
