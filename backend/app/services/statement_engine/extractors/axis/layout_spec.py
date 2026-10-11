"""Axis Bank layout configuration (family F1, dominant fingerprint "tran date | chq no | particulars | debit | credit |
balance | init. br"). Header printed on page 1 only; page-1 opening balance, a TRANSACTION TOTAL line and a CLOSING BALANCE
line are printed around the table. The "Chq No" values share the narration band, so the cheque number is part of the
raw narration."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

AXIS_TRAN_CHQ_PARTICULARS_DR_CR_BAL_ID = "axis_trandate_chqno_particulars_debit_credit_balance_initbr"
_AMT = r"(-?[\d,]*\.\d{2})"

AXIS_LAYOUT_1 = LayoutSpec(
    layout_id=AXIS_TRAN_CHQ_PARTICULARS_DR_CR_BAL_ID,
    bank_key="axis",
    bank_markers=("AXISBANK",),
    merge_statements=True,
    bank_name="Axis Bank",
    columns={
        "date": (("trandate",), ("tran", "date")),
        "ref": (("chqno",), ("chq", "no")),
        "narration": (("particulars",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
        "init": (("init",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]*\.\d{2}$"),
    period_re=re.compile(r"From:(\d{2}-\d{2}-\d{4})To:(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    end_markers=("++++ENDOFSTATEMENT".replace("+", ""),),
    header_repeats=False,
    continuation_start="top",
    opening_balance_re=re.compile(r"OPENINGBALANCE" + _AMT),
    closing_balance_re=re.compile(r"^CLOSINGBALANCE" + _AMT + r"$"),
    totals_line_re=re.compile(r"^TRANSACTIONTOTAL" + _AMT + _AMT + r"$"),
    account_label="accountno",
)
AXIS_LAYOUT_1.validate()


# "Tran Date | Value Date | Transaction Particulars | Chq No | Amount(INR) | DR/CR | Balance(INR) |
# Branch Name": ONE money column whose side lives in a dedicated DR/CR column between the amount and
# the right-aligned balance; an OPENING BALANCE figure sits on the first row line. The trailing
# Branch Name text column carries no money and is ignored.
AXIS_LAYOUT_2 = LayoutSpec(
    layout_id="axis_trandate_valuedate_transactionparticulars_chqno_amountinr_drcr_balanceinr_branchname",
    bank_key="axis",
    bank_markers=("AXISBANK",),
    merge_statements=True,
    bank_name="Axis Bank",
    columns={
        "date": (("trandate",), ("tran", "date")),
        "value_date": (("valuedate",), ("value", "date")),
        "narration": (("transactionparticulars",), ("transaction", "particulars"), ("particulars",)),
        "ref": (("chqno",), ("chq", "no")),
        "amount": (("amountinr",), ("amount",)),
        "drcr": (("drcr",), ("dr", "cr"), ("dr", "/", "cr")),
        "balance": (("balanceinr",), ("balance",)),
        "branch": (("branchname",), ("branch", "name")),
    },
    text_columns=("date", "value_date", "narration", "ref", "drcr"),
    debit_column="amount_dr",
    credit_column="amount_cr",
    single_amount_column="amount",
    side_marker_column="drcr",
    balance_column="balance",
    secondary_date_column="value_date",
    band_left_pad={"drcr": 70.0},
    continuation_amounts=True,
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?(?:[\d,]+)?\.\d{2}(?:\s+(?i:cr|dr))?$"),
    opening_balance_re=re.compile(r"(?i)openingbalance(-?[\d,]*\.\d{2})"),
    closing_balance_re=re.compile(r"(?i)closingbalance(-?[\d,]*\.\d{2})"),
    anchor_full=True,
    period_re=re.compile(r"(?!)"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
AXIS_LAYOUT_2.validate()

# "Txn Date | Transaction | Withdrawals | Deposits | Balance | Other Information" — mobile-app export: header on page 2
# (page 1 is a customer cover), an "Opening Balance" line opens the table, "Other Information" is a sparse trailing
# column whose cells are page furniture. No closing/totals print -> REVIEW ceiling.
AXIS_LAYOUT_3 = LayoutSpec(
    layout_id="axis_txndate_transaction_withdrawals_deposits_balance_otherinformation",
    bank_key="axis",
    bank_markers=("AXISBANK",),
    merge_statements=True,
    bank_name="Axis Bank",
    columns={
        "date": (("txndate",), ("txn", "date")),
        "narration": (("transaction",),),
        "debit": (("withdrawals",),),
        "credit": (("deposits",),),
        "balance": (("balance",),),
        "otherinfo": (("otherinformation",), ("other", "information")),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]*\.\d{2}$"),
    period_re=re.compile(r"(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    opening_balance_re=re.compile(r"(?i)openingbalance" + _AMT),
    anchor_full=True,
    dates_monotonic_expected=False,
)
AXIS_LAYOUT_3.validate()

# Same export minus the "Other Information" column.
AXIS_LAYOUT_4 = LayoutSpec(
    layout_id="axis_txndate_transaction_withdrawals_deposits_balance",
    bank_key="axis",
    bank_markers=("AXISBANK",),
    merge_statements=True,
    bank_name="Axis Bank",
    columns={
        "date": (("txndate",), ("txn", "date")),
        "narration": (("transaction",),),
        "debit": (("withdrawals",),),
        "credit": (("deposits",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]*\.\d{2}$"),
    period_re=re.compile(r"(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    opening_balance_re=re.compile(r"(?i)openingbalance" + _AMT),
    anchor_full=True,
    dates_monotonic_expected=False,
)
AXIS_LAYOUT_4.validate()
