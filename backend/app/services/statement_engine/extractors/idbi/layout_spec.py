"""IDBI Bank layouts. L1 shares Bank of Baroda's "Date | Particulars | Chq.No. | Withdrawals | Deposits | Balance"
header verbatim — it is claimed only on IDBI evidence (brand text or the Slice 2 detector). L2 is the e-statement
"S.No | Txn Date | Value Date | Description | Cheque No | Withdrawals(Dr) | Deposits(Cr) | Balance(INR)" with the txn
date cell carrying a time suffix. Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

IDBI_LAYOUT_1 = LayoutSpec(
    layout_id="idbi_date_particulars_chqno_withdrawals_deposits_balance",
    bank_key="idbi",
    bank_markers=("IDBIBANK",),
    merge_statements=True,
    bank_name="IDBI Bank",
    columns={
        "date": (("date",),),
        "narration": (("particulars",),),
        "ref": (("chq.no.",), ("chqno",), ("chq", "no")),
        "debit": (("withdrawals",),),
        "credit": (("deposits",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}[-/]\d{2}[-/]\d{4}$"),
    date_format="%d/%m/%Y|%d-%m-%Y",
    amount_re=re.compile(r"^-?(?:[\d,]+(?:\.\d{1,2})?|\.\d{1,2})(?: ?(?:Cr|Dr))?$"),
    period_re=re.compile(r"(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=False,
    merge_drcr_suffix=True,
    opening_row_balance_only=True,
    zero_amount_is_empty=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
IDBI_LAYOUT_1.validate()

IDBI_LAYOUT_2 = LayoutSpec(
    layout_id="idbi_sno_txndate_valuedate_description_chequeno_withdrawals_deposits_balance",
    bank_key="idbi",
    bank_markers=("IDBIBANK",),
    merge_statements=True,
    bank_name="IDBI Bank",
    columns={
        "date": (("txndate",), ("txn", "date")),
        "value_date": (("valuedate",), ("value", "date")),
        "narration": (("description",),),
        "ref": (("chequeno",), ("cheque", "no")),
        "debit": (("withdrawals",),),
        "credit": (("deposits",),),
        "balance": (("balance",), ("balanceinr",), ("balance", "inr")),
    },
    text_columns=("date", "value_date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    secondary_date_column="value_date",
    header_repeats=True,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
)
IDBI_LAYOUT_2.validate()


# L3 (PARKED - not registered): e-statement "Srl | Txn Date | Value Date | Description | Cheque No | CR/DR | CCY | Amount (INR) |
# Balance (INR)" - "Cheque No"/"CC Y" title halves print on a second header line, the txn-date cell carries
# an "hh:mm:ss AM" time tail, the serial column sits left of the date data and a single Amount column is
# sided by the CR/DR marker. Newest-first ordering observed in corpus.
IDBI_LAYOUT_3 = LayoutSpec(
    layout_id="idbi_srl_txndate_valuedate_description_chequeno_crdr_ccy_amountinr_balanceinr",
    bank_key="idbi",
    bank_markers=("IDBIBANK", "IDBI.COM"),
    merge_statements=True,
    bank_name="IDBI Bank",
    columns={
        "date": (("txn", "date"), ("txndate",)),
        "value_date": (("value", "date"), ("valuedate",)),
        "narration": (("description",),),
        "ref": (("cheque", "no"), ("chequeno",), ("cheque",)),
        "drcr": (("cr", "dr"), ("crdr",), ("cr", "/", "dr")),
        "ccy": (("cc", "y"), ("ccy",), ("cc",)),
        "amount": (("amount", "inr"), ("amountinr",), ("amount",)),
        "balance": (("balance", "inr"), ("balanceinr",), ("balance",)),
    },
    text_columns=("date", "value_date", "narration", "ref", "drcr", "ccy"),
    debit_column="amount_dr",
    credit_column="amount_cr",
    single_amount_column="amount",
    side_marker_column="drcr",
    balance_column="balance",
    secondary_date_column="value_date",
    band_left_pad={"drcr": 60.0},
    continuation_amounts=True,
    header_lines=3,               # "Cheque"/"CC" title halves print one line above the main line, "No"/"Y" one below
    header_wraps=True,
    date_left_pad=30.0,
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_tail_re=re.compile(r"^(\d{1,2}:\d{2}:\d{2}|[AP]M|[ap]m)$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"(?i)(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
)
IDBI_LAYOUT_3.validate()

# PARKED: normalize.py's side-marker regex `\(?(cr|dr)\)?$` does not accept this family's period-suffixed
# `Dr.`/`Cr.` markers -> every row fails "amount cell carries no Dr/Cr marker". Engine gap: marker regex needs
# a `\.?$`. Spec kept defined for study; do NOT register until the engine accepts period-suffixed markers.


# L4: passbook "Date | Particulars | Cheque No | Debit | Credit | Closing Balance" - `dd/mm/yy` dates,
# balances carry a split trailing "CR"/"DR" word, opening prints as "Opening Balance As On <date> :<amt> CR".
IDBI_LAYOUT_4 = LayoutSpec(
    layout_id="idbi_date_particulars_chequeno_debit_credit_closingbalance",
    bank_key="idbi",
    bank_markers=("IDBIBANK", "IDBI.COM"),
    merge_statements=True,
    bank_name="IDBI Bank",
    columns={
        "date": (("date",),),
        "narration": (("particulars",),),
        "ref": (("cheque", "no"), ("chequeno",), ("cheque",)),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("closing", "balance"), ("closingbalance",), ("balance",)),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{2}$"),
    date_format="%d/%m/%y",
    amount_re=re.compile(r"^-?(?:[\d,]+(?:\.\d{1,2})?|\.\d{1,2})(?:\s*(?i:cr|dr))?$"),
    merge_drcr_suffix=True,
    period_re=IDBI_LAYOUT_1.period_re,
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    opening_balance_re=re.compile(r"(?i)OpeningBalanceAsOn\d{2}/\d{2}/\d{4}:?(-?[\d,]+\.\d{1,2})"),
    header_repeats=True,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
)
IDBI_LAYOUT_4.validate()

# L5: passbook "Date | Particulars | Chq No. | Chq Date | Debit | Credit | Balance" - `dd-mm-yyyy` dates,
# balances carry a merged "Cr" suffix, "Opening Balance"/"Closing Balance" print as undated lines inside the
# table region (closing line also carries the period totals before the closing figure).
IDBI_LAYOUT_5 = LayoutSpec(
    layout_id="idbi_date_particulars_chqno_chqdate_debit_credit_balance",
    bank_key="idbi",
    bank_markers=("IDBIBANK", "IDBI.COM"),
    merge_statements=True,
    bank_name="IDBI Bank",
    columns={
        "date": (("date",),),
        "narration": (("particulars",),),
        "ref": (("chq", "no"), ("chqno",), ("chq",)),
        "chqdate": (("chq", "date"), ("chqdate",)),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref", "chqdate"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?(?:[\d,]+(?:\.\d{1,2})?|\.\d{1,2})(?:\s*(?i:cr|dr))?$"),
    period_re=IDBI_LAYOUT_1.period_re,
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    opening_balance_re=re.compile(r"(?i)OpeningBalance(-?[\d,]+\.\d{1,2})"),
    closing_balance_re=re.compile(r"(?i)ClosingBalance(?:[\d,]+\.\d{1,2})*(-?[\d,]+\.\d{1,2})Cr"),
    anchor_full=True,
    end_markers=("^CLOSINGBALANCE",),
    header_repeats=True,
    continuation_start="top",
    row_order="auto",
    dates_monotonic_expected=False,
)
IDBI_LAYOUT_5.validate()
