"""Bank of India layout configuration.

Two families observed in the corpus (N6):
- L1 branch-printed passbook: "Date | Description | Instr.No. | Debits | Credits | Balance",
  running page header "DATE:<d-m-y>BANK OF INDIA<branch>PAGE:<n>", account block carries
  "IFSC Code:BKID...", a bare opening-balance figure prints alone under the header,
  "SOL-ID..." branch lines interleave inside the table, period
  "Statement of Account from <d-m-y> to <d-m-y>".
- L2 "DetailedStatement" web export: "Sr No | Date | Remarks | Debit | Credit | Balance",
  balance cells carry a "₹" prefix, narration wraps onto continuation lines, pages >=2
  carry no repeated header, period "Transaction Date from:<d-m-y> to:<d-m-y>",
  no printed opening/closing anchors (REVIEW ceiling by design).
Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

BANK_OF_INDIA_LAYOUT_1 = LayoutSpec(
    layout_id="bankofindia_date_description_instrno_debits_credits_balance",
    bank_key="bank_of_india",
    bank_markers=("BANKOFINDIA", "IFSC:BKID", "IFSCCODE:BKID"),
    merge_statements=True,
    bank_name="Bank of India",
    columns={
        "date": (("date",),),
        "narration": (("description",),),
        "ref": (("instrno",), ("instr", "no"), ("instr", "no.")),
        "debit": (("debits",), ("debit",)),
        "credit": (("credits",), ("credit",)),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"StatementofAccountfrom(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    monospace_text=True,
    opening_row_balance_only=True,
    header_repeats=True,
    continuation_start="top",
    ignore_line_res=(
        re.compile(r"^-+$"),
        re.compile(r"^SOL-ID"),
        re.compile(r"^DATE:\d{2}-\d{2}-\d{4}BANKOFINDIA"),
        re.compile(r"^Page\d+of\d+", re.I),
    ),
)
BANK_OF_INDIA_LAYOUT_1.validate()

BANK_OF_INDIA_LAYOUT_2 = LayoutSpec(
    layout_id="bankofindia_srno_date_remarks_debit_credit_balance",
    bank_key="bank_of_india",
    bank_markers=("BANKOFINDIA", "IFSC:BKID", "IFSCCODE:BKID", "RELATIONSHIPBEYONDBANKING"),
    merge_statements=True,
    bank_name="Bank of India",
    columns={
        "date": (("date",),),
        "narration": (("remarks",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    amount_prefix="₹",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"TransactionDatefrom:?(\d{2}-\d{2}-\d{4})to:?(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    left_aligned_amounts=True,   # money cells right-align ~110 units past narrow centred titles
    row_order="auto",            # some exports print newest-first
    continuation_start="top",
    ifsc_re=re.compile(r"BKID0\d{6}"),
)
BANK_OF_INDIA_LAYOUT_2.validate()
