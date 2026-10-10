"""Indian Overseas Bank layouts. L1: "Date (Value | Particulars | Ref | Transaction | Debit(Rs) | Credit(Rs) |
Balance(Rs)" — the Date/Value-Date titles fuse into one cell; the value date itself prints as a parenthesised
continuation line under each row and is ignored. Empty money cells print "-". Dates `dd-Mmm-yyyy`; period prints
`ddmmyyyytoddmmyyyy`. The brand never prints in the text layer -> routing relies on the detector. Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

IOB_LAYOUT_1 = LayoutSpec(
    layout_id="iob_datevalue_particulars_ref_transaction_debitrs_creditrs_balancers",
    bank_key="iob",
    bank_name="Indian Overseas Bank",
    bank_markers=(),
    merge_statements=True,
    columns={
        "date": (("datevalue",), ("date", "value")),
        "narration": (("particulars",),),
        "ref": (("ref",),),
        "txntype": (("transaction",),),
        "debit": (("debitrs",), ("debit", "rs")),
        "credit": (("creditrs",), ("credit", "rs")),
        "balance": (("balancers",), ("balance", "rs")),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$"),
    date_format="%d-%b-%Y",
    amount_re=re.compile(r"^-?[\d,]+(?:\.\d{1,2})?$"),
    empty_amount_marker="-",
    period_re=re.compile(r"(\d{8})to(\d{8})"),
    period_date_format="%d%m%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    continuation_start="top",
    dates_monotonic_expected=False,
)
IOB_LAYOUT_1.validate()

IOB_LAYOUT_2 = LayoutSpec(
    layout_id="iob_date_chq_naration_cod_debit_credit_balance",
    bank_key="iob",
    bank_name="Indian Overseas Bank",
    bank_markers=(),
    merge_statements=True,
    columns={
        "date": (("date",),),
        "ref": (("chq",), ("chqno",), ("chq", "no")),
        "narration": (("naration",), ("narration",)),
        "cod": (("cod",), ("code",)),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$"),
    date_format="%d-%b-%Y",
    amount_re=re.compile(r"^-?[\d,]+(?:\.\d{1,2})?$"),
    period_re=re.compile(r"(\d{2}/\d{2}/\d{4})\D+(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    totals_line_re=re.compile(r"(?i)TOTALDEBIT:?([\d,]+(?:\.\d{1,2})?)TOTALCREDIT:?([\d,]+(?:\.\d{1,2})?)"),
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    continuation_start="top",
    dates_monotonic_expected=False,
)
IOB_LAYOUT_2.validate()
