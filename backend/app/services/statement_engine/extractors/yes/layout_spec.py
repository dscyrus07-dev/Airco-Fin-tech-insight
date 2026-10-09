"""Yes Bank layouts. L1: "Transaction | Value Date | Cheque No/Reference No | Description | Withdrawals |
Deposits | Running Balance" (the "Date" half of the first title prints on the next line). The brand never
prints as a standalone token (only inside IFSC codes / narration strings) -> routing relies on the detector.
Dates are `dd Mmm yyyy`, `dd/mm/yyyy`, or `dd-Mmm-yyyy`. Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

YES_LAYOUT_1 = LayoutSpec(
    layout_id="yes_transaction_valuedate_chequenoreferenceno_description_withdrawals_deposits_runningbalance",
    bank_key="yes",
    bank_name="Yes Bank",
    bank_markers=(),
    merge_statements=True,
    columns={
        "date": (("transaction", "date"), ("transaction",), ("transactiondate",)),
        "value_date": (("value", "date"), ("valuedate",)),
        "ref": (("chequenoreferenceno",), ("cheque", "no", "reference", "no"), ("chequeno", "referenceno"), ("cheque",), ("chequeno",), ("cheque", "no")),
        "narration": (("description",),),
        "debit": (("withdrawals",),),
        "credit": (("deposits",),),
        "balance": (("running", "balance"), ("runningbalance",), ("balance",)),
    },
    text_columns=("date", "value_date", "ref", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    secondary_date_column="value_date",
    date_re=re.compile(r"^\d{2} [A-Za-z]{3} \d{4}$|^\d{2}/\d{2}/\d{4}$|^\d{2}-[A-Za-z]{3}-\d{4}$"),
    date_format="%d %b %Y|%d/%m/%Y|%d-%b-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
)
YES_LAYOUT_1.validate()

# L2 (PARKED — not registered): same table, but "Running Balance" wraps: the header line ends at "Running" and
# "Balance" prints alone on the next line. Fresh 97-file re-measure: routes 24% trusted (5 VERIFIED / 16 FAILED
# chain+side — this export family prints balances that do not reconcile; kept defined for study, unregistered).
_YES_L2_COLS = dict(YES_LAYOUT_1.columns, balance=(("running",),))
YES_LAYOUT_2 = LayoutSpec(
    layout_id="yes_transaction_valuedate_chequenoreferenceno_description_withdrawals_deposits_runningbalance_wrapped",
    bank_key="yes",
    bank_name="Yes Bank",
    bank_markers=(),
    merge_statements=True,
    columns=_YES_L2_COLS,
    text_columns=YES_LAYOUT_1.text_columns,
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    secondary_date_column="value_date",
    date_re=YES_LAYOUT_1.date_re,
    date_format=YES_LAYOUT_1.date_format,
    amount_re=YES_LAYOUT_1.amount_re,
    period_re=YES_LAYOUT_1.period_re,
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
)
YES_LAYOUT_2.validate()

# L3: the reference column is titled "Reference Number" / "No/Reference No" instead of "Cheque No/Reference No",
# and the balance title may be "Running Balance" (one line) or wrap after "Running".
_YES_L3_COLS = dict(
    YES_LAYOUT_1.columns,
    ref=(("reference", "number"), ("referencenumber",), ("no", "reference", "no"), ("noreferenceno",),
         *YES_LAYOUT_1.columns["ref"]),
    balance=(("running", "balance"), ("runningbalance",), ("running",), ("balance",)),
)
YES_LAYOUT_3 = LayoutSpec(
    layout_id="yes_transaction_valuedate_referencenumber_description_withdrawals_deposits_runningbalance",
    bank_key="yes",
    bank_name="Yes Bank",
    bank_markers=(),
    merge_statements=True,
    columns=_YES_L3_COLS,
    text_columns=YES_LAYOUT_1.text_columns,
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    secondary_date_column="value_date",
    date_re=re.compile(r"^\d{2} [A-Za-z]{3} \d{4}$|^\d{2}/\d{2}/\d{4}$|^\d{2}-[A-Za-z]{3}-\d{4}$|^\d{4}-\d{2}-\d{2}$"),
    date_format="%d %b %Y|%d/%m/%Y|%d-%b-%Y|%Y-%m-%d",
    amount_re=YES_LAYOUT_1.amount_re,
    period_re=YES_LAYOUT_1.period_re,
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
)
YES_LAYOUT_3.validate()
