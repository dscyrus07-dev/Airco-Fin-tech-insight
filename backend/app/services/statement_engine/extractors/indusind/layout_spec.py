"""IndusInd layout ("Date | Particulars | ChqRefNo | Withdrawl | Deposit | Balance" — the debit title is printed
"Withdrawl" on some prints and "Withdrawal" on others; "Period : ddMMMyyyytoddMMMyyyy" above the table; integer-style
amounts without paise; narration wraps under particulars). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

INDUSIND_LAYOUT_1 = LayoutSpec(
    layout_id="indusind_date_particulars_chqrefno_withdrawl_deposit_balance",
    bank_key="indusind",
    bank_markers=("INDUSINDBANK",),
    bank_name="IndusInd Bank",
    columns={
        "date": (("date",),),
        "narration": (("particulars",),),
        "ref": (("chqrefno",), ("chq", "ref", "no"), ("chqref", "no")),
        "debit": (("withdrawl",), ("withdrawal",)),
        "credit": (("deposit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$"),
    date_format="%d-%b-%Y",
    amount_re=re.compile(r"^-?[\d,]+(?:\.\d{1,2})?$"),
    period_re=re.compile(r"(?i)period:?(\d{2}-?[a-z]{3}-?\d{4})to(\d{2}-?[a-z]{3}-?\d{4})"),
    period_date_format="%d-%b-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    opening_row_balance_only=True,
    closing_balance_re=re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}([\d,]+(?:\.\d{1,2})?)$"),
    header_repeats=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
INDUSIND_LAYOUT_1.validate()
