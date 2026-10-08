"""AP Grameena Vikas Bank layout ("Post Date | Value Date | Narration | Cheque Details | Debit | Credit |
Balance"): dd-mm-yyyy dates in both date columns, "-" empty cheque cells, balance cells end in a fused
Cr/Dr suffix ("2183.32Cr"). Period prints as "Statement of account from dd-mm-yyyy to dd-mm-yyyy".
Brand evidence: "AP GRAMEENA VIKAS BANK" in the account header (IFSC prefix APGV). The same core
format is shared by APGB (Andhra Pragathi Grameena Bank) statements -- refused via OTHER_BANK_MARKERS.
Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

APGV_LAYOUT_1 = LayoutSpec(
    layout_id="apgv_postdate_valuedate_narration_chequedetails_debit_credit_balance",
    bank_key="apgv",
    bank_name="AP Grameena Vikas Bank",
    bank_markers=("APGRAMEENAVIKASBANK",),
    columns={
        "date": (("postdate",),),
        "valuedate": (("valuedate",),),
        "narration": (("narration",),),
        "cheque": (("cheque",), ("chequedetails",)),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "valuedate", "narration", "cheque"),
    secondary_date_column="valuedate",
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?: ?\(?[Cc][Rr]\)?\.?| ?\(?[Dd][Rr]\)?\.?)?$"),
    period_re=re.compile(r"(?i)from::?(\d{2}/\d{2}/\d{4})to:?(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    empty_amount_marker="-",
    merge_drcr_suffix=True,
    ignore_line_res=(re.compile(r".*(?:CRRTCHG|ACCOUNTMAI)[\d.]+|.*LOANACCEPTED"),),   # dated memo lines carry no money cells at all
    row_order="auto",
)
APGV_LAYOUT_1.validate()
