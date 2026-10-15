"""Federal Bank layout configuration (dominant fingerprint "date | value date | particulars | tran type | cheque details |
withdrawals | deposits | balance | dr/cr"). Facts only."""
from __future__ import annotations

import re

from ...extraction.layout_spec import LayoutSpec

FEDERAL_LAYOUT_1 = LayoutSpec(
    layout_id="federal_date_valuedate_particulars_trantype_chequedetails_withdrawals_deposits_balance_drcr",
    bank_key="federal",
    bank_markers=("FEDERALBANK",),
    merge_statements=True,
    bank_name="Federal Bank",
    columns={
        "date": (("date",),),
        "value_date": (("value", "date"), ("valuedate",)),
        "narration": (("particulars",),),
        "trantype": (("tran", "type"), ("trantype",)),
        "ref": (("cheque", "details"), ("chequedetails",)),
        "debit": (("withdrawals",),),
        "credit": (("deposits",),),
        "balance": (("balance",),),
        "side": (("dr", "cr"), ("drcr",)),          # transaction side marker: not used (the money columns carry the side)
    },
    text_columns=("date", "value_date", "narration", "trantype", "ref"),
    band_left_pad={"narration": 85.0},
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]*\.\d{2}$"),
    period_re=re.compile(r"PERIOD:(\d{2}-[A-Za-z]{3}-\d{4})to(\d{2}-[A-Za-z]{3}-\d{4})"),
    period_date_format="%d-%b-%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    secondary_date_column="value_date",
    end_markers=("ENDOFSTATEMENT",),
    header_repeats=True,
    header_wraps=True,
    opening_balance_re=re.compile(r"OpeningBalance(-?[\d,]*\.\d{2})"),
    totals_line_re=re.compile(r"(?i)grandtotal(-?[\d,]+\.\d{2})(-?[\d,]+\.\d{1,2})"),
    anchor_full=True,
    date_left_pad=10.0,
)
FEDERAL_LAYOUT_1.validate()


# Same "Statement of Account" family as FEDERAL_LAYOUT_1 but WITHOUT the trailing DR/CR column: the
# header line prints "Tran"/"Cheque" (their second words "Type"/"Details" wrap below the header line),
# amounts may print as bare integers, dates are dd-MMM-yyyy, the period line is ISO yyyy-mm-dd.
FEDERAL_LAYOUT_2 = LayoutSpec(
    layout_id="federal_date_valuedate_particulars_trantype_chequedetails_withdrawals_deposits_balance",
    bank_key="federal",
    bank_markers=("FEDERALBANK",),
    merge_statements=True,
    bank_name="Federal Bank",
    columns={
        "date": (("date",),),
        "value_date": (("value", "date"), ("valuedate",)),
        "narration": (("particulars",),),
        "trantype": (("tran", "type"), ("tran",)),
        "ref": (("cheque", "details"), ("cheque",)),
        "debit": (("withdrawals",),),
        "credit": (("deposits",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "value_date", "narration", "trantype", "ref"),
    band_left_pad={"narration": 85.0},
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}(?:-[A-Za-z]{3}-\d{4}|/\d{2}/\d{4}|-\d{2}-\d{4})$"),
    date_format="%d-%b-%Y|%d/%m/%Y|%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+(?:\.\d{1,2})?$"),
    period_re=re.compile(r"(?i)period(\d{4}-\d{2}-\d{2})to(\d{4}-\d{2}-\d{2})"),
    period_date_format="%Y-%m-%d",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    secondary_date_column="value_date",
    end_markers=("ENDOFSTATEMENT",),
    header_repeats=True,
    header_wraps=True,
    continuation_start="top",
    opening_balance_re=re.compile(r"(?i)openingbalance(-?[\d,]*\.?\d*)"),
    totals_line_re=re.compile(r"(?i)grandtotal(-?[\d,]+\.\d{2})(-?[\d,]+\.\d{1,2})"),
    anchor_full=True,
    date_left_pad=10.0,
)
FEDERAL_LAYOUT_2.validate()


# Same family plus a "Tran ID" column between "Tran Type" and "Cheque Details" and a trailing
# "DR"/"CR" side-marker column (classified but unused: the money columns carry the side).
FEDERAL_LAYOUT_3 = LayoutSpec(
    layout_id="federal_date_valuedate_particulars_trantype_tranid_chequedetails_withdrawals_deposits_balance_drcr",
    bank_key="federal",
    bank_markers=("FEDERALBANK",),
    merge_statements=True,
    bank_name="Federal Bank",
    columns={
        "date": (("date",),),
        "value_date": (("value", "date"), ("valuedate",)),
        "narration": (("particulars",),),
        "trantype": (("tran", "type"), ("tran",)),
        "ref": (("tran", "id"), ("tranid",)),
        "cheque": (("cheque", "details"), ("chequedetails",)),
        "debit": (("withdrawals",),),
        "credit": (("deposits",),),
        "balance": (("balance",),),
        "side": (("dr",), ("drcr",), ("dr", "cr"), ("cr", "dr"), ("crdr",)),
    },
    text_columns=("date", "value_date", "narration", "trantype", "ref", "cheque"),
    band_left_pad={"narration": 85.0},
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}(?:-[A-Za-z]{3}-\d{4}|/\d{2}/\d{4}|-\d{2}-\d{4})$"),
    date_format="%d-%b-%Y|%d/%m/%Y|%d-%m-%Y",
    amount_re=re.compile(r"^-?[\d,]+(?:\.\d{1,2})?$"),
    period_re=re.compile(r"(?i)period(\d{4}-\d{2}-\d{2})to(\d{4}-\d{2}-\d{2})"),
    period_date_format="%Y-%m-%d",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    secondary_date_column="value_date",
    end_markers=("ENDOFSTATEMENT",),
    header_repeats=True,
    header_wraps=True,
    continuation_start="top",
    opening_balance_re=re.compile(r"(?i)openingbalance(-?[\d,]*\.?\d*)"),
    totals_line_re=re.compile(r"(?i)grandtotal(-?[\d,]+\.\d{2})(-?[\d,]+\.\d{1,2})"),
    anchor_full=True,
    date_left_pad=10.0,
)
FEDERAL_LAYOUT_3.validate()


