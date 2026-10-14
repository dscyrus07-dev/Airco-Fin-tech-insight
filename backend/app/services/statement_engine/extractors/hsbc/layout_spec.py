"""HSBC layout ("Date | Description | Credit | Debit | Balance" — credit column before debit; "Date Range:
dd/mm/yyyy - dd/mm/yyyy" above the table; narration wraps under the description column). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

HSBC_LAYOUT_1 = LayoutSpec(
    layout_id="hsbc_date_description_credit_debit_balance",
    bank_key="hsbc",
    bank_markers=("HSBC",),
    bank_name="HSBC",
    columns={
        "date": (("date",),),
        "narration": (("description",),),
        "credit": (("credit",),),
        "debit": (("debit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(?i)daterange:?(\d{2}/\d{2}/\d{4})-(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
)
HSBC_LAYOUT_1.validate()

HSBC_LAYOUT_2 = LayoutSpec(
    layout_id="hsbc_date_paymenttypeanddetails_paidout_paidin_balance",
    bank_key="hsbc",
    bank_markers=("HSBC",),
    bank_name="HSBC UK",
    columns={
        "date": (("date",),),
        "narration": (("payment", "type", "and", "details"), ("paymenttypeanddetails",)),
        "debit": (("paid", "out"), ("paidout",)),
        "credit": (("paid", "in"), ("paidin",)),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    balance_optional=True,
    date_re=re.compile(r"^\d{2} [A-Za-z]{3} \d{2}$"),
    date_format="%d %b %y",
    date_join_words=True,
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(?i)(\d{1,2}[a-z]+)to(\d{1,2}[a-z]+\d{4})"),
    period_date_format="%d%B|%d%B%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    continuation_amounts=True,
    opening_balance_re=re.compile(r"(?i)balancebroughtforward[^\d-]{0,4}(-?[\d,]+\.\d{2})"),
    closing_balance_re=re.compile(r"(?i)closingbalance[^\d-]{0,4}(-?[\d,]+\.\d{2})"),
    balance_checkpoint_re=re.compile(r"(?i)balance(?:brought|carried)\s*forward[^\d-]{0,4}(-?[\d,]+\.\d{2})"),
    anchor_full=True,
    row_order="auto",
    dates_monotonic_expected=True,
)
HSBC_LAYOUT_2.validate()
