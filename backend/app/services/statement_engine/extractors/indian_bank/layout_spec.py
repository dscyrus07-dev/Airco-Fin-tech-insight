"""Indian Bank layout configuration (fingerprint "transaction date | particulars | withdrawals | deposit | balance"; the
date title wraps over two lines, an empty money cell prints "-", balances carry a Cr/Dr suffix). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

INDIAN_BANK_LAYOUT_1 = LayoutSpec(
    layout_id="indianbank_transactiondate_particulars_withdrawals_deposit_balance",
    bank_key="indian_bank",
    bank_markers=("INDIANBANK",),
    merge_statements=True,
    bank_name="Indian Bank",
    columns={
        "date": (("transaction",), ("transactiondate",)),
        "narration": (("particulars",),),
        "debit": (("withdrawals",), ("withdrawal",)),
        "credit": (("deposit",), ("deposits",)),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?:[Cc][Rr]|[Dd][Rr])?$"),
    empty_amount_marker="-",
    period_re=re.compile(r"StatementPeriod:From(\d{2}/\d{2}/\d{4})To(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    row_order="auto",
    dates_monotonic_expected=False,
)
INDIAN_BANK_LAYOUT_1.validate()


# "Value Date | Post Date | Remitter Branch | Description | Cheque No | DR | CR | Balance" on two
# header lines ("Value"/"Post"/"Remitter" on line 1, "Date"/"Date"/"Branch" on line 2): the row date
# is the Post Date column and prints yearless "MM/DD", resolved through the printed
# "STATEMENT OF ACCOUNT from dd/mm/yyyy to dd/mm/yyyy" range. Money splits into a DR and a CR column;
# the balance carries a CR suffix and the first row is a "BALANCE B/F" opening line.
INDIAN_BANK_LAYOUT_2 = LayoutSpec(
    layout_id="indianbank_postdate_remitter_description_chequeno_dr_cr_balance_yearless",
    bank_key="indian_bank",
    bank_markers=("INDIANBANK",),
    merge_statements=True,
    bank_name="Indian Bank",
    columns={
        "date": (("post",), ("postdate",), ("post", "date")),
        "remitter": (("remitter",),),
        "narration": (("description",),),
        "ref": (("chequeno",), ("cheque", "no")),
        "debit": (("dr",),),
        "credit": (("cr",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "remitter", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    year_from_period=True,
    continuation_amounts=True,
    date_re=re.compile(r"^\d{2}/\d{2}$"),
    date_format="%d/%m %Y",  # _add_years joins "dd/mm yyyy" with a space
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}\s*(?i:(?:cr|dr))?$"),
    opening_balance_re=re.compile(r"(?i)balanceb/f(-?[\d,]+\.\d{2})"),
    period_re=re.compile(r"(?i)from(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
INDIAN_BANK_LAYOUT_2.validate()


# "Date | Transaction Details | Debits | Credits | Balance" web-statement export: INR-prefixed amounts,
# a "-" token in the empty money cell, dates "d Mon yyyy", and a printed Opening/Ending Balance +
# Total Credits/Debits block above the table.
INDIAN_BANK_LAYOUT_3 = LayoutSpec(
    layout_id="indianbank_date_transactiondetails_debits_credits_balance_inr",
    bank_key="indian_bank",
    bank_markers=("INDIANBANK",),
    merge_statements=True,
    bank_name="Indian Bank",
    columns={
        "date": (("date",),),
        "narration": (("transactiondetails",), ("transaction", "details"), ("details",),),
        "debit": (("debits",),),
        "credit": (("credits",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    amount_prefix="INR",
    empty_amount_marker="-",
    date_re=re.compile(r"^(?:\d{1,2} [A-Za-z]{3}|[A-Za-z]{3} \d{1,2}) \d{4}$"),
    date_format="%d %b %Y|%b %d %Y",
    amount_re=re.compile(r"^[+-]?[\d,]+\.\d{2}$"),
    opening_balance_re=re.compile(r"(?i)openingbalanceinr(-?[\d,]+\.\d{2})"),
    closing_balance_re=re.compile(r"(?i)endingbalanceinr(-?[\d,]+\.\d{2})"),
    period_re=re.compile(r"(?!)"),
    period_date_format="%d %b %Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
INDIAN_BANK_LAYOUT_3.validate()
