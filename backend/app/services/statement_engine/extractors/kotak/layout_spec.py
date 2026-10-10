"""Kotak Mahindra Bank layout configuration (dominant fingerprint "date | transaction details | cheque/reference# |
debit | credit | balance"; signed amounts, a dated OPENING BALANCE row). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

KOTAK_LAYOUT_1 = LayoutSpec(
    layout_id="kotak_date_transactiondetails_chequereference_debit_credit_balance",
    bank_key="kotak",
    bank_markers=("KOTAKMAHINDRA",),
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
    bank_markers=("KOTAKMAHINDRA",),
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


# "Date | Narration | Chq/Ref No | Withdrawal (Dr)/ Deposit (Cr) | Balance": ONE money column shared by
# both sides - "Deposit (Cr)" wraps to a second header line, each cell carries its (Dr)/(Cr) suffix and
# so does the balance. Dates dd-mm-yyyy; "Period : dd-mm-yyyy to dd-mm-yyyy".
KOTAK_LAYOUT_4 = LayoutSpec(
    layout_id="kotak_date_narration_chqrefno_amountdrcr_balancecr",
    bank_key="kotak",
    bank_markers=("KOTAKMAHINDRA",),
    merge_statements=True,
    bank_name="Kotak Mahindra Bank",
    columns={
        "date": (("date",),),
        "narration": (("narration",),),
        "ref": (("chqrefno",), ("chq", "ref", "no"), ("chq", "ref")),
        "amount": (("withdrawal", "dr"), ("withdrawaldr",)),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="amount_dr",
    credit_column="amount_cr",
    single_amount_column="amount",
    merge_drcr_suffix=True,
    left_aligned_amounts=True,
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}\s*\(?(?i:cr|dr)\)?$"),
    period_re=re.compile(r"(?i)period:(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    opening_balance_re=re.compile(r"(?i)OpeningBalance:(-?[\d,]+\.\d{2})"),
    closing_balance_re=re.compile(r"(?i)ClosingBalance:(-?[\d,]+\.\d{2})"),
    anchor_full=True,
    header_repeats=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
KOTAK_LAYOUT_4.validate()


# "# | TRANSACTION DATE | VALUE DATE | TRANSACTION DETAILS | CHQ / REF NO. | DEBIT/CREDIT(Rs) |
# BALANCE(Rs)": the money column prints an attached +/- sign; dates "d Mon yyyy"; an "OPENING x"
# figure sits at the bottom of each page under the balance column.
KOTAK_LAYOUT_5 = LayoutSpec(
    layout_id="kotak_hash_transactiondate_valuedate_transactiondetails_chqrefno_debitcredit_balance",
    bank_key="kotak",
    bank_markers=("KOTAKMAHINDRA",),
    merge_statements=True,
    bank_name="Kotak Mahindra Bank",
    columns={
        "date": (("transactiondate",), ("transaction", "date")),
        "value_date": (("valuedate",), ("value", "date")),
        "narration": (("transactiondetails",), ("transaction", "details")),
        "ref": (("chqrefno",), ("chq", "ref", "no"), ("chq", "ref")),
        "amount": (("debitcredit",), ("debit", "credit"), ("debit", "/", "credit")),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "narration", "ref"),
    debit_column="amount_dr",
    credit_column="amount_cr",
    single_amount_column="amount",
    merge_sign_prefix=True,
    balance_column="balance",
    date_re=re.compile(r"^\d{1,2} [A-Za-z]{3} \d{4}$"),
    date_format="%d %b %Y",
    amount_re=re.compile(r"^[+-]?[\d,]+\.\d{2}$"),
    opening_balance_re=re.compile(r"(?i)opening(-?[\d,]+\.\d{2})"),
    period_re=re.compile(r"(\d{1,2}[A-Za-z]{3}\d{4})-(\d{1,2}[A-Za-z]{3}\d{4})"),
    period_date_format="%d%b%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    secondary_date_column="value_date",
    header_repeats=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
KOTAK_LAYOUT_5.validate()


# "# | Date | Description | Chq/Ref. No. | Withdrawal (Dr.) | Deposit (Cr.) | Balance" passbook print:
# a dash-filled "Opening Balance" balance-only row, plain amounts in two columns, dates "d Mon yyyy".
KOTAK_LAYOUT_6 = LayoutSpec(
    layout_id="kotak_hash_date_description_chqrefno_withdrawaldr_depositcr_balance",
    bank_key="kotak",
    bank_markers=("KOTAKMAHINDRA",),
    merge_statements=True,
    bank_name="Kotak Mahindra Bank",
    columns={
        "date": (("date",),),
        "narration": (("description",),),
        "ref": (("chqrefno",), ("chq", "ref", "no"), ("chq", "ref")),
        "debit": (("withdrawal", "dr"), ("withdrawaldr",)),
        "credit": (("deposit", "cr"), ("depositcr",)),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    opening_row_balance_only=True,
    left_aligned_amounts=True,
    empty_amount_marker="-",
    date_re=re.compile(r"^\d{1,2} [A-Za-z]{3} \d{4}$"),
    date_format="%d %b %Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(\d{1,2}[A-Za-z]{3}\d{4})-(\d{1,2}[A-Za-z]{3}\d{4})"),
    period_date_format="%d%b%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
KOTAK_LAYOUT_6.validate()


# "# | TRANSACTION | TRANSACTION DETAILS | CHQ / REF NO. | DEBIT(Rs) | CREDIT(Rs) | BALANCE(Rs)": the
# date column is literally titled TRANSACTION, debit cells carry a decorative leading "-", credit cells
# a decorative "+"; an "OPENING x" figure prints at the bottom of each page.
KOTAK_LAYOUT_7 = LayoutSpec(
    layout_id="kotak_hash_transaction_transactiondetails_chqrefno_debit_credit_balance_signed",
    bank_key="kotak",
    bank_markers=("KOTAKMAHINDRA",),
    merge_statements=True,
    bank_name="Kotak Mahindra Bank",
    columns={
        "date": (("transaction",),),
        "narration": (("transactiondetails",), ("transaction", "details")),
        "ref": (("chqrefno",), ("chq", "ref", "no"), ("chq", "ref")),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    sign_is_decoration=True,
    date_re=re.compile(r"^\d{1,2} [A-Za-z]{3} \d{4}$"),
    date_format="%d %b %Y",
    amount_re=re.compile(r"^[+-]?[\d,]+\.\d{2}$"),
    opening_balance_re=re.compile(r"(?i)opening(-?[\d,]+\.\d{2})"),
    period_re=re.compile(r"(\d{1,2}[A-Za-z]{3}\d{4})-(\d{1,2}[A-Za-z]{3}\d{4})"),
    period_date_format="%d%b%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
KOTAK_LAYOUT_7.validate()


# K5 without the ref column: "# | TRANSACTION DATE | VALUE DATE | TRANSACTION DETAILS | DEBIT/CREDIT(Rs) |
# BALANCE(Rs)" (9-file cluster, cheap reuse).
KOTAK_LAYOUT_8 = LayoutSpec(
    layout_id="kotak_hash_transactiondate_valuedate_transactiondetails_debitcredit_balance",
    bank_key="kotak",
    bank_markers=("KOTAKMAHINDRA",),
    merge_statements=True,
    bank_name="Kotak Mahindra Bank",
    columns={
        "date": (("transactiondate",), ("transaction", "date")),
        "value_date": (("valuedate",), ("value", "date")),
        "narration": (("transactiondetails",), ("transaction", "details")),
        "amount": (("debitcredit",), ("debit", "credit"), ("debit", "/", "credit")),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "narration"),
    debit_column="amount_dr",
    credit_column="amount_cr",
    single_amount_column="amount",
    merge_sign_prefix=True,
    balance_column="balance",
    date_re=re.compile(r"^\d{1,2} [A-Za-z]{3} \d{4}$"),
    date_format="%d %b %Y",
    amount_re=re.compile(r"^[+-]?[\d,]+\.\d{2}$"),
    opening_balance_re=re.compile(r"(?i)opening(-?[\d,]+\.\d{2})"),
    period_re=re.compile(r"(\d{1,2}[A-Za-z]{3}\d{4})-(\d{1,2}[A-Za-z]{3}\d{4})"),
    period_date_format="%d%b%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    secondary_date_column="value_date",
    header_repeats=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
KOTAK_LAYOUT_8.validate()


# "Sl. No. | Date | Description | Chq / Ref number | Amount | Dr / Cr | Balance | Dr / Cr": one money
# column, the side marker in its own column after it, signed balance with a trailing side marker.
KOTAK_LAYOUT_9 = LayoutSpec(
    layout_id="kotak_slno_date_description_chqrefnumber_amount_drcr_balance_drcr",
    bank_key="kotak",
    bank_markers=("KOTAKMAHINDRA",),
    merge_statements=True,
    bank_name="Kotak Mahindra Bank",
    columns={
        "date": (("date",),),
        "narration": (("description",),),
        "ref": (("chqrefnumber",), ("chq", "ref", "number"), ("chq", "ref")),
        "amount": (("amount",),),
        "drcr": (("drcr",), ("dr", "cr")),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref", "drcr"),
    debit_column="amount_dr",
    credit_column="amount_cr",
    single_amount_column="amount",
    side_marker_column="drcr",
    band_left_pad={"drcr": 100.0},
    continuation_amounts=True,
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?:\s+(?i:cr|dr))?$"),
    period_re=re.compile(r"(?i)from(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
)
KOTAK_LAYOUT_9.validate()
