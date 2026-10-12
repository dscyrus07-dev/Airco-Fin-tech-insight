"""UCO Bank layouts ("Date | Particulars | Instrument No | Withdrawals | Deposits | Balance" and the
variant without the instrument column). Dates dd-mm-yyyy; right-aligned separate debit/credit columns;
the A family prints no opening anchor (self-derived chain -> REVIEW ceiling), the B family prints an
"Opening Balance" line. Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

UCO_LAYOUT_1 = LayoutSpec(
    layout_id="uco_date_particulars_instrumentno_withdrawals_deposits_balance",
    bank_key="uco",
    bank_markers=("UCOBANK",),
    bank_name="UCO Bank",
    columns={
        "date": (("date",),),
        "narration": (("particulars",),),
        "ref": (("instrument", "no"), ("instrumentno",), ("instrument",)),
        "debit": (("withdrawals",),),
        "credit": (("deposits",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]*\.\d{2}$"),
    period_re=re.compile(r"(?i)(\d{2}-\d{2}-\d{4})and(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    opening_balance_re=re.compile(r"(?i)OpeningBalance(-?[\d,]*\.\d{2})"),
    anchor_full=True,
    date_left_pad=10.0,
)
UCO_LAYOUT_1.validate()

UCO_LAYOUT_2 = LayoutSpec(
    layout_id="uco_date_particulars_withdrawals_deposits_balance",
    bank_key="uco",
    bank_markers=("UCOBANK",),
    bank_name="UCO Bank",
    columns={
        "date": (("date",),),
        "narration": (("particulars",),),
        "debit": (("withdrawals",),),
        "credit": (("deposits",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]*\.\d{2}$"),
    period_re=re.compile(r"(?i)(\d{2}-\d{2}-\d{4})and(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    opening_balance_re=re.compile(r"(?i)OpeningBalance(-?[\d,]*\.\d{2})"),
    anchor_full=True,
    date_left_pad=10.0,
)
UCO_LAYOUT_2.validate()
