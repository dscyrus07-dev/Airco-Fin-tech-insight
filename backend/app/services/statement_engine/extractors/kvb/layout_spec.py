"""Karur Vysya Bank layout (header "Txn | Value | Brn | Particulars | RefNo | Debit | Credit | Balance" with the second
line "Date Date Code"; summary block printed above the table; first row is the balance-only carry-forward; period line
"Statement Duration : dd/mm/yyyy to dd/mm/yyyy"). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

KVB_LAYOUT_1 = LayoutSpec(
    layout_id="kvb_txn_value_brn_particulars_refno_debit_credit_balance",
    bank_key="kvb",
    bank_markers=("KARURVYSYABANK",),
    bank_name="Karur Vysya Bank",
    columns={
        "date": (("txn",),),
        "value_date": (("value",),),
        "branch": (("brn",),),
        "narration": (("particulars",),),
        "ref": (("refno",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "branch", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(?i)(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    secondary_date_column="value_date",
    header_repeats=True,
    opening_row_balance_only=True,
    band_left_pad={"date": 10.0, "narration": 60.0},
    dates_monotonic_expected=False,
)
KVB_LAYOUT_1.validate()
