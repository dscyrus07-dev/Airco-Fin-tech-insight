"""Union Bank of India layout configuration (fingerprint "s.no | date | transaction id | remarks | amount (rs.) |
balance (rs.)"): ONE amount column whose cells end in (Dr)/(Cr), balance carries (Cr)/(Dr), newest transaction first.
Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

UNION_LAYOUT_1 = LayoutSpec(
    layout_id="union_sno_date_transactionid_remarks_amount_balance",
    bank_key="union",
    bank_markers=("UNIONBANKOFINDIA",),
    merge_statements=True,
    bank_name="Union Bank of India",
    columns={
        "date": (("date",),),
        "ref": (("transactionid",), ("transaction", "id")),
        "narration": (("remarks",),),
        "amount": (("amountrs",), ("amount",)),
        "balance": (("balancers",), ("balance",)),
    },
    text_columns=("date", "ref", "narration"),
    band_left_pad={"narration": 90.0},
    debit_column="amount_dr",
    credit_column="amount_cr",
    single_amount_column="amount",
    balance_column="balance",
    row_order="reverse",
    merge_drcr_suffix=True,
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?: ?\((?:Cr|Dr)\))?$"),
    period_re=re.compile(r"StatementPeriod(\d{2}/\d{2}/\d{4})To(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
)
UNION_LAYOUT_1.validate()
