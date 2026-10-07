"""Declarative layout facts. The extraction engine reads a LayoutSpec and contains no bank-specific logic: adding a
layout (a second layout of a bank, another bank) means adding a spec plus synthetic fixtures, not changing the engine.

Supported table model: a header row naming the columns, left-to-right text columns (date first, narration and optional
reference / secondary date in any order), then right-aligned money columns (debit, credit, balance) matched by
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
    summary_marker: str                        # whitespace-free, upper-case marker that starts the printed summary ("" = none)
    summary_label_text: str                    # normalised concatenation of the summary column labels
    summary_fields: Tuple[str, ...] = DEFAULT_SUMMARY_FIELDS   # printed order of the summary numbers
    secondary_date_column: Optional[str] = None  # a text column that holds a date (e.g. value date)
    header_repeats: bool = False               # True when every page repeats the table header
    ifsc_re: Optional[Pattern[str]] = None
    account_label: str = ""                    # normalised token that precedes the account number value
    end_markers: Tuple[str, ...] = ()          # extra whitespace-free upper-case markers that end the table (footers)
    date_tail_re: Optional[Pattern[str]] = None  # continuation of a date cell wrapped onto the next line (e.g. the year)
    side_flip_policy: str = "fail"             # "review": isolated printed-side/balance disagreements (amount equals the balance move) only warn
    period_tolerance_days: int = 1             # rows this many days outside the printed period are informational only
    dates_monotonic_expected: bool = True      # False: the bank prints rows in posting order that may not be date-sorted
    summary_expected: bool = True              # False: statements of this layout normally print no summary block
    opening_balance_re: Optional[Pattern[str]] = None  # whitespace-free page-1 text; group 1 = printed opening balance
    closing_balance_re: Optional[Pattern[str]] = None  # whitespace-free text of ONE line inside the table; group 1 = closing balance
    totals_line_re: Optional[Pattern[str]] = None      # whitespace-free line inside the table; groups 1,2 = printed debit, credit sums
    opening_row_marker: str = ""               # whitespace-free upper-case start of the narration of a dated "opening balance" row (dropped; its balance is the printed opening)
    sign_is_decoration: bool = False           # a +/- printed on debit/credit amounts only restates the column, it is not a reversal
    summary_position: str = "after"             # "after": summary block follows the table; "before": printed above the header on page 1
    continuation_start: str = "marker"         # pages >= 2 without header: "marker" (after period line) or "top" (whole page)
    ignore_line_res: Tuple[Pattern[str], ...] = ()     # whitespace-free lines to drop (page numbers, running headers)

    @property
    def amount_columns(self) -> Tuple[str, ...]:
        return (self.debit_column, self.credit_column, self.balance_column)

    def validate(self) -> None:
        if len(self.text_columns) < 2 or self.text_columns[0] != "date" or "narration" not in self.text_columns:
            raise ValueError("text_columns must start with 'date' and include 'narration'")
        for col in (*self.text_columns, *self.amount_columns):
            if col not in self.columns:
                raise ValueError(f"column {col!r} has no header token sequence")
        if self.summary_position not in ("after", "before"):
            raise ValueError("summary_position must be 'after' or 'before'")
        if self.continuation_start not in ("marker", "top"):
            raise ValueError("continuation_start must be 'marker' or 'top'")
        if self.side_flip_policy not in ("fail", "review"):
            raise ValueError("side_flip_policy must be 'fail' or 'review'")
        if self.secondary_date_column and self.secondary_date_column not in self.text_columns:
            raise ValueError("secondary_date_column must be one of text_columns")
