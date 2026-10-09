"""Union Bank of India layout configuration (fingerprint "s.no | date | transaction id | remarks | amount (rs.) |
balance (rs.)"): ONE amount column whose cells end in (Dr)/(Cr), balance carries (Cr)/(Dr), newest transaction first.
Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

UNION_LAYOUT_1 = LayoutSpec(
    layout_id="union_sno_date_transactionid_remarks_amount_balance",
    bank_key="union",
    bank_markers=("UNIONBANKOFINDIA",),
    merge_statements=True,
    bank_name="Union Bank of India",
    columns={
        "date": (("date",),),
        "ref": (("transactionid",), ("transaction", "id")),
        "narration": (("remarks",),),
        "amount": (("amountrs",), ("amount",)),
        "balance": (("balancers",), ("balance",)),
    },
    text_columns=("date", "ref", "narration"),
    band_left_pad={"narration": 90.0},
    debit_column="amount_dr",
    credit_column="amount_cr",
    single_amount_column="amount",
    balance_column="balance",
    row_order="reverse",
    merge_drcr_suffix=True,
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?: ?\((?:Cr|Dr)\))?$"),
    period_re=re.compile(r"StatementPeriod(\d{2}/\d{2}/\d{4})To(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
)
UNION_LAYOUT_1.validate()


# "Date | Remarks | Tran Id-1 | UTR Number | Instr. ID | Withdrawals | Deposits | Balance" export:
# dash dates, an empty money cell prints "-", plain balances. The Tran/UTR/Instr columns sit between
# Remarks and the money columns; only Tran Id is kept as ref (UTR/Instr ids are classified but unused).
UNION_LAYOUT_2 = LayoutSpec(
    layout_id="union_date_remarks_tranid_utrnumber_instrid_withdrawals_deposits_balance",
    bank_key="union",
    bank_markers=("UNIONBANKOFINDIA",),
    merge_statements=True,
    bank_name="Union Bank of India",
    columns={
        "date": (("date",),),
        "narration": (("remarks",),),
        "ref": (("tran", "id-1"), ("tranid1",), ("tranid-1",), ("tran", "id1"), ("tran", "id"), ("tranid",)),
        "utr": (("utr", "number"), ("utrnumber",)),
        "instr": (("instr.", "id"), ("instr", "id"), ("instrid",)),
        "debit": (("withdrawals",),),
        "credit": (("deposits",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref", "utr", "instr"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    empty_amount_marker="-",
    date_re=re.compile(r"^\d{2}[-/]\d{2}[-/]\d{4}$"),
    date_format="%d-%m-%Y|%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"StatementPeriodFrom-?(\d{2}/\d{2}/\d{4})To-?(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
    dates_monotonic_expected=False,
)
UNION_LAYOUT_2.validate()


# PARKED (Wave 4): this variant prints amounts truncated to ONE decimal ("1882.8(Dr)") while balances
# carry paise ("37289.49(Cr)") - the printed figures can never reconcile, so the layout is kept here as
# documentation only and is NOT registered. Verified-on only ~26% of its cluster (untruncated files).
# UNION_LAYOUT_1 shape but the printer emits "dd-mm-yyyy" dates and "Amount( )"/"Balance( )" titles;
# amounts keep the (Dr)/(Cr) suffix that carries the side. Same columns, different date shape, so the
# layout-1 header match cannot serve these files (its date_re rejects every row).
UNION_LAYOUT_3 = LayoutSpec(
    layout_id="union_sno_date_transactionid_remarks_amount_balance_dash",
    bank_key="union",
    bank_markers=("UNIONBANKOFINDIA",),
    merge_statements=True,
    bank_name="Union Bank of India",
    columns={
        "date": (("date",),),
        "ref": (("transactionid",), ("transaction", "id")),
        "narration": (("remarks",),),
        "amount": (("amountrs",), ("amount",)),
        "balance": (("balancers",), ("balance",)),
    },
    text_columns=("date", "ref", "narration"),
    band_left_pad={"narration": 90.0},
    debit_column="amount_dr",
    credit_column="amount_cr",
    single_amount_column="amount",
    balance_column="balance",
    row_order="auto",
    merge_drcr_suffix=True,
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{1,2}(?: ?\((?:Cr|Dr)\))?$"),
    period_re=re.compile(r"StatementPeriod(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
)
UNION_LAYOUT_3.validate()


# "SI | Date | Particulars | Chq Num | Withdrawal | Deposit | Balance" passbook print: a balance-only
# "Opening Balance" first row, "Cr" as a separate word after the balance, "Summary : Closing Balance :"
# totals line, period "STATEMENT OF ACCOUNT FOR THE PERIOD FROM <d-m-y> TO <d-m-y>".
UNION_LAYOUT_4 = LayoutSpec(
    layout_id="union_si_date_particulars_chqnum_withdrawal_deposit_balance",
    bank_key="union",
    bank_markers=("UNIONBANKOFINDIA",),
    merge_statements=True,
    bank_name="Union Bank of India",
    columns={
        "date": (("date",),),
        "narration": (("particulars",),),
        "ref": (("chq", "num"), ("chqnum",)),
        "debit": (("withdrawal",),),
        "credit": (("deposit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    opening_row_balance_only=True,
    merge_drcr_suffix=True,
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    date_format="%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?:\s*\(?(?i:cr|dr)\)?)?$"),
    closing_balance_re=re.compile(r"(?i)closingbalance:?([\d,]+\.\d{2})"),
    period_re=re.compile(r"(?i)periodfrom(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
)
UNION_LAYOUT_4.validate()


# "Tran Date | Tran Id | Remarks | Amount (Rs.) | Balance (Rs.)" export: same single-amount (Dr)/(Cr)
# family as layout-1 but without the serial column and with "Tran" titles; the transaction-id cell
# sits leftmost on the dated line and Remarks arrive on continuation lines. Period line prints
# "Statement Period : <d/m/Y> <h:m> <am/pm> ........ From -<d/m/Y> To <d/m/Y>".
UNION_LAYOUT_5 = LayoutSpec(
    layout_id="union_trandate_tranid_remarks_amount_balance",
    bank_key="union",
    bank_markers=("UNIONBANKOFINDIA",),
    merge_statements=True,
    bank_name="Union Bank of India",
    columns={
        "date": (("tran", "date"), ("trandate",)),
        "ref": (("tran", "id"), ("tranid",)),
        "narration": (("remarks",),),
        "amount": (("amountrs",), ("amount",)),
        "balance": (("balancers",), ("balance",)),
    },
    text_columns=("date", "narration"),
    band_left_pad={"narration": 90.0},
    debit_column="amount_dr",
    credit_column="amount_cr",
    single_amount_column="amount",
    balance_column="balance",
    row_order="reverse",
    merge_drcr_suffix=True,
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?: ?\((?:Cr|Dr)\))?$"),
    period_re=re.compile(r"From-?(\d{2}/\d{2}/\d{4})To(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    continuation_start="top",
)
UNION_LAYOUT_5.validate()
