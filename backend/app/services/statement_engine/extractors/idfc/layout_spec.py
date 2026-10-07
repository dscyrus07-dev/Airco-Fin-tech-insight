"""IDFC First Bank layout configuration (dominant fingerprint "transaction date | value date | particulars | cheque no |
debit | credit | balance"). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

IDFC_LAYOUT_1 = LayoutSpec(
    layout_id="idfc_transactiondate_valuedate_particulars_cheque_debit_credit_balance",
    bank_key="idfc",
    bank_markers=("IDFCFIRST",),
    merge_statements=True,
    bank_name="IDFC First Bank",
    columns={
        "date": (("transactiondate",), ("transaction", "date"), ("transaction",)),
        "value_date": (("valuedate",), ("value", "date")),
        "narration": (("particulars",),),
        "ref": (("chequeno",), ("cheque", "no"), ("cheque",)),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref", "value_date"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$"),
    date_format="%d-%b-%Y",
    amount_re=re.compile(r"^(?:-?[\d,]*\.\d{2}|\(-?[\d,]*\.\d{2}\))$"),
    period_re=re.compile(r"STATEMENTPERIOD:(\d{4}-\d{2}-\d{2})TO(\d{4}-\d{2}-\d{2})"),
    period_date_format="%Y-%m-%d",
    summary_marker="",
    summary_label_text="openingbalancetotaldebittotalcreditclosingbalance",
    summary_fields=("opening", "debits", "credits", "closing"),
    secondary_date_column="value_date",
    summary_position="before",
    header_repeats=True,
    opening_balance_re=re.compile(r"^OpeningBalance(-?[\d,]*\.\d{2})$"),
    ignore_line_res=(re.compile(r"^[Pp]age\d+of\d+$"),),
)
IDFC_LAYOUT_1.validate()
