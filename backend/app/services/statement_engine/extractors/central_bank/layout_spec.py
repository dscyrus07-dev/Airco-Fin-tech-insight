"""Central Bank of India layouts. Facts only.

CBI-L1 ("Post Date | Value Date | Branch Code | Cheque Number | Account Description | Debit | Credit |
Balance"): the header prints on two lines -- "Post Date / Value / Branch / Cheque / Account Description /
Debit / Credit / Balance" with "Date / Code / Number" on the sub-line. Rows are dd/dd/dddd post + value
dates, a 5-digit branch code, an optional cheque number, narration, one money cell and a balance that
carries a trailing Cr/Dr suffix fused into the same cell ("9999.99 CR"). Statement period line:
"STATEMENT OF ACCOUNT from dd/dd/dddd to dd/dd/dddd"; the table ends at "END OF STATEMENT FROM
INTERNET BANKING". Brand "CENTRAL BANK OF INDIA" prints on every statement.
"""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

CBI_LAYOUT_1 = LayoutSpec(
    layout_id="central_bank_postdate_value_branch_cheque_accountdescription_debit_credit_balance",
    bank_key="central_bank",
    bank_name="Central Bank of India",
    bank_markers=("CENTRALBANKOFINDIA",),
    columns={
        "date": (("postdate",), ("post", "date")),
        "valuedate": (("value",), ("value", "date"), ("date",)),
        "branch": (("branch",), ("code",)),
        "cheque": (("cheque",), ("number",)),
        "narration": (("accountdescription",), ("description",)),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "valuedate", "branch", "cheque", "narration"),
    secondary_date_column="valuedate",
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?: ?\(?[Cc][Rr]\)?\.?| ?\(?[Dd][Rr]\)?\.?)?$"),
    period_re=re.compile(r"(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    merge_statements=True,
    merge_drcr_suffix=True,
    end_markers=("ENDOFSTATEMENTFROMINTERNETBANKING",),
    row_order="auto",
)
CBI_LAYOUT_1.validate()

# CBI-L2 adds a TRANSACTION column between Cheque and the description
# ("postdate value branch cheque transaction description debit credit balance").
CBI_LAYOUT_2 = LayoutSpec(
    layout_id="central_bank_postdate_value_branch_cheque_transaction_description_debit_credit_balance",
    bank_key="central_bank",
    bank_name="Central Bank of India",
    bank_markers=("CENTRALBANKOFINDIA",),
    columns={
        "date": (("postdate",), ("post", "date")),
        "valuedate": (("value",), ("value", "date"), ("date",)),
        "branch": (("branch",), ("code",)),
        "cheque": (("cheque",), ("number",)),
        "narration": (("transactiondescription",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "valuedate", "branch", "cheque", "narration"),
    secondary_date_column="valuedate",
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?: ?\(?[Cc][Rr]\)?\.?| ?\(?[Dd][Rr]\)?\.?)?$"),
    period_re=re.compile(r"(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    merge_statements=True,
    merge_drcr_suffix=True,
    end_markers=("ENDOFSTATEMENTFROMINTERNETBANKING",),
    row_order="auto",
)
CBI_LAYOUT_2.validate()
