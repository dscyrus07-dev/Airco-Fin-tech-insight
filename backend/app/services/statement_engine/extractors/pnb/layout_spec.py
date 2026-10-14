"""Punjab National Bank layout ("Date | Instrument Id | Amount | Type | Balance | Remarks" — single amount column with
the Dr/Cr marker printed in its own "Type" column; brand never appears in the text layer so routing relies on the
detector). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

PNB_LAYOUT_1 = LayoutSpec(
    layout_id="pnb_date_instrumentid_amount_type_balance_remarks",
    bank_key="pnb",
    bank_markers=(),
    merge_statements=True,
    bank_name="Punjab National Bank",
    columns={
        "date": (("date",),),
        "instid": (("instrumentid",), ("instrument", "id")),
        "type": (("type",),),
        "narration": (("remarks",),),
        "amount": (("amount",), ("amountinr",)),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    single_amount_column="amount",
    side_marker_column="narration",
    date_re=re.compile(r"^\d{2}[/\-]\d{2}[/\-]\d{4}$"),
    date_format="%d/%m/%Y|%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+(?:\.\d{1,2})?$"),
    period_re=re.compile(r"(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=False,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
)
PNB_LAYOUT_1.validate()


# L2 (n1): passbook landscape, narrow page (~750pt). Header prints on two visual lines:
# "Transaction | Cheque | Withdrawal | Deposit | Balance | Narration" over
# "Date | Number" - the date title is absent from the first line, so `header_lines`
# (not `header_wraps`) merges the pair. Balances carry a period-suffixed "Cr."/"Dr."
# (merged onto the cell). No printed opening/closing anchors: REVIEW ceiling.
PNB_LAYOUT_2 = LayoutSpec(
    layout_id="pnb_transactiondate_chequenumber_withdrawal_deposit_balance_narration_2l",
    bank_key="pnb",
    bank_markers=(),
    merge_statements=True,
    bank_name="Punjab National Bank",
    columns={
        "date": (("transaction", "date"), ("transactiondate",)),
        "ref": (("cheque", "number"), ("chequenumber",)),
        "debit": (("withdrawal",), ("withdrawals",)),
        "credit": (("deposit",), ("deposits",)),
        "balance": (("balance",),),
        "narration": (("narration",),),
    },
    text_columns=("date", "ref", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    header_lines=2,
    # the printed narration column sits RIGHT of the money columns, so its band must reach
    # left past the money cells: classify_word only runs the amount-edge check inside the
    # last text band. Narration words right of the balance edge drop as trailing furniture.
    band_left_pad={"narration": 274.0},
    merge_drcr_suffix=True,
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?:\s*(?i:cr|dr)\.?)?$"),
    period_re=re.compile(r"(\d{4}/\d{2}/\d{2}|\d{2}/\d{2}/\d{4})to(\d{4}/\d{2}/\d{2}|\d{2}/\d{2}/\d{4})"),
    period_date_format="%Y/%m/%d|%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=False,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
)
PNB_LAYOUT_2.validate()


# L3 (n1): passbook landscape, wide page (~1024pt). Same column set but the header is a
# three-line interleave: "Transaction | Cheque" (top), "Withdrawal | Deposit | Balance |
# Narration" (middle), "Date | Number" (bottom) - the money titles sit BETWEEN the wrapped
# first-line titles. Interior pages repeat no header. Balances carry "Cr."/"Dr.".
PNB_LAYOUT_3 = LayoutSpec(
    layout_id="pnb_transactiondate_chequenumber_withdrawal_deposit_balance_narration_3l",
    bank_key="pnb",
    bank_markers=(),
    merge_statements=True,
    bank_name="Punjab National Bank",
    columns=PNB_LAYOUT_2.columns,
    text_columns=PNB_LAYOUT_2.text_columns,
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    header_lines=3,
    band_left_pad={"narration": 512.0},   # see L2: narration band must start left of the money cells
    merge_drcr_suffix=True,
    date_re=PNB_LAYOUT_2.date_re,
    date_format=PNB_LAYOUT_2.date_format,
    amount_re=PNB_LAYOUT_2.amount_re,
    period_re=PNB_LAYOUT_2.period_re,
    period_date_format=PNB_LAYOUT_2.period_date_format,
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=False,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
)
PNB_LAYOUT_3.validate()
