"""South Indian Bank layout ("Date | Particulars | Chq.No. | Withdrawals | Deposits | Balance" — the same
fixed-pitch header Bank of Baroda layout 3 prints; SIB dates are `dd-mm-yy` and the balance carries a Cr/Dr
suffix word). The brand never prints in the text layer -> routing relies on the detector. Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

SIB_LAYOUT_1 = LayoutSpec(
    layout_id="south_indian_date_particulars_chqno_withdrawals_deposits_balance",
    bank_key="south_indian",
    bank_name="South Indian Bank",
    bank_markers=("SOUTHINDIANBANK",),
    merge_statements=True,
    monospace_text=True,
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
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?: ?\(?[Cc][Rr]\)?\.?| ?\(?[Dd][Rr]\)?\.?)?$"),
    period_re=re.compile(r"(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    merge_drcr_suffix=True,
    continuation_amounts=True,
    opening_row_balance_only=True,
    page_break_re=re.compile(r"^PageTotal:"),
    ignore_line_res=(re.compile(r"^-{10,}$"),),
)
SIB_LAYOUT_1.validate()
