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
    band_left_pad={"narration": 96.0},   # "Particulars" title is centred; narration data starts ~x108 vs title ~203
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}\s*(?:[Cc][Rr]|[Dd][Rr])?$"),   # balance prints "5224.11 CR" fused
    merge_drcr_suffix=True,
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
# is the Post Date column and prints in three wrap shapes — bare "dd/mm" (year injected from the printed
# "STATEMENT OF ACCOUNT from dd/mm/yyyy to dd/mm/yyyy" range via year_from_period), "dd/mm/" + "yyyy" on
# the continuation line, and "dd/mm" + "/yyyy" on the continuation line (date_tail completes the date and
# _add_years leaves it alone because it already parses). Money splits into a DR and a CR column; the
# balance carries a Cr suffix clipped at the page edge ("750041.02C" — opt-in clipped_drcr_suffix field),
# the ref title prints "Cheque No"/fused "Chq No/Ref"/clipped "Chequ", and the opening line prints
# "BALANCE B/F" or "Opening Balance :".
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
        "ref": (("chequeno",), ("cheque", "no"), ("chq", "noref"), ("chq", "no"), ("chqno",), ("chqnoref",),
                ("chequ",), ("chq",), ("chequ", "no")),
        "debit": (("dr",),),
        "credit": (("cr",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "remitter", "narration", "ref"),
    band_left_pad={"narration": 35.0},   # description data starts ~x404 while the "Description" title sits at ~435
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    year_from_period=True,
    continuation_amounts=True,
    clipped_drcr_suffix=True,   # balance tokens clip at the page edge ("750041.02C" for "…Cr")
    date_re=re.compile(r"^\d{2}/\d{2}/?$"),
    date_tail_re=re.compile(r"^/?\d{4}$"),
    date_format="%d/%m %Y|%d/%m/ %Y|%d/%m /%Y|%d/%m/%Y",  # tail joins "dd/mm"/"dd/mm/" + [" "]yyyy or /yyyy
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}\s*(?i:(?:cr|dr|c|d))?$"),
    opening_balance_re=re.compile(r"(?i)(?:balanceb/f|openingbalance)[:\s]*(-?[\d,]+\.\d{2})"),
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
