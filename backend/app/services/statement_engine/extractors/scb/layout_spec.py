"""Standard Chartered Bank layout configuration (fingerprint "date | value date | description | cheque | deposit |
withdrawal | balance"; value date wraps onto a second header line; opening "BALANCE FORWARD" row, running balance restated at
the top of later pages; a TOTAL line prints credits, debits, closing). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

SCB_LAYOUT_1 = LayoutSpec(
    layout_id="scb_date_valuedate_description_cheque_deposit_withdrawal_balance",
    bank_key="scb",
    bank_markers=("STANDARDCHARTERED",),
    merge_statements=True,
    bank_name="Standard Chartered Bank",
    columns={
        "date": (("date",),),
        "value_date": (("value",),),
        "narration": (("description",),),
        "ref": (("cheque",),),
        "credit": (("deposit",),),
        "debit": (("withdrawal",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2} [A-Za-z]{3} \d{2,4}$"),
    date_format="%d %b %y|%d %b %Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"^NOPERIOD(\d)(\d)$"),
    period_date_format="%d %b %Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    secondary_date_column="value_date",
    header_repeats=True,
    opening_row_marker="BALANCE",
    carry_forward_re=re.compile(r"(?i)BALANCE(?:BROUGHT)?FORWARD"),
    undated_rows_inherit_date=True,
    totals_line_re=re.compile(r"^(?:TOTAL|Total)([\d,]+\.\d{2})([\d,]+\.\d{2})([\d,]+\.\d{2})$"),
    totals_credit_first=True,
    totals_accumulate=True,
    page_footer_markers=("BANKDEPOSITSARECOVERED",),
    dates_monotonic_expected=False,
)
SCB_LAYOUT_1.validate()
