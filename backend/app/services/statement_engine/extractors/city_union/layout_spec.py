"""City Union Bank layouts. Brand "CITY UNION BANK" prints on every page. Facts only.

CUB-L1: "Date | Description | ChequeNo | Debit | Credit | Balance", dates dd/dd/yyyy,
narration wraps into single-column continuation lines.
CUB-L2: "Date | Particulars | ChqNo | Debit | Credit | Balance", dates dd-Mmm-yyyy;
period line "Period : dd-Mmm-yyyy to dd-Mmm-yyyy"; opening balance line
"Opening Balance as of dd-Mmm-yyyy <amt>".
"""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

CBI = None  # placeholder intentionally unused

CUB_LAYOUT_1 = LayoutSpec(
    layout_id="city_union_date_description_chequeno_debit_credit_balance",
    bank_key="city_union",
    bank_name="City Union Bank",
    bank_markers=("CITYUNIONBANK", "CITYUNIONBANKLIMITED"),
    columns={
        "date": (("date",),),
        "narration": (("description",),),
        "ref": (("chequeno",), ("cheque", "no")),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    merge_statements=True,
    row_order="auto",
)
CUB_LAYOUT_1.validate()

CUB_LAYOUT_2 = LayoutSpec(
    layout_id="city_union_date_particulars_chqno_debit_credit_balance",
    bank_key="city_union",
    bank_name="City Union Bank",
    bank_markers=("CITYUNIONBANK", "CITYUNIONBANKLIMITED"),
    columns={
        "date": (("date",),),
        "narration": (("particulars",),),
        "ref": (("chqno",), ("chq", "no")),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$"),
    date_format="%d-%b-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(\d{2}-[A-Za-z]{3}-\d{4})to(\d{2}-[A-Za-z]{3}-\d{4})"),
    period_date_format="%d-%b-%Y",
    opening_balance_re=re.compile(r"(?i)openingbalanceasof\d{2}-[a-z]{3}-\d{4}([\d,]+\.\d{2})"),
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    merge_statements=True,
    row_order="auto",
)
CUB_LAYOUT_2.validate()
