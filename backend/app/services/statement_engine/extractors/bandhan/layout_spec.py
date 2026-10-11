"""Bandhan Bank layouts.
A: "Date | Effective | Cheque Sequence | Branch | Description | Withdrawal | Deposit Amt | Balance",
dates dd/mm/yyyy, period line "FromDDMMYYYYtoDDMMYYYY" (fused digits).
B: "Date | Description | Debit/Credit | Amount | Balance", dates dd/mm/yyyy; the Dr/Cr marker prints in
its own column (single amount column + side marker); the page footer repeats "page no N".
Brand "BANDHAN BANK"/bandhanbank.com prints in furniture. Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

BANDHAN_LAYOUT_1 = LayoutSpec(
    layout_id="bandhan_date_effective_chequesequence_branch_description_withdrawal_depositamt_balance",
    bank_key="bandhan",
    bank_name="Bandhan Bank",
    bank_markers=("BANDHANBANK",),
    columns={
        "date": (("date",),),
        "effective": (("effective",),),
        "chequeseq": (("chequesequence",),),
        "branch": (("branch",),),
        "narration": (("description",),),
        "debit": (("withdrawal",),),
        "credit": (("depositamt",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "effective", "chequeseq", "branch", "narration"),
    secondary_date_column="effective",
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"from(\d{8})to(\d{8})"),
    period_date_format="%d%m%Y",
    summary_marker="^OPENINGBALANCEDRCOUNT",
    summary_label_text="openingbalancedrcountcrcountdebitscreditsclosingbalance",
    anchor_full=True,
    summary_expected=False,
    continuation_start="top",
    ignore_line_res=(re.compile(r"^PAGE\d+$"),),
    row_order="auto",
)
BANDHAN_LAYOUT_1.validate()

BANDHAN_LAYOUT_2 = LayoutSpec(
    layout_id="bandhan_date_description_debitcredit_amount_balance",
    bank_key="bandhan",
    bank_name="Bandhan Bank",
    bank_markers=("BANDHANBANK",),
    columns={
        "date": (("date",),),
        "narration": (("description",),),
        "drcr": (("debitcredit",),),
        "amount": (("amount",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "drcr"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    single_amount_column="amount",
    side_marker_column="drcr",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"^NOPERIOD(\d)(\d)$"),   # the statement prints "Transaction Period last 6 month" - no dates
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    opening_balance_re=re.compile(r"openingbalance([\d,]+\.\d{2})"),
    closing_balance_re=re.compile(r"closingbalance([\d,]+\.\d{2})"),
    end_markers=("PAGENO",),
    row_order="auto",
)
BANDHAN_LAYOUT_2.validate()
