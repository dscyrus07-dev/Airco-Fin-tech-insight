"""Canara Bank layout configuration (family F1, dominant fingerprint "date | particulars | deposits | withdrawals |
balance"; credit column printed BEFORE the debit column). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

CANARA_DEP_WD_BAL_ID = "canara_date_particulars_deposits_withdrawals_balance"

CANARA_LAYOUT_1 = LayoutSpec(
    layout_id=CANARA_DEP_WD_BAL_ID,
    bank_key="canara",
    bank_markers=("CANARABANK",),
    merge_statements=True,
    bank_name="Canara Bank",
    columns={
        "date": (("date",),),
        "narration": (("particulars",),),
        "deposits": (("deposits",),),
        "withdrawals": (("withdrawals",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="withdrawals",
    credit_column="deposits",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(?:fortheperiod|between)(\d{2}-[A-Za-z]{3}-\d{4})(?:to|and)(\d{2}-[A-Za-z]{3}-\d{4})"),
    period_date_format="%d-%b-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    dates_monotonic_expected=False,
    period_tolerance_days=3,
    side_flip_policy="review",
    end_markers=("ENDOFSTATEMENT",),
    header_repeats=True,
    opening_balance_re=re.compile(r"OpeningBalance(-?[\d,]+\.\d{2})"),
    closing_balance_re=re.compile(r"^ClosingBalance(-?[\d,]+\.\d{2})$"),
    ignore_line_res=(re.compile(r"^[Pp]age\d+$"),),
)
CANARA_LAYOUT_1.validate()


# "Txn Date | Value Date | Cheque No. | Description | Branch | Debit | Credit | Balance" portal export:
# the txn date cell is a single "dd-mm-yyyy hh:mm:ss" token, the value date prints "d Mon yyyy",
# and Opening/Closing Balance lines carry a "Rs." prefix.
CANARA_LAYOUT_2 = LayoutSpec(
    layout_id="canara_txndate_valuedate_chequeno_description_branch_debit_credit_balance",
    bank_key="canara",
    bank_markers=("CANARABANK",),
    merge_statements=True,
    bank_name="Canara Bank",
    columns={
        "date": (("txndate",), ("txn", "date")),
        "value_date": (("valuedate",), ("value", "date")),
        "ref": (("chequeno",), ("cheque", "no"), ("chqno",), ("chq", "no")),
        "narration": (("description",),),
        "branch": (("branch",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "ref", "narration", "branch"),
    band_left_pad={"narration": 54.0},   # description data starts ~x256 while the "Description" title sits at ~306
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    secondary_date_column="value_date",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2}$"),
    date_format="%d-%m-%Y %H:%M:%S",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    opening_balance_re=re.compile(r"(?i)openingbalancers?\.?(-?[\d,]+\.\d{2})"),
    closing_balance_re=re.compile(r"(?i)^closingbalancers?\.?(-?[\d,]+\.\d{2})$"),
    period_re=re.compile(r"(?!)"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
CANARA_LAYOUT_2.validate()


CANARA_LAYOUT_3 = LayoutSpec(
    layout_id="canara_transdate_valuedate_branch_refchno_description_withdraws_deposit_balance",
    bank_key="canara",
    bank_markers=("CANARABANK",),
    merge_statements=True,
    bank_name="Canara Bank",
    columns={
        "date": (("trans",),),
        "value_date": (("value",),),
        "branch": (("branch",),),
        "ref": (("refchqno",), ("ref", "chq", "no")),
        "narration": (("description",),),
        "debit": (("withdraws",),),
        "credit": (("deposit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "branch", "ref", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    secondary_date_column="value_date",
    opening_row_marker="B/F",
    left_aligned_amounts=True,
    zero_amount_is_empty=True,
    date_re=re.compile(r"^\d{2}-[A-Za-z]{3}-\d{2}$"),
    date_format="%d-%b-%y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(?i)period:?(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
CANARA_LAYOUT_3.validate()


CANARA_LAYOUT_4 = LayoutSpec(
    layout_id="canara_txndate_valuedate_chequeno_description_branchcode_debit_credit_balance",
    bank_key="canara",
    bank_markers=("CANARABANK",),
    merge_statements=True,
    bank_name="Canara Bank",
    columns={
        "date": (("txndate",), ("txn", "date")),
        "value_date": (("valuedate",), ("value", "date")),
        "ref": (("chequeno",), ("cheque", "no"), ("cheque", "no.")),
        "narration": (("description",),),
        "branch": (("branch",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "ref", "narration", "branch"),
    band_left_pad={"narration": 62.0},   # "Description" title is centred; narration data starts ~x193 vs title ~252
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    secondary_date_column="value_date",
    row_order="auto",
    date_re=re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$"),
    date_format="%d-%b-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    opening_balance_re=re.compile(r"(?i)balanceb/f:?([\d,]+\.\d{2})"),
    closing_balance_re=re.compile(r"(?i)closingbalance:?([\d,]+\.\d{2})"),
    period_re=re.compile(r"(?i)searchedby:?(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
CANARA_LAYOUT_4.validate()
