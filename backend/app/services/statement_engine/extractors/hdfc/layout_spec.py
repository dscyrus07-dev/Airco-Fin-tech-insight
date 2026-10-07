"""Declarative layout facts. The extraction machinery reads a LayoutSpec; adding a layout (HDFC A', D, other
banks) means adding a spec plus fixtures, not changing the machinery."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Pattern, Tuple


@dataclass(frozen=True)
class LayoutSpec:
    layout_id: str
    bank_key: str
    # column name -> alternative token sequences (normalised: lower-case alphanumerics) that print the column title
    columns: Dict[str, Tuple[Tuple[str, ...], ...]]
    amount_columns: Tuple[str, ...]            # right-aligned money columns, matched by right edge
    date_re: Pattern[str]
    date_format: str                           # strptime format of row dates
    amount_re: Pattern[str]
    period_re: Pattern[str]                    # matched on the whitespace-free text of a line
    summary_marker: str                        # whitespace-free, upper-case marker that starts the printed summary
    ifsc_re: Pattern[str]
    account_label: str                         # normalised token that precedes the account number value


HDFC_LAYOUT_A_ID = "hdfc_date_narration_ref_valuedt_withdrawal_deposit_closing"

HDFC_LAYOUT_A = LayoutSpec(
    layout_id=HDFC_LAYOUT_A_ID,
    bank_key="hdfc",
    columns={
        "date": (("date",),),
        "narration": (("narration",),),
        "ref": (("chqrefno",), ("chq", "ref", "no")),
        "value_date": (("valuedt",), ("value", "dt")),
        "withdrawal": (("withdrawalamt",), ("withdrawal", "amt")),
        "deposit": (("depositamt",), ("deposit", "amt")),
        "balance": (("closingbalance",), ("closing", "balance")),
    },
    amount_columns=("withdrawal", "deposit", "balance"),
    date_re=re.compile(r"^\d{2}/\d{2}/\d{2}$"),
    date_format="%d/%m/%y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"From:(\d{2}/\d{2}/\d{4})To:(\d{2}/\d{2}/\d{4})"),
    summary_marker="STATEMENTSUMMARY",
    ifsc_re=re.compile(r"HDFC0\d{6}"),
    account_label="accountno",
)
