"""Axis Bank layout configuration (family F1, dominant fingerprint "tran date | chq no | particulars | debit | credit |
balance | init. br"). Header printed on page 1 only; page-1 opening balance, a TRANSACTION TOTAL line and a CLOSING BALANCE
line are printed around the table. The "Chq No" values share the narration band, so the cheque number is part of the
raw narration."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

AXIS_TRAN_CHQ_PARTICULARS_DR_CR_BAL_ID = "axis_trandate_chqno_particulars_debit_credit_balance_initbr"
_AMT = r"(-?[\d,]*\.\d{2})"

AXIS_LAYOUT_1 = LayoutSpec(
    layout_id=AXIS_TRAN_CHQ_PARTICULARS_DR_CR_BAL_ID,
    bank_key="axis",
    merge_statements=True,
    bank_name="Axis Bank",
    columns={
        "date": (("trandate",), ("tran", "date")),
        "ref": (("chqno",), ("chq", "no")),
        "narration": (("particulars",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
        "init": (("init",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]*\.\d{2}$"),
    period_re=re.compile(r"From:(\d{2}-\d{2}-\d{4})To:(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    end_markers=("++++ENDOFSTATEMENT".replace("+", ""),),
    header_repeats=False,
    continuation_start="top",
    opening_balance_re=re.compile(r"OPENINGBALANCE" + _AMT),
    closing_balance_re=re.compile(r"^CLOSINGBALANCE" + _AMT + r"$"),
    totals_line_re=re.compile(r"^TRANSACTIONTOTAL" + _AMT + _AMT + r"$"),
    account_label="accountno",
)
AXIS_LAYOUT_1.validate()
