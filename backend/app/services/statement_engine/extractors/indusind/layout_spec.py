"""IndusInd layout ("Date | Particulars | ChqRefNo | Withdrawl | Deposit | Balance" — the debit title is printed
"Withdrawl" on some prints and "Withdrawal" on others; "Period : ddMMMyyyytoddMMMyyyy" above the table; integer-style
amounts without paise; narration wraps under particulars). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

INDUSIND_LAYOUT_1 = LayoutSpec(
    layout_id="indusind_date_particulars_chqrefno_withdrawl_deposit_balance",
    bank_key="indusind",
    bank_markers=("INDUSINDBANK",),
    bank_name="IndusInd Bank",
    columns={
        "date": (("date",),),
        "narration": (("particulars",),),
        "ref": (("chqrefno",), ("chq", "ref", "no"), ("chqref", "no")),
        "debit": (("withdrawl",), ("withdrawal",)),
        "credit": (("deposit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$"),
    date_format="%d-%b-%Y",
    amount_re=re.compile(r"^-?[\d,]+(?:\.\d{1,2})?$"),
    period_re=re.compile(r"(?i)period:?(\d{2}-?[a-z]{3}-?\d{4})to(\d{2}-?[a-z]{3}-?\d{4})"),
    period_date_format="%d-%b-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    opening_row_balance_only=True,
    closing_balance_re=re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}([\d,]+(?:\.\d{1,2})?)$"),
    header_repeats=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
INDUSIND_LAYOUT_1.validate()


# Second print family: "Chq No/Ref No" spells the ref title with slashes; every page re-opens with a dated
# "Brought Forward" balance row and closes with a dated "Carried Forward" one, both money cells print 0.00 when
# unused, and amounts always carry two decimals. Dates are dd-Mmm-yyyy on the transaction lines.
INDUSIND_LAYOUT_2 = LayoutSpec(
    layout_id="indusind_date_particulars_chqnorefno_withdrawal_deposit_balance",
    bank_key="indusind",
    bank_markers=("INDUSINDBANK", "INDUSLNDBANK", "INDUSIND.COM"),
    bank_name="IndusInd Bank",
    columns={
        "date": (("date",),),
        "narration": (("particulars",),),
        "ref": (("chqnorefno",), ("chq", "no", "ref", "no"), ("chqnoref", "no"), ("cheqrefno",), ("cheqnorefno",)),
        "debit": (("withdrawal",), ("withdrawl",)),
        "credit": (("deposit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$"),
    date_format="%d-%b-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(?i)period:?(\d{2}-?[a-z]{3}-?\d{4})-(\d{2}-?[a-z]{3}-?\d{4})"),
    period_date_format="%d-%b-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    opening_row_marker="BROUGHTFORWARD",
    closing_balance_re=re.compile(r"(?i)carriedforward([\d,]+\.\d{2})"),
    carry_forward_re=re.compile(r"(?i)broughtforward|carriedforward"),
    zero_amount_is_empty=True,
    date_left_pad=8.0,
    header_wraps=True,
    header_repeats=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
INDUSIND_LAYOUT_2.validate()


# Same "Chq No/Ref No" family printed with space-separated dates ("05 Jan 2026" is one PDF word); these prints do
# not carry Brought/Carried Forward rows, so the chain end stays self-derived (REVIEW).
INDUSIND_LAYOUT_3 = LayoutSpec(
    layout_id="indusind_date_particulars_chqnorefno_withdrawal_deposit_balance_spaced",
    bank_key="indusind",
    bank_markers=("INDUSINDBANK", "INDUSLNDBANK", "INDUSIND.COM"),
    bank_name="IndusInd Bank",
    columns=INDUSIND_LAYOUT_2.columns,
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2} [A-Za-z]{3} \d{4}$"),
    date_format="%d %b %Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{1,2}$"),
    period_re=re.compile(r"(?i)period:?(\d{2}[a-z]{3}\d{4})-(\d{2}[a-z]{3}\d{4})"),
    period_date_format="%d%b%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    opening_row_marker="BROUGHTFORWARD",
    closing_balance_re=re.compile(r"(?i)carriedforward([\d,]+\.\d{2})"),
    carry_forward_re=re.compile(r"(?i)broughtforward|carriedforward"),
    zero_amount_is_empty=True,
    date_left_pad=8.0,
    header_wraps=True,
    header_repeats=True,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
)
INDUSIND_LAYOUT_3.validate()
