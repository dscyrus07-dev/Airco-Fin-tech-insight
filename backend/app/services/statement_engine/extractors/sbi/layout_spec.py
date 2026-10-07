"""SBI layout configuration (layout family F1, dominant fingerprint "txn date | value date | description | ref no./cheque |
debit | credit | balance"). Facts only; the machinery lives in statement_engine.extraction."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

SBI_TXN_VALUE_DESC_REF_DR_CR_BAL_ID = "sbi_txndate_valuedate_description_refcheque_debit_credit_balance"

SBI_LAYOUT_1 = LayoutSpec(
    layout_id=SBI_TXN_VALUE_DESC_REF_DR_CR_BAL_ID,
    bank_key="sbi",
    bank_name="State Bank of India",
    columns={
        "date": (("txndate",),),
        "value_date": (("value",),),            # "Value" / "Date" print on two lines; the first line carries "Value"
        "narration": (("description",),),
        "ref": (("refnocheque",), ("refno", "cheque")),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{1,2} [A-Za-z]{3}(?: \d{4})?$"),       # "5 Jan 2023" or, when the cell wraps, "10 Jan"
    date_tail_re=re.compile(r"^\d{4}$"),                           # ... and the year on the next line
    date_format="%d %b %Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"AccountStatementfrom(\d{1,2}[A-Za-z]{3}\d{4})to(\d{1,2}[A-Za-z]{3}\d{4})"),
    period_date_format="%d%b%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    end_markers=("PLEASEDONOTSHAREYOURATM", "THISISACOMPUTERGENERATEDSTATEMENT"),
    secondary_date_column="value_date",
    header_repeats=True,
    opening_balance_re=re.compile(r"Balanceason\d{1,2}[A-Za-z]{3}\d{4}:(?:\(cid:\d+\))?(-?[\d,]+\.\d{2})"),
    account_label="accountnumber",
)
SBI_LAYOUT_1.validate()
