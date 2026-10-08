"""Bank of Maharashtra layouts.
A: "Sr No | Date | Particulars | Cheque/Reference No | Debit | Credit | Balance | Channel" where empty
money cells print "-"; dates dd/mm/yyyy.
B: same grid plus a "Type" column between Date and Particulars, no Sr No.
Period line reads "... from dd/mm/yyyy to dd/mm/yyyy."; brand "BANK OF MAHARASHTRA" / IFSC MAHB print
in page furniture. Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

BOM_LAYOUT_1 = LayoutSpec(
    layout_id="bom_srno_date_particulars_chequereferenceno_debit_credit_balance_channel",
    bank_key="bank_of_maharashtra",
    bank_name="Bank of Maharashtra",
    bank_markers=("BANKOFMAHARASHTRA",),
    columns={
        "sr": (("srno",),),
        "date": (("date",),),
        "narration": (("particulars",),),
        "ref": (("chequereferenceno",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
        "channel": (("channel",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"from(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    merge_statements=True,
    page_break_re=re.compile(r"BSUMMARYFORACCOUNT"),
    end_markers=("ENDOFSTATEMENT",),
    empty_amount_marker="-",
    row_order="auto",
)
BOM_LAYOUT_1.validate()

BOM_LAYOUT_2 = LayoutSpec(
    layout_id="bom_date_type_particulars_chequereferenceno_debit_credit_balance_channel",
    bank_key="bank_of_maharashtra",
    bank_name="Bank of Maharashtra",
    bank_markers=("BANKOFMAHARASHTRA",),
    columns={
        "date": (("date",),),
        "type": (("type",),),
        "narration": (("particulars",),),
        "ref": (("chequereferenceno",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
        "channel": (("channel",),),
    },
    text_columns=("date", "type", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"from(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    merge_statements=True,
    page_break_re=re.compile(r"BSUMMARYFORACCOUNT"),
    end_markers=("ENDOFSTATEMENT",),
    empty_amount_marker="-",
    row_order="auto",
)
BOM_LAYOUT_2.validate()
