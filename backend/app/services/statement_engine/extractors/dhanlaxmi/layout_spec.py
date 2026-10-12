"""Dhanlaxmi Bank layout ("Date | Value Date | Description | Cheque No | Debits | Credits | Balance").
Dates dd-MMM-yyyy upper-case; right-aligned debit/credit columns; statement period prints as
"Period : dd-Mon-yyyy To dd-Mon-yyyy". Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

DHANLAXMI_LAYOUT_1 = LayoutSpec(
    layout_id="dhanlaxmi_date_valuedate_description_chequeno_debits_credits_balance",
    bank_key="dhanlaxmi",
    bank_markers=("DHANLAXMIBANK", "DHANBANK"),
    bank_name="Dhanlaxmi Bank",
    columns={
        "date": (("date",),),
        "value_date": (("value", "date"), ("valuedate",)),
        "narration": (("description",),),
        "ref": (("cheque", "no"), ("chequeno",), ("sr", "no")),
        "debit": (("debits",), ("debit",)),
        "credit": (("credits",), ("credit",)),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "narration", "ref"),
    secondary_date_column="value_date",
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$"),
    date_format="%d-%b-%Y",
    amount_re=re.compile(r"^-?[\d,]*\.\d{2}$"),
    zero_amount_is_empty=True,
    period_re=re.compile(r"(?i)period\s*:?\s*(\d{2}-[A-Za-z]{3}-\d{4})to(\d{2}-[A-Za-z]{3}-\d{4})"),
    period_date_format="%d-%b-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    opening_balance_re=re.compile(r"(?i)OpeningBalance(-?[\d,]*\.\d{2})"),
    closing_balance_re=re.compile(r"(?i)ClosingBalance(-?[\d,]*\.\d{2})"),
    anchor_full=True,
    date_left_pad=10.0,
)
DHANLAXMI_LAYOUT_1.validate()
