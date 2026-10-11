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
        "narration": (("narration",), ("particulars",)),
        "ref": (("chqrefno",), ("chq", "ref", "no"), ("chqref",), ("reference",)),
        "value_date": (("valuedt",), ("value", "dt"), ("valuedate",), ("value", "date")),
        "withdrawal": (("withdrawalamt",), ("withdrawal", "amt"), ("withdrawalamount",), ("withdrawal", "amount")),
        "deposit": (("depositamt",), ("deposit", "amt"), ("depositamount",), ("deposit", "amount")),
        "balance": (("closingbalance",), ("closing", "balance")),
    },
    text_columns=("date", "narration", "ref", "value_date"),
    debit_column="withdrawal",
    credit_column="deposit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{2,4}$"),
    date_format="%d/%m/%y|%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"From:(\d{2}/\d{2}/\d{4})To:(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="STATEMENTSUMMARY",
    summary_label_text="openingbalancedrcountcrcountdebitscreditsclosingbal",
    secondary_date_column="value_date",
    ifsc_re=re.compile(r"HDFC0\d{6}"),
    account_label="accountno",
    zero_amount_is_empty=True,
)
HDFC_LAYOUT_A.validate()


# "Sr.No. | Date | Particulars | Chq./Ref. | Debit | Credit | Closing Balance" (passbook print):
# "Chq./Ref. Number" wraps so "Number" lands on the next line; continued pages title the last column
# just "Balance". Zero money cells print "0.00". Rows open with "OPENING BALANCE <amt>" and close with a
# "STATEMENT SUMMARY" labels->numbers block + "**END OF STATEMENT**".
HDFC_LAYOUT_B = LayoutSpec(
    layout_id="hdfc_srno_date_particulars_chqref_debit_credit_closingbalance",
    bank_key="hdfc",
    bank_markers=("HDFCBANK",),
    merge_statements=True,
    bank_name="HDFC Bank",
    columns={
        "date": (("date",),),
        "narration": (("particulars",), ("narration",)),
        "ref": (("chqref",), ("chqrefno",), ("chq", "ref", "no"), ("chqref", "number"), ("chq", "ref", "number")),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("closingbalance",), ("closing", "balance"), ("balance",)),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"FROM(\d{2}/\d{2}/\d{4})TO(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="STATEMENTSUMMARY",
    summary_label_text="openingbalancedrcountcrcountdebitscreditsclosingbal",
    summary_expected=False,
    end_markers=("ENDOFSTATEMENT",),
    header_repeats=True,
    header_wraps=True,
    zero_amount_is_empty=True,
    opening_balance_re=re.compile(r"(?i)openingbalance(-?[\d,]+\.\d{2})"),
    anchor_full=True,
    dates_monotonic_expected=False,
)
HDFC_LAYOUT_B.validate()
