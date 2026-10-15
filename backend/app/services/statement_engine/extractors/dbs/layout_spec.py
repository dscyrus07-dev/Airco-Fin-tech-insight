"""DBS Bank layout configuration (fingerprint "transaction date | value date | details of transaction | debit | credit |
balance"; e-statement, opening "Opening Balance" row, "Statement Period: dd-Mon-yyyy to dd-Mon-yyyy" above the table,
"***End of Statement***" footer, header repeats each page). Facts only."""
from __future__ import annotations

import re

from dataclasses import replace

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
    opening_balance_re=re.compile(r"(?i)openingbalance:?(-?[\d,]+\.\d{2})"),
    closing_balance_re=re.compile(r"(?i)^closingbalance:?(-?[\d,]+\.\d{2})$"),
    anchor_full=True,
    end_markers=("***ENDOFSTATEMENT",),
    account_label="ACCOUNTNO",
    segment_header_re=re.compile(r"(?i)accountno\.?\s*:"),   # multi-account exports reprint the account block
    anchor_scan="document",                                   # per-segment openings/closings scan the whole doc
    merge_statements=True,
    row_order="auto",
    dates_monotonic_expected=False,
)
DBS_LAYOUT_1.validate()

DBS_LAYOUT_2 = LayoutSpec(
    layout_id="dbs_transactiondate_valuedate_branchcode_description_chequereferencenumber_debit_credit_balance",
    bank_key="dbs",
    bank_markers=("DBSBANK",),
    bank_name="DBS Bank",
    columns={
        "date": (("transaction", "date"), ("transactiondate",)),
        "value_date": (("value", "date"), ("valuedate",)),
        "branch_code": (("branch", "code"), ("branchcode",)),
        "narration": (("description",),),
        "ref": (("chequereference", "number"), ("chequereference",), ("chequereferencenumber",)),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "branch_code", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(?i)periodfrom:?(\d{2}/\d{2}/\d{4})to:?(\d{2}/\d{2}/\d{4})"),   # prints as two separate
    period_date_format="%d/%m/%Y",                                                      # lines -> stays unmatched
    summary_marker="^SUMMARY",
    summary_label_text="",
    summary_expected=False,
    secondary_date_column="value_date",
    header_repeats=True,
    header_wraps=True,
    opening_balance_re=re.compile(r"(?i)openingbalance[^0-9]*?INR(-?[\d,]+\.\d{2})"),
    closing_balance_re=re.compile(r"(?i)closingbalance[^0-9]*?INR(-?[\d,]+\.\d{2})"),
    anchor_full=True,
    end_markers=("***ENDOFSTATEMENT",),
    account_label="ACCOUNTNUMBER",
    row_order="auto",
    dates_monotonic_expected=False,
)
DBS_LAYOUT_2.validate()

DBS_LAYOUT_3 = LayoutSpec(
    layout_id="dbs_date_detailsoftransaction_debit_credit",
    bank_key="dbs",
    bank_markers=("DBSBANK",),
    bank_name="DBS Bank",
    columns={
        "date": (("date",),),
        "narration": (("details", "of", "transaction"), ("detailsoftransaction",)),
        "debit": (("debit",),),
        "credit": (("credit",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="",
    no_running_balance=True,
    leading_narration=True,
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(?i)transactionhistory(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    page_footer_markers=("DBSBANKLTD", "PRIVATE&CONFIDENTIAL"),
    anchor_full=True,
    account_label="ACCOUNTNO",
    row_order="auto",
    dates_monotonic_expected=False,
)
DBS_LAYOUT_3.validate()


# Same balance-less "Details of Transaction" export with yearless row dates ("02 Jul"); the printed
# "Transaction History From dd-mm-yyyy To dd-mm-yyyy" line supplies the year.
DBS_LAYOUT_4 = replace(
    DBS_LAYOUT_3,
    layout_id="dbs_date_detailsoftransaction_debit_credit_yearless",
    date_re=re.compile(r"^\d{2} [A-Za-z]{3}$"),
    date_format="%d %b %Y",
    period_re=re.compile(r"(?i)transactionhistoryfrom(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"),
    year_from_period=True,
)
DBS_LAYOUT_4.validate()
