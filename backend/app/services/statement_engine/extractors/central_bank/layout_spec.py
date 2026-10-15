"""Central Bank of India layouts. Facts only.

CBI-L1 ("Post Date | Value Date | Branch Code | Cheque Number | Account Description | Debit | Credit |
Balance"): the header prints on two lines -- "Post Date / Value / Branch / Cheque / Account Description /
Debit / Credit / Balance" with "Date / Code / Number" on the sub-line. Rows are dd/dd/dddd post + value
dates, a 5-digit branch code, an optional cheque number, narration, one money cell and a balance that
carries a trailing Cr/Dr suffix fused into the same cell ("9999.99 CR"). Statement period line:
"STATEMENT OF ACCOUNT from dd/dd/dddd to dd/dd/dddd"; the table ends at "END OF STATEMENT FROM
INTERNET BANKING". Brand "CENTRAL BANK OF INDIA" prints on every statement.
"""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

CBI_LAYOUT_1 = LayoutSpec(
    layout_id="central_bank_postdate_value_branch_cheque_accountdescription_debit_credit_balance",
    bank_key="central_bank",
    bank_name="Central Bank of India",
    bank_markers=("CENTRALBANKOFINDIA",),
    columns={
        "date": (("postdate",), ("post", "date")),
        "valuedate": (("value",), ("value", "date"), ("date",)),
        "branch": (("branch",), ("code",)),
        "cheque": (("cheque",), ("number",)),
        "narration": (("accountdescription",), ("description",)),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "valuedate", "branch", "cheque", "narration"),
    secondary_date_column="valuedate",
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?: ?\(?[Cc][Rr]\)?\.?| ?\(?[Dd][Rr]\)?\.?)?$"),
    period_re=re.compile(r"(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    merge_statements=True,
    merge_drcr_suffix=True,
    end_markers=("ENDOFSTATEMENTFROMINTERNETBANKING",),
    row_order="auto",
)
CBI_LAYOUT_1.validate()

