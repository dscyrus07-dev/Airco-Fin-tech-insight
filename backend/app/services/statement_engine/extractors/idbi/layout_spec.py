"""IDBI Bank layouts. L1 shares Bank of Baroda's "Date | Particulars | Chq.No. | Withdrawals | Deposits | Balance"
header verbatim — it is claimed only on IDBI evidence (brand text or the Slice 2 detector). L2 is the e-statement
"S.No | Txn Date | Value Date | Description | Cheque No | Withdrawals(Dr) | Deposits(Cr) | Balance(INR)" with the txn
date cell carrying a time suffix. Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

IDBI_LAYOUT_1 = LayoutSpec(
    layout_id="idbi_date_particulars_chqno_withdrawals_deposits_balance",
    bank_key="idbi",
    bank_markers=("IDBIBANK",),
    merge_statements=True,
    bank_name="IDBI Bank",
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
    date_re=re.compile(r"^\d{2}[-/]\d{2}[-/]\d{4}$"),
    date_format="%d/%m/%Y|%d-%m-%Y",
    amount_re=re.compile(r"^-?(?:[\d,]+(?:\.\d{1,2})?|\.\d{1,2})(?: ?(?:Cr|Dr))?$"),
    period_re=re.compile(r"(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=False,
    merge_drcr_suffix=True,
    opening_row_balance_only=True,
    zero_amount_is_empty=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
IDBI_LAYOUT_1.validate()

IDBI_LAYOUT_2 = LayoutSpec(
    layout_id="idbi_sno_txndate_valuedate_description_chequeno_withdrawals_deposits_balance",
    bank_key="idbi",
    bank_markers=("IDBIBANK",),
    merge_statements=True,
    bank_name="IDBI Bank",
    columns={
        "date": (("txndate",), ("txn", "date")),
        "value_date": (("valuedate",), ("value", "date")),
        "narration": (("description",),),
        "ref": (("chequeno",), ("cheque", "no")),
        "debit": (("withdrawals",),),
        "credit": (("deposits",),),
        "balance": (("balance",), ("balanceinr",), ("balance", "inr")),
    },
    text_columns=("date", "value_date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    secondary_date_column="value_date",
    header_repeats=True,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
)
IDBI_LAYOUT_2.validate()
