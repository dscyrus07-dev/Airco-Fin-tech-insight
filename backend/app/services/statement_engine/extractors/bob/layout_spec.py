"""Bank of Baroda layout configuration (fingerprint "serial no | transaction date | value date | description | cheque
number | debit | credit | balance"; "-" prints in the empty money column). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

BOB_LAYOUT_1 = LayoutSpec(
    layout_id="bob_serial_transactiondate_valuedate_description_cheque_debit_credit_balance",
    bank_key="bob",
    bank_markers=("BANKOFBARODA",),
    merge_statements=True,
    bank_name="Bank of Baroda",
    columns={
        "date": (("transaction",),),
        "value_date": (("value",),),
        "narration": (("description",),),
        "ref": (("cheque",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"Statementfrom(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    secondary_date_column="value_date",
    header_repeats=True,
    opening_row_marker="OPENINGBALANCE",
    page_footer_markers=("NOTE:INCASEYOU",),
    ignore_line_res=(re.compile(r"^-$"),),
)
BOB_LAYOUT_1.validate()

BOB_LAYOUT_2 = LayoutSpec(     # "date | narration | chq.no. | withdrawal (dr) | deposit (cr) | balance cr/dr"
    layout_id="bob_date_narration_chqno_withdrawaldr_depositcr_balance",
    bank_key="bob",
    bank_markers=("BANKOFBARODA",),
    merge_statements=True,
    bank_name="Bank of Baroda",
    columns={
        "date": (("date",),),
        "narration": (("narration",),),
        "ref": (("chqno",), ("chq", "no")),
        "debit": (("withdrawal", "dr"), ("withdrawaldr",)),
        "credit": (("deposit", "cr"), ("depositcr",)),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?: ?(?:Cr|Dr))?$"),
    period_re=re.compile(r"Periodfrom([A-Za-z]{3}\d{2},\d{4})to([A-Za-z]{3}\d{2},\d{4})"),
    period_date_format="%b%d,%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    opening_row_marker="OPENINGBALANCE",
    closing_row_marker="CLOSINGBALANCE",
    merge_drcr_suffix=True,
    continuation_start="top",
)
BOB_LAYOUT_2.validate()

BOB_LAYOUT_3 = LayoutSpec(     # fixed-pitch text pages: "date | particulars | chq.no. | withdrawals | deposits | balance"
    layout_id="bob_date_particulars_chqno_withdrawals_deposits_balance",
    bank_key="bob",
    bank_markers=("BANKOFBARODA",),
    merge_statements=True,
    monospace_text=True,
    bank_name="Bank of Baroda",
    columns={
        "date": (("date",),),
        "narration": (("particulars",),),
        "ref": (("chq.no.",), ("chqno",), ("chq", "no")),
        "debit": (("withdrawals",),),
        "credit": (("deposits",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{2}$"),
    date_format="%d-%m-%y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?: ?(?:Cr|Dr))?$"),
    period_re=re.compile(r"(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    merge_drcr_suffix=True,
    opening_row_balance_only=True,
    page_break_re=re.compile(r"^PageTotal:"),
    ignore_line_res=(re.compile(r"^-{10,}$"),),
)
BOB_LAYOUT_3.validate()
