"""ICICI Bank layout configuration (fingerprint "s no | value date | transaction date | cheque number | transaction remarks |
withdrawal amount (INR) | deposit amount (INR) | balance (INR)"; both money cells always print, a zero marks the empty side).
Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

ICICI_LAYOUT_1 = LayoutSpec(
    layout_id="icici_sno_valuedate_transactiondate_chequenumber_remarks_withdrawal_deposit_balance",
    bank_key="icici",
    bank_markers=("ICICIBANK",),
    merge_statements=True,
    bank_name="ICICI Bank",
    columns={
        "date": (("transactiondate",), ("transaction", "date")),
        "ref": (("chequenumber",), ("cheque", "number")),
        "narration": (("transactionremarks",), ("transaction", "remarks")),
        "debit": (("withdrawalamount",), ("withdrawal", "amount")),
        "credit": (("depositamount",), ("deposit", "amount")),
        "balance": (("balanceinr",), ("balance", "inr"), ("balance",)),
    },
    text_columns=("date", "ref", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}[/,\-]\d{2}[/,\-]\d{4}$"),
    date_format="%d/%m/%Y|%d,%m,%Y|%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+(?:\.\d{1,2})?$"),
    period_re=re.compile(r"^NOPERIOD(\d)(\d)$"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    zero_amount_is_empty=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
ICICI_LAYOUT_1.validate()

ICICI_LAYOUT_2 = LayoutSpec(     # older ICICI layout (previously mis-filed under Canara): "date | mode | particulars | deposits | withdrawals | balance" with a dated B/F opening row
    layout_id="icici_date_mode_particulars_deposits_withdrawals_balance",
    bank_key="icici",
    bank_markers=("ICICIBANK",),
    merge_statements=True,
    bank_name="ICICI Bank",
    columns={
        "date": (("date",),),
        "mode": (("mode",),),
        "narration": (("particulars",),),
        "deposits": (("deposits",),),
        "withdrawals": (("withdrawals",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "mode", "narration"),
    band_left_pad={"narration": 12.0},   # narration data starts ~x144 vs the "Particulars" title at ~149
    debit_column="withdrawals",
    credit_column="deposits",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"theperiod([A-Za-z]+\d{2},\d{4})-([A-Za-z]+\d{2},\d{4})"),
    period_date_format="%B%d,%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    dates_monotonic_expected=False,
    period_tolerance_days=3,
    side_flip_policy="review",
    end_markers=("ENDOFSTATEMENT",),
    header_repeats=True,
    opening_row_marker="B/F",
)
ICICI_LAYOUT_2.validate()


# "S No. | Transaction Date | Cheque Number | Transaction Remarks | Withdrawal | Deposit | Balance" —
# two-line header: "Date"/"Amount (INR)"/"(INR)" sit on the second line. Rows carry one money cell
# (the empty side prints nothing). Dates dd.mm.yyyy; period "for the period <Mon d, yyyy> - <Mon d, yyyy>".
ICICI_LAYOUT_3 = LayoutSpec(
    layout_id="icici_sno_transactiondate_chequenumber_transactionremarks_withdrawal_deposit_balance",
    bank_key="icici",
    bank_markers=("ICICIBANK",),
    merge_statements=True,
    bank_name="ICICI Bank",
    columns={
        "date": (("transaction",),),
        "ref": (("chequenumber",), ("cheque", "number")),
        "narration": (("transaction", "remarks"), ("transactionremarks",), ("remarks",)),
        "debit": (("withdrawal",), ("withdrawalamount",), ("withdrawal", "amount")),
        "credit": (("deposit",), ("depositamount",), ("deposit", "amount")),
        "balance": (("balance",), ("balanceinr",), ("balance", "inr")),
    },
    text_columns=("date", "ref", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}\.\d{2}\.\d{4}$"),
    date_format="%d.%m.%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{1,2}$"),
    period_re=re.compile(r"fortheperiod([A-Za-z]+\d{1,2},\d{4})-([A-Za-z]+\d{1,2},\d{4})"),
    period_date_format="%B%d,%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
ICICI_LAYOUT_3.validate()


# ICICI_LAYOUT_1 shape plus a real "Value Date" column between "S No." and "Transaction Date":
# the extra word sits LEFT of the date title so it stays furniture (anchors expect text columns right
# of date); it makes the layout-1 header an unknown-column rejection, so this needs its own spec.
# Some files print dates "31,07,2023" (commas) and one-decimal amounts: date shape is wider than L1's,
# which also lets _rank's date-hit term hand comma-date files to this spec over L1.
# "Withdrawal"/"Deposit" print bare or as "... Amount"; "Balance (INR)" may keep "(INR)" on the same line.
ICICI_LAYOUT_4 = LayoutSpec(
    layout_id="icici_sno_valuedate_transactiondate_chequenumber_remarks_withdrawal_deposit_balance_vd",
    bank_key="icici",
    bank_markers=("ICICIBANK",),
    merge_statements=True,
    bank_name="ICICI Bank",
    columns={
        "date": (("transactiondate",), ("transaction", "date")),
        "ref": (("chequenumber",), ("cheque", "number")),
        "narration": (("transactionremarks",), ("transaction", "remarks")),
        "debit": (("withdrawalamount",), ("withdrawal", "amount"), ("withdrawal",)),
        "credit": (("depositamount",), ("deposit", "amount"), ("deposit",)),
        "balance": (("balanceinr",), ("balance", "inr"), ("balance",)),
    },
    text_columns=("date", "ref", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}[/,]\d{2}[/,]\d{4}$"),
    date_format="%d/%m/%Y|%d,%m,%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{1,2}$"),
    period_re=re.compile(r"^NOPERIOD(\d)(\d)$"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    zero_amount_is_empty=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
ICICI_LAYOUT_4.validate()


# Same column set as L1 ("S No. | Transaction Date | Cheque Number | Transaction Remarks | Withdrawal Amount (INR) |
# Deposit Amount (INR) | Balance (INR)") but the header prints the second title line left-shifted: "Date" lands under
# "Transaction" yet "Amount (INR)" sits ~3pt LEFT of "Withdrawal"/"Deposit", outside the wrap cluster, so the merged
# stream reads "amountinr withdrawal" (L3's own variant reads "withdrawal amountinr"). Dates dd.mm.yyyy. No printed
# summary and no B/F opening row: anchorless family, best attainable verdict is REVIEW.
ICICI_LAYOUT_5 = LayoutSpec(
    layout_id="icici_sno_transactiondate_chequenumber_remarks_amountinrfirst_wrap",
    bank_key="icici",
    bank_markers=("ICICIBANK",),
    merge_statements=True,
    bank_name="ICICI Bank",
    columns={
        "date": (("transaction", "date"), ("transaction",)),
        "ref": (("chequenumber",), ("cheque", "number")),
        "narration": (("transactionremarks",), ("transaction", "remarks")),
        "debit": (("amountinr", "withdrawal"), ("withdrawal", "amountinr"), ("withdrawal",)),
        "credit": (("amountinr", "deposit"), ("deposit", "amountinr"), ("deposit",)),
        "balance": (("balance", "inr"), ("balanceinr",), ("balance",)),
    },
    text_columns=("date", "ref", "narration"),
    band_left_pad={"narration": 60.0},   # remarks data starts ~x192 while the "Transaction Remarks" title sits at ~247
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}\.\d{2}\.\d{4}$"),
    date_format="%d.%m.%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{1,2}$"),
    period_re=re.compile(r"fortheperiod([A-Za-z]+\d{1,2},\d{4})-([A-Za-z]+\d{1,2},\d{4})"),
    period_date_format="%B%d,%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    header_wraps=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
ICICI_LAYOUT_5.validate()
