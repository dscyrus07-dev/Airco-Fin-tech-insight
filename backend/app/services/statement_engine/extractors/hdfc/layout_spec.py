"""HDFC layout configuration (layout A). Facts only; the machinery lives in statement_engine.extraction."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

HDFC_LAYOUT_A_ID = "hdfc_date_narration_ref_valuedt_withdrawal_deposit_closing"

HDFC_LAYOUT_A = LayoutSpec(
    layout_id=HDFC_LAYOUT_A_ID,
    bank_key="hdfc",
    bank_markers=("HDFCBANK",),
    bank_name="HDFC Bank",
    columns={
        "date": (("date",),),
        "narration": (("narration",),),
        "ref": (("chqrefno",), ("chq", "ref", "no")),
        "value_date": (("valuedt",), ("value", "dt")),
        "withdrawal": (("withdrawalamt",), ("withdrawal", "amt")),
        "deposit": (("depositamt",), ("deposit", "amt")),
        "balance": (("closingbalance",), ("closing", "balance")),
    },
    text_columns=("date", "narration", "ref", "value_date"),
    debit_column="withdrawal",
    credit_column="deposit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{2}$"),
    date_format="%d/%m/%y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"From:(\d{2}/\d{2}/\d{4})To:(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="STATEMENTSUMMARY",
    summary_label_text="openingbalancedrcountcrcountdebitscreditsclosingbal",
    secondary_date_column="value_date",
    ifsc_re=re.compile(r"HDFC0\d{6}"),
    account_label="accountno",
)
HDFC_LAYOUT_A.validate()
