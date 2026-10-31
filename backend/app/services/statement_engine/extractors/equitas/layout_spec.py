"""Equitas Small Finance Bank layout ("Date | Reference No/Cheque No | Narration | Withdrawal | Deposit |
Closing Balance" with an "INR" sub-label line under the money columns). Dates are ISO yyyy-mm-dd; the
narration column wraps into single-word continuation lines; the statement period line reads
"Statement for the period from dd-Mmm-yyyy to dd-Mmm-yyyy"; the table ends at "END OF THE STATEMENT".
Brand "EQUITAS SMALL FINANCE BANK LIMITED" prints in the page footer. Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

EQUITAS_LAYOUT_1 = LayoutSpec(
    layout_id="equitas_date_referencenochequeno_narration_withdrawal_deposit_closingbalance",
    bank_key="equitas_sfb",
    bank_name="Equitas Small Finance Bank",
    bank_markers=("EQUITASSMALLFINANCEBANK",),
    columns={
        "date": (("date",),),
        "ref": (("referencenochequeno",),),
        "narration": (("narration",),),
        "debit": (("withdrawal",),),
        "credit": (("deposit",),),
        "balance": (("closingbalance",),),
    },
    text_columns=("date", "ref", "narration"),
    band_left_pad={"narration": 20.0},   # narration data starts ~x210, left of the "Narration" title's left edge
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{4}-\d{2}-\d{2}$|^\d{2}-[A-Za-z]{3}-\d{4}$"),
    date_format="%Y-%m-%d|%d-%b-%Y",
    amount_re=re.compile(r"^-?[\d,]+(?:\.\d{2})?$"),
    period_re=re.compile(r"(\d{2}-[A-Za-z]{3}-\d{4})to(\d{2}-[A-Za-z]{3}-\d{4})"),
    period_date_format="%d-%b-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    merge_statements=True,
    end_markers=("ENDOFTHESTATEMENT",),
    continuation_start="top",
    row_order="auto",
)
EQUITAS_LAYOUT_1.validate()


EQUITAS_LAYOUT_2 = LayoutSpec(
    # "STATEMENT OF ACCOUNT" export: Tran Date|Value Date|Ref|Description|Debits|Credits|Balance;
    # dd-MMM-yy dates; a dated "B/F ..." opening row; ends at "Statement Summary:" + "******END OF STATEMENT******".
    layout_id="equitas_trandate_valuedate_ref_description_debits_credits_balance",
    bank_key="equitas_sfb",
    bank_name="Equitas Small Finance Bank",
    bank_markers=("EQUITASSMALLFINANCEBANK",),
    columns={
        "date": (("tran", "date"), ("trandate",)),
        "valuedate": (("value", "date"), ("valuedate",)),
        "ref": (("ref",),),
        "narration": (("description",),),
        "debit": (("debits",),),
        "credit": (("credits",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "valuedate", "ref", "narration"),
    secondary_date_column="valuedate",
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-[A-Za-z]{3}-\d{2}$"),
    date_format="%d-%b-%y",
    amount_re=re.compile(r"^-?[\d,]*\.\d{2}$"),
    period_re=re.compile(r"(?i)period:?(\d{2}-[A-Za-z]{3}-\d{2})to(\d{2}-[A-Za-z]{3}-\d{2})"),
    period_date_format="%d-%b-%y",
    summary_marker="STATEMENTSUMMARY",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    opening_row_marker="B/F",
    zero_amount_is_empty=True,
    # the Statement Summary value row merges columns without separators when squashed;
    # no closing regex can be written safely -> single-ended anchor on the B/F row
    anchor_full=False,
    end_markers=("ENDOFSTATEMENT", "STATEMENTSUMMARY"),
    continuation_start="top",
    row_order="auto",
)
EQUITAS_LAYOUT_2.validate()

EQUITAS_LAYOUT_3 = LayoutSpec(
    # Relationship-statement export: wrapped header "Date of TXN | Value date of TXN | Reference or cheque no |
    # Narration | Debit (`) | Credit (`) | Balance (`)"; dd/mm/yyyy dates; undated OPENING BALANCE row; no
    # printed closing (single-ended anchor).
    layout_id="equitas_dateoftxn_valuedateof_referenceorchequeno_narration_debit_credit_balance",
    bank_key="equitas_sfb",
    bank_name="Equitas Small Finance Bank",
    bank_markers=("EQUITASSMALLFINANCEBANK",),
    columns={
        "date": (("dateoftxn",),),
        "valuedate": (("valuedateof", "txn"), ("valuedateoftxn",)),
        "ref": (("referenceor", "chequeno"), ("referenceorchequeno",)),
        "narration": (("narration",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "valuedate", "ref", "narration"),
    band_left_pad={"narration": 46.0},   # narration data starts ~x247 vs centred "Narration" title ~288
    secondary_date_column="valuedate",
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]*\.\d{2}$"),
    period_re=re.compile(r"(?i)from(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    header_wraps=True,
    opening_balance_re=re.compile(r"(?i)OPENINGBALANCE(-?[\d,]*\.\d{2})"),
    continuation_start="top",
    row_order="auto",
)
EQUITAS_LAYOUT_3.validate()