# CBI-L2 adds a TRANSACTION column between Cheque and the description
# ("postdate value branch cheque transaction description debit credit balance").
CBI_LAYOUT_2 = LayoutSpec(
    layout_id="central_bank_postdate_value_branch_cheque_transaction_description_debit_credit_balance",
    bank_key="central_bank",
    bank_name="Central Bank of India",
    bank_markers=("CENTRALBANKOFINDIA",),
    columns={
        "date": (("postdate",), ("post", "date")),
        "valuedate": (("value",), ("value", "date"), ("date",)),
        "branch": (("branch",), ("code",)),
        "cheque": (("cheque",), ("number",)),
        "narration": (("transactiondescription",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "valuedate", "branch", "cheque", "narration"),
    secondary_date_column="valuedate",
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?: ?\(?[Cc][Rr]\)?\.?| ?\(?[Dd][Rr]\)?\.?)?$"),
    period_re=re.compile(r"(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    merge_statements=True,
    merge_drcr_suffix=True,
    end_markers=("ENDOFSTATEMENTFROMINTERNETBANKING",),
    row_order="auto",
)
CBI_LAYOUT_2.validate()

# CBI-L3 ("Value | Post | Details | Chq.No. | Debit | Credit | Balance"): the branch-portal
# export prints 'Value / Post' on one line, the remaining titles on the next, and a lone
# 'Date / Date' wrap line underneath. dd/dd/dd dates, '-' empty cheque cell, balance fused
# with a Cr suffix, and a 'BROUGHT FORWARD : <amt>Cr' opening line at the table top. No
# closing label prints -> single-ended opening anchor.
CBI_LAYOUT_3 = LayoutSpec(
    layout_id="central_bank_value_post_details_chqno_debit_credit_balance",
    bank_key="central_bank",
    bank_name="Central Bank of India",
    bank_markers=("CENTRALBANKOFINDIA",),
    columns={
        "date": (("value",), ("value", "date"), ("valuedate",)),
        "valuedate": (("post",), ("post", "date"), ("postdate",)),
        "narration": (("details",),),
        "cheque": (("chqno",), ("chq", "no"), ("chq", "no.")),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "valuedate", "narration", "cheque"),
    secondary_date_column="valuedate",
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{2}$"),
    date_format="%d/%m/%y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?: ?\(?[Cc][Rr]\)?\.?| ?\(?[Dd][Rr]\)?\.?)?$"),
    period_re=re.compile(r"(?i)statementfrom(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    header_wraps=True,
    empty_amount_marker="-",
    merge_drcr_suffix=True,
    monospace_text=True,
    opening_balance_re=re.compile(r"(?i)broughtforward:?([\d,]+\.\d{2})cr"),
    end_markers=("ENDOFSTATEMENT",),
    row_order="auto",
)
CBI_LAYOUT_3.validate()


# CBI-L4 (n1): account-summary statement ("Post Date | Value Date | Branch Co | Journal No | Branch Name |
# City | Zone Name | Cheque | Mode of Remitta[nce] | Account Description | Debit | Credit | Balance |
# Limit Sanctioned | Drawing Amount | Hold Amount") - the 15 titles spread over THREE visual lines with
# mid-word splits ("Valu|e|Date", "Bra|nch|Co", "Ch|equ|e", "Drawin|g|Amount", "Sanctio|ned"); the date
# title sits on the middle line, money titles on the top line. `header_lines=3` merges them by horizontal
# overlap; every printed column must be declared so the merged view completes with no unknown token.
# Data rows print the date split inside the cell ("11/11" + "/2023" tail joins via date_tail_re) and the
# money cell on the continuation line (continuation_amounts). The three rightmost printed columns
# (limit/drawing/hold) are declared for header completeness only - their cells sit past the balance edge
# and are ignored. dd/mm/yy-style rows; balances carry CR/DR (merged). Anchors: none printed -> REVIEW.
CBI_LAYOUT_4 = LayoutSpec(
    layout_id="central_bank_postdate_valuedate_branchco_journal_branchname_city_zone_cheque_mode_description_15col",
    bank_key="central_bank",
    bank_name="Central Bank of India",
    bank_markers=("CENTRALBANKOFINDIA",),
    columns={
        "date": (("post", "date"), ("postdate",)),
        "valuedate": (("valu", "e", "date"), ("value", "date"), ("valuedate",), ("value",), ("date",)),
        "branchcode": (("bra", "nch", "co"), ("branch", "co"), ("branch", "code")),
        "journalno": (("journal", "no"), ("journalno",)),
        "branchname": (("branch", "name"), ("branchname",)),
        "city": (("city",),),
        "zonename": (("zone", "name"), ("zonename",)),
        "chequeno": (("ch", "equ", "e"), ("cheque",), ("cheque", "no")),
        "mode": (("mode", "of", "remitta"), ("mode", "of"), ("mode",)),
        "narration": (("account", "description"), ("description",), ("accountdescription",)),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
        "limit": (("limit", "sanctio", "ned"), ("limit",)),
        "drawing": (("drawin", "g", "amount"), ("drawing", "amount")),
        "hold": (("hold", "amount"),),
    },
    text_columns=("date", "valuedate", "branchcode", "journalno", "branchname", "city", "zonename",
                  "chequeno", "mode", "narration"),
    secondary_date_column="valuedate",
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    header_lines=3,
    header_repeats=True,
    merge_statements=True,
    merge_drcr_suffix=True,
    continuation_amounts=True,
    date_tail_re=re.compile(r"^/\d{2,4}$"),
    band_left_pad={"narration": 20.0},
    date_re=re.compile(r"^\d{2}/\d{2}(?:/\d{2,4})?$"),
    date_format="%d/%m /%Y|%d/%m/%Y|%d/%m/%y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?: ?\(?[Cc][Rr]\)?\.?| ?\(?[Dd][Rr]\)?\.?)?$"),
    period_re=re.compile(r"statementofaccountfrom(\d{2}/\d{2}/\d{4})to(\d{2}/\d{2}/\d{4})"),
    period_date_format="%d/%m/%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    end_markers=("ENDOFSTATEMENT",),
    continuation_start="top",
    row_order="auto",
)
CBI_LAYOUT_4.validate()
