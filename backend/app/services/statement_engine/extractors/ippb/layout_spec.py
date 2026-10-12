"""India Post Payments Bank layout ("Date | Tran ID | Transaction | Particulars | Withdrwal(sic) |
Deposit | Balance" + trailing Cr/Dr marker word). Dates dd-mm-yyyy; the withdrawal title is misspelt
"WITHDRWAL" in the export; balance carries a separate trailing Cr/Dr word; an undated "Opening Balance"
line prints the opening figure in the balance column. Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

IPPB_LAYOUT_1 = LayoutSpec(
    layout_id="ippb_date_tranid_transaction_particulars_withdrwal_deposit_balance",
    bank_key="ippb",
    bank_markers=("INDIAPOSTPAYMENTSBANK", "IPPB"),
    bank_name="India Post Payments Bank",
    columns={
        "date": (("date",),),
        "ref": (("tran", "id"), ("tranid",), ("transaction", "id")),
        "narration": (("transaction", "particulars"), ("transactionparticulars",), ("particulars",)),
        "debit": (("withdrwal",), ("withdrawal",), ("withdrawals",)),
        "credit": (("deposit",), ("deposits",)),
        "balance": (("balance",),),
    },
    text_columns=("date", "ref", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]*\.\d{2}$"),
    period_re=re.compile(r"(?i)period\s*:\s*(\d{2}-[A-Za-z]{3}-\d{4})to(\d{2}-[A-Za-z]{3}-\d{4})"),
    period_date_format="%d-%b-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    opening_balance_re=re.compile(r"(?i)OpeningBalance(-?[\d,]*\.\d{2})"),
    anchor_full=True,
    date_left_pad=10.0,
)
IPPB_LAYOUT_1.validate()
