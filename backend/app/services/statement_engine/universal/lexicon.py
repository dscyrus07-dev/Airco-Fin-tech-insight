"""Vocabulary for structure inference. Synonyms are compared after norm_token()
(lower-case alphanumerics only), so "Txn Date", "txn_date" and "TXN-DATE" all hit "txndate".

A role may match an alternative that is several tokens long: the match consumes a contiguous
run of tokens on the header line ("Value Date" -> ("value", "date")).
"""
from __future__ import annotations

import re

# role -> alternative token sequences (already normalised words joined by spaces shown as tuples)
HEADER_SYNONYMS = {
    "date": [
        ("date",), ("txndate",), ("txn", "date"), ("transactiondate",), ("transaction", "date"),
        ("tran", "date"), ("trandate",), ("postingdate",), ("posting", "date"), ("post", "date"),
        ("dt",), ("dated",), ("transactiondt",), ("txndt",),
        ("datetime",), ("date", "time"), ("dateandtime",), ("txndatetime",),
        ("transactiondatetime",), ("dateandtime",),
    ],
    "value_date": [
        ("valuedate",), ("value", "date"), ("val", "date"), ("valuedt",),
        ("valuetxndate",), ("value", "txn", "date"),
    ],
    "narration": [
        ("narration",), ("particulars",), ("description",), ("details",), ("remarks",),
        ("transactiondetails",), ("transaction", "details"), ("transactiondescription",),
        ("transaction", "description"), ("detail",), ("paymentdetails",), ("payment", "details"),
        ("transaction",), ("txn", "description"), ("activity",), ("particular",),
    ],
    "debit": [
        ("debit",), ("debits",), ("withdrawal",), ("withdrawals",), ("withdrawalamt",),
        ("withdrawal", "amount"), ("dr",), ("dramount",), ("dr", "amount"), ("paidout",),
        ("paid", "out"), ("moneyout",), ("money", "out"), ("debitamount",), ("debit", "amount"),
        ("amountdebited",), ("amount", "debited"), ("payment",), ("payments",), ("spent",),
        ("withdrawalamt",), ("amtdebited",), ("outflow",), ("charges",), ("chequedeposit",),
        ("debitrs",), ("debit", "rs"), ("withdr",), ("out",),
        ("withdrawal", "amt"), ("debit", "amt"), ("dr", "amt"), ("amtdebit",),
        ("withdrawal", "inr"), ("debit", "inr"),
    ],
    "credit": [
        ("credit",), ("credits",), ("deposit",), ("deposits",), ("depositamt",),
        ("deposit", "amount"), ("cr",), ("cramount",), ("cr", "amount"), ("paidin",),
        ("paid", "in"), ("moneyin",), ("money", "in"), ("creditamount",), ("credit", "amount"),
        ("amountcredited",), ("amount", "credited"), ("receipt",), ("receipts",), ("received",),
        ("depositamt",), ("amtcredited",), ("inflow",), ("creditrs",), ("credit", "rs"),
        ("dep",), ("in",), ("deposit", "amt"), ("credit", "amt"), ("cr", "amt"),
        ("amtcredit",), ("deposit", "inr"), ("credit", "inr"),
    ],
    "amount": [
        ("amount",), ("amountinr",), ("amount", "inr"), ("transactionamount",),
        ("transaction", "amount"), ("amt",), ("txnamount",), ("txn", "amount"),
        ("amountrs",), ("amount", "rs"), ("rs",), ("amountin", "rs"),
        ("debitcredit",), ("creditdebit",), ("debcr",), ("drcr",),
        ("amountinrs",), ("amount", "in", "rs"), ("transactionamt",),
    ],
    "balance": [
        ("balance",), ("balances",), ("closingbalance",), ("closing", "balance"),
        ("runningbalance",), ("running", "balance"), ("availablebalance",), ("available", "balance"),
        ("balanceamount",), ("balance", "amount"), ("bal",), ("ledgerbalance",), ("ledger", "balance"),
        ("balancerb",), ("balancenin",), ("balin",), ("accountbalance",), ("account", "balance"),
        ("closingbal",), ("balancers",), ("balance", "rs"), ("balance", "inr"),
        ("balanceinrs",), ("balanceinr",), ("availablebal",),
    ],
    "ref": [
        ("ref",), ("refno",), ("ref", "no"), ("referenceno",), ("reference", "no"),
        ("referencenumber",), ("reference", "number"), ("reference",), ("chequeno",),
        ("cheque", "no"), ("chqno",), ("chq", "no"), ("cheque",), ("chq",),
        ("instrumentno",), ("instrument", "no"), ("instno",), ("utr",), ("utrno",),
        ("rrn",), ("transactionid",), ("transaction", "id"), ("txnid",), ("refnum",),
        ("chequenumber",), ("cheque", "number"), ("instrno",), ("instdno",),
        ("chqrefno",), ("chqref",), ("refnochequeno",), ("ref", "no", "cheque", "no"),
    ],
    "type": [
        ("type",), ("txntype",), ("txn", "type"), ("transactiontype",), ("transaction", "type"),
        ("drcr",), ("dr", "cr"), ("crdr",), ("cr", "dr"), ("debcr",), ("drcrindicator",),
        ("crdrindicator",), ("txnmode",), ("mode",), ("instrument", "type"),
    ],
    "serial": [
        ("slno",), ("sl", "no"), ("sno",), ("s", "no"), ("serialno",), ("serial", "no"),
        ("srno",), ("sr", "no"), ("no",), ("sl",),
    ],
    "branch": [("branch",), ("branchname",), ("branch", "name"), ("trnbranch",)],
    "category": [("category",), ("code",)],
}

