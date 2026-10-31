"""SBI layout configuration (layout family F1, dominant fingerprint "txn date | value date | description | ref no./cheque |
debit | credit | balance"). Facts only; the machinery lives in statement_engine.extraction."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

SBI_TXN_VALUE_DESC_REF_DR_CR_BAL_ID = "sbi_txndate_valuedate_description_refcheque_debit_credit_balance"

SBI_LAYOUT_1 = LayoutSpec(
    layout_id=SBI_TXN_VALUE_DESC_REF_DR_CR_BAL_ID,
    bank_key="sbi",
    bank_markers=("STATEBANKOFINDIA",),
    merge_statements=True,
    bank_name="State Bank of India",
    columns={
        "date": (("txndate",), ("txn", "date")),
        "value_date": (("value",), ("valuedate",), ("value", "date")),   # "Value" / "Date" print on two lines; the first line carries "Value"
        "narration": (("description",), ("particulars",)),
        "ref": (("refnocheque",), ("refno", "cheque"), ("ref", "no", "cheque"), ("refno", "chequeno"), ("reference",)),
        "debit": (("debit",), ("debits",)),
        "credit": (("credit",), ("credits",)),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{1,2}[ -][A-Za-z]{3}(?:[ -]\d{2,4})?$"),  # "5 Jan 2023", "01-SEP-2021" or wrapped "10 Jan"
    date_tail_re=re.compile(r"^\d{4}$"),                           # ... and the year on the next line
    date_format="%d %b %Y|%d-%b-%Y|%d-%b-%y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"AccountStatementfrom(\d{1,2}[A-Za-z]{3}\d{4})to(\d{1,2}[A-Za-z]{3}\d{4})"),
    period_date_format="%d%b%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    end_markers=("PLEASEDONOTSHAREYOURATM", "THISISACOMPUTERGENERATEDSTATEMENT"),
    secondary_date_column="value_date",
    header_repeats=True,
    opening_balance_re=re.compile(r"Balanceason\d{1,2}[A-Za-z]{3}\d{4}:(?:\(cid:\d+\))?(-?[\d,]+\.\d{2})"),
    account_label="accountnumber",
    zero_amount_is_empty=True,
    band_left_pad={"narration": 55.0},   # "Description" title is centred; narration data starts ~45pt left of it
)
SBI_LAYOUT_1.validate()


# ---------------------------------------------------------------------------
# Wave-4 variants. Same SBI core-banking family, different printed column sets
# or date formats. Registered AFTER SBI_LAYOUT_1 so the original keeps priority.
# ---------------------------------------------------------------------------

# "Date | Details | Debit | Credit | Balance" — no value-date, no ref column.
SBI_LAYOUT_2 = LayoutSpec(
    layout_id="sbi_date_details_debit_credit_balance",
    bank_key="sbi",
    bank_markers=("STATEBANKOFINDIA",),
    merge_statements=True,
    bank_name="State Bank of India",
    columns={
        "date": (("date",),),
        "narration": (("details",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    band_left_pad={"narration": 72.0},   # "Details" title is centred; narration data starts ~x127 vs title ~193
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{1,2}[ -][A-Za-z]{3}(?:[ -]\d{2,4})?$"),
    date_tail_re=re.compile(r"^\d{4}$"),
    date_format="%d %b %Y|%d-%b-%Y|%d-%b-%y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}-?$"),   # overdrawn balances print a trailing minus ("109962.66-")
    # "Search for <later> to <earlier>" prints a reversed range in this variant: deliberately never match
    # (the period check then SKIPs instead of trusting a backwards window); "Balance as on" likewise prints the
    # post-first-row balance, so opening_balance_re is left unset and the reference check SKIPs.
    period_re=re.compile(r"(?!x)x"),
    period_date_format="%d%b%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    empty_amount_marker="-",
    row_order="auto",
    end_markers=("PLEASEDONOTSHAREYOURATM", "THISISACOMPUTERGENERATEDSTATEMENT"),
    header_repeats=True,
    account_label="accountnumber",
)
SBI_LAYOUT_2.validate()

# "Date | Details | Ref No./Cheque No. | Debit | Credit | Balance" — ref column present.
SBI_LAYOUT_3 = LayoutSpec(
    layout_id="sbi_date_details_refnocheque_debit_credit_balance",
    bank_key="sbi",
    bank_markers=("STATEBANKOFINDIA",),
    merge_statements=True,
    bank_name="State Bank of India",
    columns={
        "date": (("date",), ("datevaluedate",), ("date", "value", "date"), ("datevaluedat",)),
        "narration": (("details",), ("narration",)),
        "ref": (("refnocheque",), ("refno", "cheque"), ("ref", "nocheque"), ("refchequeno",), ("ref", "chequeno"), ("refcheque", "no")),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "ref"),
    band_left_pad={"narration": 72.0},   # "Details" title is centred; narration data starts ~x127 vs title ~193
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{1,2}[ -][A-Za-z]{3}(?:[ -]\d{2,4})?$"),
    date_tail_re=re.compile(r"^\d{4}$"),
    date_format="%d %b %Y|%d-%b-%Y|%d-%b-%y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}-?$"),   # overdrawn balances print a trailing minus ("109962.66-")
    # "Search for <later> to <earlier>" prints a reversed range in this variant: deliberately never match
    # (the period check then SKIPs instead of trusting a backwards window); "Balance as on" likewise prints the
    # post-first-row balance, so opening_balance_re is left unset and the reference check SKIPs.
    period_re=re.compile(r"(?!x)x"),
    period_date_format="%d%b%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    empty_amount_marker="-",
    row_order="auto",
    end_markers=("PLEASEDONOTSHAREYOURATM", "THISISACOMPUTERGENERATEDSTATEMENT"),
    header_repeats=True,
    account_label="accountnumber",
)
SBI_LAYOUT_3.validate()

# "Txn Date | Value Date | Description | Debit | Credit | Balance" — L1 without the ref column.
SBI_LAYOUT_4 = LayoutSpec(
    layout_id="sbi_txndate_valuedate_description_debit_credit_balance",
    bank_key="sbi",
    bank_markers=("STATEBANKOFINDIA",),
    merge_statements=True,
    bank_name="State Bank of India",
    columns={
        "date": (("txndate",),),
        "value_date": (("valuedate",), ("value",)),
        "narration": (("description",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "narration"),
    band_left_pad={"narration": 75.0},   # narration data starts ~x169 while the "Description" title sits at ~240
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}[-/]\d{2}[-/]\d{4}$"),
    date_format="%d-%m-%Y|%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}\s*(?i:(?:cr|dr))?\.?$"),
    merge_drcr_suffix=True,
    drcr_suffix_decoration=True,
    row_order="auto",
    period_re=re.compile(r"(?:AccountStatementfrom|Searchfor)(\d{1,2}-\d{2}-\d{4})to(\d{1,2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    empty_amount_marker="-",
    end_markers=("PLEASEDONOTSHAREYOURATM", "THISISACOMPUTERGENERATEDSTATEMENT"),
    secondary_date_column="value_date",
    header_repeats=True,
    # "Balance as on <dd-mm-yyyy>" here prints the statement-generation balance (a date after the period start),
    # not the opening balance: left unset so the reference check SKIPs instead of comparing against a wrong anchor.
    opening_balance_re=None,
    account_label="accountnumber",
)
SBI_LAYOUT_4.validate()

# "Txn Date | Value Date | Description | Cheque | Debit | Credit | Balance" — L4 with a standalone cheque column
# (its title makes L4 refuse on the unknown token, so it needs its own spec; all L4 params carry over).
SBI_LAYOUT_9 = LayoutSpec(
    layout_id="sbi_txndate_valuedate_description_cheque_debit_credit_balance",
    bank_key="sbi",
    bank_markers=("STATEBANKOFINDIA",),
    merge_statements=True,
    bank_name="State Bank of India",
    columns={
        "date": (("txndate",),),
        "value_date": (("valuedate",), ("value",)),
        "narration": (("description",),),
        "cheque": (("cheque",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "narration", "cheque"),
    band_left_pad={"narration": 52.0},   # "Description" title is centred; narration data starts ~45pt left of it
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}[-/]\d{2}[-/]\d{4}$"),
    date_format="%d-%m-%Y|%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}\s*(?i:(?:cr|dr))?\.?$"),
    merge_drcr_suffix=True,
    drcr_suffix_decoration=True,
    row_order="auto",
    period_re=re.compile(r"(?:AccountStatementfrom|Searchfor)(\d{1,2}-\d{2}-\d{4})to(\d{1,2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    empty_amount_marker="-",
    end_markers=("PLEASEDONOTSHAREYOURATM", "THISISACOMPUTERGENERATEDSTATEMENT"),
    secondary_date_column="value_date",
    header_repeats=True,
    opening_balance_re=None,
    account_label="accountnumber",
    continuation_amounts=True,
)
SBI_LAYOUT_9.validate()

# "Post Date | Value Date | Description | Debit | Credit | Balance" — dd-mm-yyyy, balance carries a fused Cr/Dr suffix.
SBI_LAYOUT_5 = LayoutSpec(
    layout_id="sbi_postdate_valuedate_description_cheque_debit_credit_balance",
    bank_key="sbi",
    bank_markers=("STATEBANKOFINDIA",),
    merge_statements=True,
    bank_name="State Bank of India",
    columns={
        "date": (("postdate",), ("post", "date"), ("post",)),
        "value_date": (("valuedate",), ("value",), ("value", "date")),
        "narration": (("description",), ("details",), ("narration",)),
        "cheque": (("cheque",), ("chqno",), ("chq", "no"), ("chgno",), ("chg", "no"), ("chequeno",), ("cheque", "no")),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "narration", "cheque"),
    band_left_pad={"narration": 45.0},   # narration data starts ~x143 while the "Description" title sits at ~182
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}[-/]\d{2}[-/]\d{2,4}$"),
    date_format="%d-%m-%Y|%d/%m/%y|%d-%m-%y|%d/%m/%Y",
    header_wraps=True,
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?i:(?:cr|dr))?\.?$"),
    row_order="auto",
    period_re=re.compile(r"Statementfrom:?(\d{2}-\d{2}-\d{4})To(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    opening_balance_re=re.compile(r"(?i)BROUGHTFORWARD:?(-?[\d,]+\.?\d*)CR"),
    closing_balance_re=re.compile(r"(?i)CLOSINGBALANCE(-?[\d,]+\.\d{2})CR"),
    anchor_full=True,
    end_markers=("PLEASEDONOTSHAREYOURATM", "THISISACOMPUTERGENERATEDSTATEMENT"),
    secondary_date_column="value_date",
    header_repeats=True,
    account_label="accountnumber",
)
SBI_LAYOUT_5.validate()

# "Txn Date | Value Date | Description | Ref No./Cheque | Branch | Debit | Credit | Balance" — L1 + branch column.
SBI_LAYOUT_6 = LayoutSpec(
    layout_id="sbi_txndate_valuedate_description_refcheque_branch_debit_credit_balance",
    bank_key="sbi",
    bank_markers=("STATEBANKOFINDIA",),
    merge_statements=True,
    bank_name="State Bank of India",
    columns={
        "date": (("txndate",),),
        "value_date": (("valuedate",), ("value",)),
        "narration": (("description",),),
        "ref": (("refnocheque",), ("refno", "cheque"), ("ref", "nocheque")),
        "branch": (("branch",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "narration", "ref", "branch"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"AccountStatementfrom(\d{1,2}[A-Za-z]{3}\d{4})to(\d{1,2}[A-Za-z]{3}\d{4})"),
    period_date_format="%d%b%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    end_markers=("PLEASEDONOTSHAREYOURATM", "THISISACOMPUTERGENERATEDSTATEMENT"),
    secondary_date_column="value_date",
    header_repeats=True,
    opening_balance_re=re.compile(r"Balanceason\d{1,2}[A-Za-z]{3}\d{4}:(?:\(cid:\d+\))?(-?[\d,]+\.\d{2})"),
    account_label="accountnumber",
)
SBI_LAYOUT_6.validate()

# "Txn | Value | Description | Ref | Branch | Debit | Credit | Balance" — short titles, yearless "d Mmm" dates.
SBI_LAYOUT_7 = LayoutSpec(
    layout_id="sbi_txn_value_description_ref_branch_debit_credit_balance",
    bank_key="sbi",
    bank_markers=("STATEBANKOFINDIA",),
    merge_statements=True,
    bank_name="State Bank of India",
    columns={
        "date": (("txn",),),
        "value_date": (("value",),),
        "narration": (("description",),),
        "ref": (("ref",),),
        "branch": (("branch",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "narration", "ref", "branch"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{1,2} [A-Za-z]{3}$"),
    date_format="%d %b %Y",
    year_from_period=True,
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    wrapped_amount_tokens=True,
    period_re=re.compile(r"AccountStatementfrom(\d{1,2}[A-Za-z]{3}\d{4})to(\d{1,2}[A-Za-z]{3}\d{4})"),
    period_date_format="%d%b%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    end_markers=("PLEASEDONOTSHAREYOURATM", "THISISACOMPUTERGENERATEDSTATEMENT"),
    secondary_date_column="value_date",
    header_repeats=True,
    opening_balance_re=re.compile(r"Balanceason\d{1,2}[A-Za-z]{3}\d{4}:(?:\(cid:\d+\))?(-?[\d,]+\.\d{2})"),
    account_label="accountnumber",
)
SBI_LAYOUT_7.validate()


# "Txn Date | Value Date | Description | Ref/Cheque | Debit | Credit | Balance" — dd-mm-yy dates, Cr/Dr suffix words.
SBI_LAYOUT_8 = LayoutSpec(
    layout_id="sbi_txndate_valuedate_description_refcheque_debit_credit_balance_ddmmyy",
    bank_key="sbi",
    bank_markers=("STATEBANKOFINDIA",),
    merge_statements=True,
    bank_name="State Bank of India",
    columns={
        "date": (("txndate",),),
        "value_date": (("valuedate",), ("value",)),
        "narration": (("description",),),
        "ref": (("refcheque",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{2}$"),
    date_format="%d-%m-%y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}\s*(?i:(?:cr|dr))?\.?$"),
    merge_drcr_suffix=True,
    drcr_suffix_decoration=True,
    empty_amount_marker="-",
    row_order="auto",
    # no period range or opening anchor is printed in this variant ("Statement of Account Date" is the print date):
    # the reference and period checks SKIP rather than trust a wrong anchor.
    period_re=re.compile(r"(?!x)x"),
    period_date_format="%d-%m-%y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    end_markers=("PLEASEDONOTSHAREYOURATM", "THISISACOMPUTERGENERATEDSTATEMENT"),
    secondary_date_column="value_date",
    header_repeats=True,
    account_label="accountnumber",
    band_left_pad={"narration": 55.0},   # narration data starts ~x156 while the centred "Description" title sits at ~205
)
SBI_LAYOUT_8.validate()


# ---------------------------------------------------------------------------
# W10-1: mPassbook / "Account Summary" export — a HEADERLESS table: no column
# titles print, only a lone "Balance" word above the grid. Column geometry comes
# from the dated line itself (implicit_header). The txn-type word ("DEP TFR",
# "WDL TFR", ...) prints in the narration band one line ABOVE the dated line and
# is attached by the implicit-header prefix rule. Anchors: page-0 "Clear Balance"
# summary + the trailing "Statement Summary" block (Brought Forward / Dr Count /
# Cr Count / Total Debits / Total Credits + a bare closing "..CR" line).
SBI_LAYOUT_10_ID = "sbi_txndate_valuedate_description_ref_debit_credit_balance_mpassbook"
SBI_LAYOUT_10 = LayoutSpec(
    layout_id=SBI_LAYOUT_10_ID,
    bank_key="sbi",
    bank_markers=("STATEBANKOFINDIA", "SBIN0"),
    bank_name="State Bank of India",
    # title spellings never print; entries exist only to satisfy column declarations
    columns={
        "date": (("\x00date\x00",),),
        "value_date": (("\x00valuedate\x00",),),
        "narration": (("\x00narration\x00",),),
        "ref": (("\x00ref\x00",),),
        "debit": (("\x00debit\x00",),),
        "credit": (("\x00credit\x00",),),
        "balance": (("\x00balance\x00",),),
    },
    text_columns=("date", "value_date", "narration", "ref"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    implicit_header=("date", "value_date", "narration", "ref", "debit", "credit", "balance"),
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    empty_amount_marker="-",
    period_re=re.compile(r"STATEMENTFROM:(\d{2}-\d{2}-\d{4})TO(\d{2}-\d{2}-\d{4})"),
    period_date_format="%d-%m-%Y",
    # last-page "Statement Summary : <from> To <to>" labels across two lines, then
    # a 5-number line (opening, dr count, cr count, total debits, total credits)
    # and a separate closing "..CR" line; five printed fields anchor both ends.
    summary_marker="STATEMENTSUMMARY",
    summary_label_text="broughtforwarddrcountcrcounttotaldebitstotalcreditsclosingbalance",
    summary_fields=("opening", "dr_count", "cr_count", "debits", "credits", "closing"),
    anchor_full=True,
    end_markers=("PLEASEDONOTSHAREYOURATM", "THISISACOMPUTERGENERATEDSTATEMENT"),
    page_footer_markers=("PAGENO.",),
    secondary_date_column="value_date",
    continuation_start="top",
    ifsc_re=re.compile(r"SBIN0\d{6}"),
    account_label="accountnumber",
    merge_statements=True,
    row_order="auto",
)
SBI_LAYOUT_10.validate()
