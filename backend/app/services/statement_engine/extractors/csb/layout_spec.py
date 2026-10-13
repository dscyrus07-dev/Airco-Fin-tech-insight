"""CSB Bank layout ("Date | Value | Transaction | Debit | Credit | Balance").
Dates dd/mm/yyyy; separate debit/credit columns; an undated "Opening Balance" line prints the opening
figure in the balance column; balance right-aligned; header repeats per page. Note: part of the corpus
folder is mislabelled Federal Bank exports which correctly route to the federal layouts. Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

CSB_LAYOUT_1 = LayoutSpec(
    layout_id="csb_date_value_transaction_debit_credit_balance",
    bank_key="csb",
    bank_markers=("CSBBANK",),
    merge_statements=True,
    bank_name="CSB Bank",
    columns={
        "date": (("date",),),
        "value_date": (("value",), ("valuedate",), ("value", "date")),
        "narration": (("transaction",), ("particulars",)),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$"),
    date_format="%d-%b-%Y",
    amount_re=re.compile(r"^-?[\d,]*\.\d{2}(?i:(?:cr|dr))?$"),
    period_re=re.compile(r"(?i)period(\d{2}[-/.]\d{2}[-/.]\d{4})to(\d{2}[-/.]\d{2}[-/.]\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    secondary_date_column="value_date",
    header_repeats=True,
    opening_balance_re=re.compile(r"(?i)OpeningBalance(-?[\d,]*\.\d{2})"),
    anchor_full=True,
    date_left_pad=10.0,
)
CSB_LAYOUT_1.validate()


# L2: CSB ePassbook "Date | Particulars | Withdrawal | Deposit | Balance". `dd-Mmm-yyyy` dates; a dated
# "OPENING BALANCE" row opens the table; narration continues below AND above the dated line; balances carry
# a (sometimes space-split) trailing "CR"; "Closing Balance <amt> CR" prints merged into the tail.
CSB_LAYOUT_2 = LayoutSpec(
    layout_id="csb_date_particulars_withdrawal_deposit_balance",
    bank_key="csb",
    bank_markers=("CSBEPASSBOOK", "CSBBANK"),
    merge_statements=True,
    bank_name="CSB Bank",
    columns={
        "date": (("date",),),
        "narration": (("particulars",),),
        "debit": (("withdrawal",),),
        "credit": (("deposit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-[A-Za-z]{3}-(?:\d{4})?$"),
    date_tail_re=re.compile(r"^\d{4}$"),
    date_format="%d-%b-%Y|%d-%b- %Y",
    amount_re=re.compile(r"^-?[\d,]*\.\d{2}(?:\s*(?i:cr|dr))?$"),
    period_re=CSB_LAYOUT_1.period_re,
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    opening_row_marker="OPENINGBALANCE",
    closing_row_marker="CLOSINGBALANCE",
    opening_balance_re=re.compile(r"(?i)OpeningBalance(-?[\d,]*\.\d{2})"),
    closing_balance_re=re.compile(r"(?i)ClosingBalance(-?[\d,]*\.\d{2})"),
    anchor_full=True,
    header_repeats=True,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
    left_aligned_amounts=True,
    continuation_amounts=True,
)
CSB_LAYOUT_2.validate()


# L3: netbanking "TRANS DATE | VALUE DATE | DETAILS | REF NO./CHEQUE NO. | DEBITS | CREDITS | BALANCE" export.
# Column titles wrap onto a second line ("TRANS"/"DATE", "REF NO."/"CHEQUE NO."); dates split "01-JUL-" + "2025";
# a dated "B/F ..." row restates the opening balance; the summary band above the table prints
# Opening/Total Debit/Total Credit/Closing labels with values on the next line (closing not safely regex-able ->
# single-ended anchor only). Unused side prints 0.00; amounts are left-aligned under wide bands.
CSB_LAYOUT_3 = LayoutSpec(
    layout_id="csb_transdate_valuedate_details_refno_debits_credits_balance",
    bank_key="csb",
    bank_markers=("CSBBANK", "CSBEPASSBOOK"),
    merge_statements=True,
    bank_name="CSB Bank",
    columns={
        "date": (("trans", "date"), ("transdate",), ("trans",)),
        "value_date": (("value", "date"), ("valuedate",), ("value",)),
        "narration": (("details",),),
        "ref": (("ref", "no", "cheque", "no"), ("ref", "no"), ("refno", "chequeno"), ("refno",)),
        "debit": (("debits",),),
        "credit": (("credits",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "narration", "ref"),
    secondary_date_column="value_date",
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-[A-Za-z]{3}-(?:\d{4})?$"),
    date_tail_re=re.compile(r"^\d{4}$"),
    date_format="%d-%b-%Y|%d-%b- %Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(?i)period:(\d{2}-[A-Za-z]{3}-\d{4})to(\d{2}-[A-Za-z]{3}-\d{4})"),
    period_date_format="%d-%b-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    header_wraps=True,
    opening_row_marker="B/F",
    left_aligned_amounts=True,
    zero_amount_is_empty=True,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
)
CSB_LAYOUT_3.validate()