# Fi/Jupiter app export ("Account Statement" PDF): a section date ("23 Nov") prints once under the Date
# title and the transaction rows beneath it carry no date; the record is narration + amount + running balance
# on one line with wrapped narration / a wrapped ".dd" amount tail on the next. No Dr/Cr side prints anywhere —
# the side is the direction of the balance move (derived, never assumed). The page-1 block prints
# "Opening Balance + Money In - Spent = Saved + Closing Balance" as a label line, a counts/dates line and a
# "₹open ₹in ₹out ₹saved ₹close" value line; header titles double every glyph ("DDaattee").
FEDERAL_LAYOUT_4 = LayoutSpec(
    layout_id="federal_date_transactiondetails_amount_balance_sectiondate",
    bank_key="federal",
    bank_markers=("FEDERALBANK",),
    bank_name="Federal Bank",
    columns={
        "date": (("date",),),
        "narration": (("transaction", "details"), ("transactiondetails",)),
        "txn_amount": (("amount",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    doubled_header_glyphs=True,
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    single_amount_column="txn_amount",
    derive_side_from_balance=True,
    date_re=re.compile(r"(?i)^\d{1,2}(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\d{0,4}$"),
    date_format="%d %b %Y|%d%b %Y|%d %B %Y|%d%B %Y|%d%B%Y|%d%b%Y",
    year_from_period=True,
    section_date_re=re.compile(r"(?i)^\d{1,2}[A-Za-z]{3,9}\d{0,4}$"),
    amount_re=re.compile(r"^-?[\d,]+(?:\.\d{1,2})?$"),
    wrapped_amount_tokens=True,
    period_re=re.compile(r"(?i)(\d{1,2}[a-z]+\d{4})to(\d{1,2}[a-z]+\d{4})"),
    period_date_format="%d%B%Y",
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    page_footer_markers=("CONTACTUS",),
    ignore_line_res=(re.compile(r"(?i)day/night"), re.compile(r"(?i)^5am-6pm")),
    anchor_scan="document",
    anchor_full=True,
    opening_balance_re=re.compile(r"^₹([\d,]+)₹"),
    closing_balance_re=re.compile(r"₹([\d,]+)$"),
    totals_line_re=re.compile(r"₹[\d,]+₹([\d,]+)₹([\d,]+)₹([\d,]+)₹"),
    totals_credit_first=True,
    totals_sum_tail=True,
    doc_counts_re=re.compile(r"(?:19|20)\d{2}(\d{1,4})Transactions(\d{1,4})Transactions(\d{1,4})Transactions"),
    summary_truncated=True,
    date_left_pad=10.0,
    ifsc_re=re.compile(r"FDRL0[0-9A-Z]{6}"),
)
FEDERAL_LAYOUT_4.validate()


# Same app-export family, older shape: "Reference ID | Transaction details | Amount | Balance" where the left
# column carries S-prefixed reference ids (the zone that hosts the section labels), section dates print with an
# apostrophe year ("1 Dec '22"), and every money cell carries a "₹" mark. The page-1 summary prints only
# Money out / Money in / Closing balance — no opening — and the figures are truncated whole-unit displays.
FEDERAL_LAYOUT_5 = LayoutSpec(
    layout_id="federal_referenceid_transactiondetails_amount_balance_sectiondate",
    bank_key="federal",
    bank_markers=("FEDERALBANK",),
    bank_name="Federal Bank",
    columns={
        "date": (("reference", "id"), ("referenceid",)),
        "narration": (("transaction", "details"), ("transactiondetails",)),
        "txn_amount": (("amount",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit",
    credit_column="credit",
    balance_column="balance",
    single_amount_column="txn_amount",
    derive_side_from_balance=True,
    date_re=re.compile(r"(?i)^\d{1,2}[a-z]{3,9}'?\d{0,4}$"),
    date_format="%d%b'%y|%d %b '%y|%d%B'%y|%d %B '%y|%d%b%Y|%d%b %Y|%d %b %Y|%d %B %Y|%d%B %Y",
    year_from_period=True,
    section_date_re=re.compile(r"(?i)^\d{1,2}[a-z]{3,9}(?:'\d{2}|\d{0,4})$"),
    amount_re=re.compile(r"^-?[\d,]+(?:\.\d{1,2})?$"),
    amount_prefix="₹",
    wrapped_amount_tokens=True,
    period_re=re.compile(r"(?i)(\d{1,2}[a-z]{3,9})to(\d{1,2}[a-z]{3,9}'\d{2}|\d{1,2}[a-z]{3,9}\d{4})"),
    period_date_format="%d%b'%y",
    period_from_borrows_end_year=True,
    summary_marker="",
    summary_label_text="",
    summary_expected=False,
    header_repeats=True,
    page_footer_markers=("CONTACTUS",),
    anchor_scan="document",
    closing_balance_re=re.compile(r"^₹[\d,.]+₹[\d,.]+₹([\d,.]+)$"),
    totals_line_re=re.compile(r"^₹([\d,.]+)₹([\d,.]+)₹[\d,.]+$"),
    summary_truncated=True,
    ifsc_re=re.compile(r"FDRL0[0-9A-Z]{6}"),
)
FEDERAL_LAYOUT_5.validate()
