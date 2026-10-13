"""Punjab National Bank layout ("Date | Instrument Id | Amount | Type | Balance | Remarks" — single amount column with
the Dr/Cr marker printed in its own "Type" column; brand never appears in the text layer so routing relies on the
detector). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

PNB_LAYOUT_1 = LayoutSpec(
    layout_id="pnb_date_instrumentid_amount_type_balance_remarks",
    bank_key="pnb",
    bank_markers=(),
    merge_statements=True,
    bank_name="Punjab National Bank",
    columns={
        "date": (("date",),),
        "instid": (("instrumentid",), ("instrument", "id")),
        "type": (("type",),),
        "narration": (("remarks",),),
        "amount": (("amount",), ("amountinr",)),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    single_amount_column="amount",
    side_marker_column="narration",
    date_re=re.compile(r"^\d{2}[/\-]\d{2}[/\-]\d{4}$"),
    date_format="%d/%m/%Y|%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+(?:\.\d{1,2})?$"),
    period_re=re.compile(r"(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=False,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
)
PNB_LAYOUT_1.validate()