# a header line must cover these to be a transaction-table header
REQUIRED_ROLES = ("date", "narration", "balance")

# ---- date shapes (regex on one word; strptime formats may chain with |) ----
DATE_SHAPES = [
    # (name, date_re pattern, date_format, optional date_tail pattern for wrapped year)
    ("dmy_slash",     r"^\d{1,2}/\d{1,2}/\d{4}$",                     "%d/%m/%Y",                                     None),
    ("dmy_slash2",    r"^\d{1,2}/\d{1,2}/\d{2}$",                     "%d/%m/%y",                                     None),
    ("dmy_dash",      r"^\d{1,2}-\d{1,2}-\d{4}$",                     "%d-%m-%Y",                                     None),
    ("ymd_dash",      r"^\d{4}-\d{2}-\d{2}$",                         "%Y-%m-%d",                                     None),
    ("ymd_slash",     r"^\d{4}/\d{2}/\d{2}$",                         "%Y/%m/%d",                                     None),
    ("dmy_dash2",     r"^\d{1,2}-\d{1,2}-\d{2}$",                     "%d-%m-%y",                                     None),
    ("dmony_dash",    r"^\d{1,2}-[A-Za-z]{3}-\d{4}$",                 "%d-%b-%Y",                                     None),
    ("dmony_dash2",   r"^\d{1,2}-[A-Za-z]{3}-\d{2}$",                 "%d-%b-%y",                                     None),
    ("dmony_compact", r"^\d{1,2}[A-Za-z]{3}\d{2,4}$",                 "%d%b%Y|%d%b%y",                                None),
    ("dmony_slash",   r"^\d{1,2}/[A-Za-z]{3}/\d{2,4}$",               "%d/%b/%Y|%d/%b/%y",                            None),
    ("dmony_spc",     r"^\d{1,2}[ -]?[A-Za-z]{3}(?:[ -]?\d{2,4})?$",  "%d %b %Y|%d %b %y|%d-%b-%Y|%d-%b-%y|%d%b%Y|%d%b%y", r"^\d{4}$"),
    ("dmy_dot",       r"^\d{1,2}\.\d{1,2}\.\d{4}$",                   "%d.%m.%Y",                                     None),
    ("dmy_dot2",      r"^\d{1,2}\.\d{1,2}\.\d{2}$",                   "%d.%m.%y",                                     None),
    ("mdy_slash",     None,                                           None,                                           None),  # deliberately unsupported
]

