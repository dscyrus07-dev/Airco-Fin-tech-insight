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
    opening_balance_re=re.compile(r"OpeningBalance(-?[\d,]*\.\d{2})"),
)
FEDERAL_LAYOUT_1.validate()
