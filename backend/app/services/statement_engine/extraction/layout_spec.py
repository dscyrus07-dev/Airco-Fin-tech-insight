"""Declarative layout facts. The extraction engine reads a LayoutSpec and contains no bank-specific logic: adding a
layout (a second layout of a bank, another bank) means adding a spec plus synthetic fixtures, not changing the engine.

Supported table model (Phase 1): a header row naming the columns, left-to-right text columns (date first, narration
second, optional reference / secondary date), then right-aligned money columns (debit, credit, balance) matched by
right edge. Single signed-amount columns and Dr/Cr suffix layouts are NOT supported yet; a spec for them must wait for
the engine capability (see layout census)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Pattern, Tuple

DEFAULT_SUMMARY_FIELDS: Tuple[str, ...] = ("opening", "dr_count", "cr_count", "debits", "credits", "closing")


@dataclass(frozen=True)
class LayoutSpec:
    layout_id: str
    bank_key: str
    bank_name: str
    # column role -> alternative token sequences (normalised: lower-case alphanumerics) that print the column title
    columns: Dict[str, Tuple[Tuple[str, ...], ...]]
    text_columns: Tuple[str, ...]              # left-to-right, non-money columns; [0] is the row-start date, [1] narration
    debit_column: str                          # money column roles (keys of `columns`)
    credit_column: str
    balance_column: str
    date_re: Pattern[str]
    date_format: str                           # strptime format of row dates
    amount_re: Pattern[str]
    period_re: Pattern[str]                    # matched on the whitespace-free text of a line; groups = (from, to)
    period_date_format: str                    # strptime format of the printed period dates
    summary_marker: str                        # whitespace-free, upper-case marker that starts the printed summary
    summary_label_text: str                    # normalised concatenation of the summary column labels
    summary_fields: Tuple[str, ...] = DEFAULT_SUMMARY_FIELDS   # printed order of the summary numbers
    secondary_date_column: Optional[str] = None  # a text column that holds a date (e.g. value date)
    header_repeats: bool = False               # True when every page repeats the table header
    ifsc_re: Optional[Pattern[str]] = None
    account_label: str = ""                    # normalised token that precedes the account number value

    @property
    def amount_columns(self) -> Tuple[str, ...]:
        return (self.debit_column, self.credit_column, self.balance_column)

    def validate(self) -> None:
        if len(self.text_columns) < 2 or self.text_columns[1] != "narration":
            raise ValueError("text_columns must start with the date column followed by 'narration'")
        for col in (*self.text_columns, *self.amount_columns):
            if col not in self.columns:
                raise ValueError(f"column {col!r} has no header token sequence")
        if self.secondary_date_column and self.secondary_date_column not in self.text_columns:
            raise ValueError("secondary_date_column must be one of text_columns")