# money cell forms: amount_re covers them all; `single_amount` when suffixes/signs seen
# Un-comma'd bare integers without a decimal point are capped at 9 digits so 10-16 digit UPI RRNs,
# phone numbers, and account numbers inside narrations are never mistaken for amounts.
AMOUNT_RE = re.compile(r"^[+-]?\s*(?:Rs\.?|₹)?\s*-?\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?(?:\s*\(?\s*(?:cr|dr)\s*\.?\)?)?$"
                       r"|^[+-]?\s*(?:Rs\.?|₹)?\s*-?\d{1,12}\.\d{1,2}(?:\s*\(?\s*(?:cr|dr)\s*\.?\)?)?$"
                       r"|^[+-]?\s*(?:Rs\.?|₹)?\s*-?\d{1,9}(?:\s*\(?\s*(?:cr|dr)\s*\.?\)?)?$", re.I)
PLAIN_AMOUNT_RE = re.compile(r"^[+-]?\s*(?:Rs\.?|₹)?\s*-?\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?$"
                             r"|^[+-]?\s*(?:Rs\.?|₹)?\s*-?\d{1,12}\.\d{1,2}$"
                             r"|^[+-]?\s*(?:Rs\.?|₹)?\s*-?\d{1,9}$")
DRCR_SUFFIX_RE = re.compile(r"(?i)\(?\s*(cr|dr)\s*\.?\)?\s*$")
SIGNED_RE = re.compile(r"^[+-]\s*(?:Rs\.?|₹)?\s*\d")

# generic labelled summary lines (searched on whitespace-free page text, group = value)
OPENING_RES = [
    r"(?i)openingbalance[^0-9]{0,8}([\d,]+\.\d{2})",
    r"(?i)balancebroughtforward[^0-9]{0,8}([\d,]+\.\d{2})",
    r"(?i)balancebf[^0-9]{0,8}([\d,]+\.\d{2})",
    r"(?i)broughtforward[^0-9]{0,8}([\d,]+\.\d{2})",
    r"(?i)previousbalance[^0-9]{0,8}([\d,]+\.\d{2})",
]
CLOSING_RES = [
    r"(?i)closingbalance[^0-9]{0,8}([\d,]+\.\d{2})",
    r"(?i)balancecarriedforward[^0-9]{0,8}([\d,]+\.\d{2})",
    r"(?i)balancecf[^0-9]{0,8}([\d,]+\.\d{2})",
    r"(?i)carriedforward[^0-9]{0,8}([\d,]+\.\d{2})",
]
PERIOD_RES = [
    # (regex with two groups, strptime for each)
    (r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})[A-Za-z\s:]*[Tt][Oo][A-Za-z\s:]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})", "%d/%m/%Y"),
    (r"(\d{1,2}[/\-][A-Za-z]{3}[/\-]\d{4})[A-Za-z\s:]*[Tt][Oo][A-Za-z\s:]*(\d{1,2}[/\-][A-Za-z]{3}[/\-]\d{4})", "%d-%b-%Y|%d/%b/%Y"),
    (r"(\d{1,2}[A-Za-z]{3}\d{4})[Tt][Oo](\d{1,2}[A-Za-z]{3}\d{4})", "%d%b%Y"),
    (r"[Ff]rom(\d{1,2}/\d{1,2}/\d{4})[Tt]o(\d{1,2}/\d{1,2}/\d{4})", "%d/%m/%Y"),
]
TOTALS_RES = [
    r"(?i)totaldebits?[^0-9]{0,8}([\d,]+\.\d{2})[^0-9]{0,12}totalcredits?[^0-9]{0,8}([\d,]+\.\d{2})",
    r"(?i)total(?:s)?[^0-9]{0,8}([\d,]+\.\d{2})[^0-9]{0,12}([\d,]+\.\d{2})",
]
ACCOUNT_RES = [
    re.compile(r"(?i)(?:a/?c|account|acct)[\s.:]*(?:no|number|#)?[\s.:]*(\d{8,})"),
    re.compile(r"(?i)accountnumber[\s.:]*(\d{8,})"),
]
OPENING_ROW_MARKERS = ("OPENINGBALANCE", "BALANCEBROUGHTFORWARD", "BALANCEB/F", "B/FBALANCE",
                       "BALBROUGHTFWD", "BROUGHTFORWARD", "B/F", "OPENING")
CLOSING_ROW_MARKERS = ("CLOSINGBALANCE", "BALANCECARRIEDFORWARD", "CARRIEDFORWARD", "C/F", "CLOSING")

# a line with no real words -> glyph dump detector
CID_RE = re.compile(r"\(cid:\d+\)")
