"""Dhanlaxmi Bank layout ("Date | Value Date | Description | Cheque No | Debits | Credits | Balance").
Dates dd-MMM-yyyy upper-case; right-aligned debit/credit columns; statement period prints as
"Period : dd-Mon-yyyy To dd-Mon-yyyy". Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

DHANLAXMI_LAYOUT_1 = LayoutSpec(
    layout_id="dhanlaxmi_date_valuedate_description_chequeno_debits_credits_balance",
    bank_key="dhanlaxmi",
    bank_markers=("DHANLAXMIBANK", "DHANBANK"),
    bank_name="Dhanlaxmi Bank",
    columns={
        "date": (("date",),),
        "value_date": (("value", "date"), ("valuedate",)),
        "narration": (("description",),),
        "ref": (("cheque", "no"), ("chequeno",), ("sr", "no")),
        "debit": (("debits",), ("debit",)),
        "credit": (("credits",), ("credit",)),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "narration", "ref"),
    secondary_date_column="value_date",
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$"),
    date_format="%d-%b-%Y",
    amount_re=re.compile(r"^-?[\d,]*\.\d{2}$"),
    zero_amount_is_empty=True,
    period_re=re.compile(r"(?i)period\s*:?\s*(\d{2}-[A-Za-z]{3}-\d{4})to(\d{2}-[A-Za-z]{3}-\d{4})"),
    period_date_format="%d-%b-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    opening_balance_re=re.compile(r"(?i)OpeningBalance(-?[\d,]*\.\d{2})"),
    closing_balance_re=re.compile(r"(?i)ClosingBalance(-?[\d,]*\.\d{2})"),
    anchor_full=True,
    date_left_pad=10.0,
)
DHANLAXMI_LAYOUT_1.validate()

DHANLAXMI_LAYOUT_2 = LayoutSpec(
    layout_id="dhanlaxmi_txndate_valuedate_description_chequerefno_txnamount",
    bank_key="dhanlaxmi",
    bank_markers=("DHANLAXMIBANK", "DHANBANK"),
    bank_name="Dhanlaxmi Bank",
    columns={
        "date": (("txn", "date"), ("txndate",)),
        "value_date": (("value", "date"), ("valuedate",)),
        "narration": (("description",),),
        "ref": (("cheque/refno",), ("chequerefno",), ("cheque", "refno")),
        "txn_amount": (("txn", "amount"), ("txnamount",)),
    },
    text_columns=("date", "value_date", "narration", "ref"),
    secondary_date_column="value_date",
    debit_column="debit",
    credit_column="credit",
    single_amount_column="txn_amount",
    balance_column="balance",
    balance_inline_re=re.compile(r"(?i)^balance\s*:?\s*(-?[\d,]+\.\d{2})$"),
    leading_amounts=True,
    chain_reorder_same_date=True,
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"(?i)^-?[\d,]*\.\d{2}(\s*(cr|dr)\.?)?$"),
    period_re=re.compile(r"(?!x)x"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_lines=2,
    header_repeats=True,
    page_footer_markers=("*CLOSINGBALANCE", "*THISISACOMPUTER"),
    end_markers=("^OPENINGBALANCEDEBITCOUNT",),
    row_order="auto",
)
DHANLAXMI_LAYOUT_2.validate()

# L3 (n5): "Date | Cheque/Ref No | Description | Debit Amount | Credit Amount | Balance" — no value
# date, dd/mm/yyyy dates, signed balances ("-6,701.93"). The B/F opening prints as a dated row whose
# credit cell equals its balance, and the printed "Total <debits> <credits>" counts it, so the row
# stays a transaction and the totals pair is the independent verifier. No closing anchor prints.
DHANLAXMI_LAYOUT_3 = LayoutSpec(
    layout_id="dhanlaxmi_date_chequerefno_description_debitamount_creditamount_balance",
    bank_key="dhanlaxmi",
    bank_markers=("DHANLAXMIBANK", "DHANBANK"),
    bank_name="Dhanlaxmi Bank",
    columns={
        "date": (("date",),),
        "ref": (("cheque/refno",), ("cheque", "refno"), ("cheque", "ref", "no"), ("chequerefno",)),
        "narration": (("description",),),
        "debit": (("debit", "amount"), ("debitamount",)),
        "credit": (("credit", "amount"), ("creditamount",)),
        "balance": (("balance",),),
    },
    text_columns=("date", "ref", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]*\.\d{2}$"),
    period_re=re.compile(r"(?i)(\d{2}-[A-Za-z]{3}-\d{2})TO(\d{2}-[A-Za-z]{3}-\d{2})"),
    period_date_format="%d-%b-%y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    totals_line_re=re.compile(r"(?i)^total(-?[\d,]+\.\d{2})(-?[\d,]+\.\d{2})$"),
    end_markers=("^ANYDISCREPANCIES",),
    row_order="auto",
)
DHANLAXMI_LAYOUT_3.validate()
