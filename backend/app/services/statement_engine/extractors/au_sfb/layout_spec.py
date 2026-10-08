"""AU Small Finance Bank layout ("Date | Description/Narration | Value Date | Chq./Ref. No. |
Debit(Dr.) | Credit(Cr.) | Balance"). Dates are fused ddMmmyyyy; empty money cells print "-";
the statement period is "Statement from ddMmmyyyy to ddMmmyyyy"; opening/closing balances print
as "Opening Balance INR 999.99"/"Closing Balance INR 999.99" on page 1. Brand evidence is the
AUBL IFSC prefix ("AU Small Finance Bank" does not print in the text layer). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

AU_LAYOUT_1 = LayoutSpec(
    layout_id="au_date_descriptionnarration_valuedate_chqrefno_debitdr_creditcr_balance",
    bank_key="au_sfb",
    bank_name="AU Small Finance Bank",
    bank_markers=("AUBL",),
    columns={
        "date": (("date",),),
        "narration": (("descriptionnarration",),),
        "valuedate": (("valuedate",),),
        "ref": (("chqrefno",),),
        "debit": (("debitdr",),),
        "credit": (("creditcr",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "valuedate", "ref"),
    secondary_date_column="valuedate",
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2} [A-Za-z]{3} \d{4}$"),
    date_format="%d %b %Y",
    amount_re=re.compile(r"^-?[\d,]+(?:\.\d{1,2})?$"),
    period_date_format="%d%b%Y",
    period_re=re.compile(r"(?i)statementfrom(\d{2}[a-z]{3}\d{4})to(\d{2}[a-z]{3}\d{4})"),
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    empty_amount_marker="-",
    opening_balance_re=re.compile(r"openingbalanceinr([\d,]+\.\d{2})"),
    closing_balance_re=re.compile(r"closingbalanceinr([\d,]+\.\d{2})"),
    row_order="auto",
)
AU_LAYOUT_1.validate()
