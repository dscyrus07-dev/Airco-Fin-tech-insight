"""Kotak Mahindra Bank layout configuration (dominant fingerprint "date | transaction details | cheque/reference# |
debit | credit | balance"; signed amounts, a dated OPENING BALANCE row). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

KOTAK_LAYOUT_1 = LayoutSpec(
    layout_id="kotak_date_transactiondetails_chequereference_debit_credit_balance",
    bank_key="kotak",
    merge_statements=True,
    bank_name="Kotak Mahindra Bank",
    columns={
        "date": (("date",),),
        "narration": (("transaction", "details"), ("transactiondetails",)),
        "ref": (("chequereference",), ("cheque", "reference")),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2} [A-Za-z]{3}, \d{4}$"),
    date_format="%d %b, %Y",
    amount_re=re.compile(r"^[+-]?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(?:from|^)(\d{2}[A-Za-z]{3},\d{4})-(\d{2}[A-Za-z]{3},\d{4})"),
    period_date_format="%d%b,%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    end_markers=("^SUMMARY",),
    header_repeats=True,
    opening_row_marker="OPENINGBALANCE",
    sign_is_decoration=True,
    closing_balance_re=re.compile(r"^(?:Savings?Account(?:\(s\))?(?:\+Prepaid)?)?Closingbalance(-?[\d,]+\.\d{2})$"),
)
KOTAK_LAYOUT_1.validate()

KOTAK_LAYOUT_2 = LayoutSpec(     # "date | narration | chq/ref no | withdrawal (dr) | deposit (cr) | balance"; balance carries (Cr)/(Dr)
    layout_id="kotak_date_narration_chqrefno_withdrawaldr_depositcr_balance",
    bank_key="kotak",
    merge_statements=True,
    bank_name="Kotak Mahindra Bank",
    columns={
        "date": (("date",),),
        "narration": (("narration",),),
        "ref": (("chqref", "no"), ("chqrefno",), ("chq", "ref", "no"), ("chq", "no"), ("chqno",)),
        "debit": (("withdrawal", "dr"), ("withdrawaldr",)),
        "credit": (("depositcr",), ("deposit", "cr")),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?:\((?:Cr|Dr)\))?$"),
    period_re=re.compile(r"Period:(\d{2}-\d{2}-\d{4})To(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    end_markers=("^STATEMENTSUMMARY",),
    closing_balance_re=re.compile(r"^ClosingBalance([\d,]+\.\d{2})\(Cr\)$"),
    header_repeats=True,
    opening_balance_re=re.compile(r"B/F([\d,]+\.\d{2})\(Cr\)"),
    continuation_start="top",
)
KOTAK_LAYOUT_2.validate()

from dataclasses import replace   # noqa: E402

KOTAK_LAYOUT_3 = replace(         # same table as layout 2 with "dd-Mmm-yy" dates and a dated OPENING BALANCE row
    KOTAK_LAYOUT_2,
    layout_id="kotak_date_narration_chqrefno_withdrawaldr_depositcr_balance_ddmmmyy",
    date_re=re.compile(r"^\d{2}-[A-Za-z]{3}-\d{2}$"),
    date_format="%d-%b-%y",
    period_re=re.compile(r"Period(\d{2}-[A-Za-z]{3}-\d{2})to(\d{2}-[A-Za-z]{3}-\d{2})"),
    period_date_format="%d-%b-%y",
    opening_balance_re=None,
    opening_row_marker="OPENINGBALANCE",
)
KOTAK_LAYOUT_3.validate()
