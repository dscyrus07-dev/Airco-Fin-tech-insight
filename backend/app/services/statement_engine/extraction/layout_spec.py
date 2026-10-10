"""Declarative layout facts. The extraction engine reads a LayoutSpec and contains no bank-specific logic: adding a
layout (a second layout of a bank, another bank) means adding a spec plus synthetic fixtures, not changing the engine.

Supported table model: a header row naming the columns, left-to-right text columns (date first, narration and optional
reference / secondary date in any order), then right-aligned money columns (debit, credit, balance) matched by
right edge. Single signed-amount columns and Dr/Cr suffix layouts are NOT supported yet; a spec for them must wait for
the engine capability (see layout census)."""
from __future__ import annotations

from dataclasses import dataclass, field
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
    closing_row_marker: str = ""               # same for a dated "closing balance" row at the end of the table
    page_break_re: Optional[Pattern[str]] = None       # whitespace-free line that opens a printed page break inside a PDF page; lines up to and including the next header row are skipped
    opening_row_balance_only: bool = False    # the first row is the opening balance when it carries a balance and no debit/credit amount (any narration)
    totals_credit_first: bool = False          # the totals line prints credits before debits; a third group, when present, is the printed closing balance
    carry_forward_re: Optional[Pattern[str]] = None    # whitespace-free line that restates the running balance at the top of a page; dropped unless it is the table's first row
    undated_rows_inherit_date: bool = False    # a line with a balance and a debit/credit amount but no date is a new row on the previous row's date
    totals_accumulate: bool = False            # the totals line repeats (per printed section): sum the debits and credits of every match, closing from the last
    empty_amount_marker: str = ""              # text printed in a money cell that has no amount (e.g. "-"); read as empty, never as narration
    monospace_text: bool = False               # text-rendered page: each line arrives as one word; split on whitespace, x divided by character count
    bank_markers: Tuple[str, ...] = ()         # whitespace-free UPPER-CASE bank names as printed above the table header; used by the registry to refuse a header that another bank's statement shares
    year_from_period: bool = False             # printed dates carry no year: take it from the printed statement period (the year that puts the date inside the period)
    merge_statements: bool = False             # a PDF that holds several statements: ignore empty ones, merge overlapping / contiguous ones, else REVIEW
    dated_rows_after_end_ok: bool = False      # dated lines after the end marker (e.g. a trailing summary table) are not another statement
    amount_prefix: str = ""                    # currency text printed in front of amounts ("Rs.", several as "Rs.|₹"), stripped before matching
    merge_sign_prefix: bool = False            # a standalone "+"/"-" word right before an amount belongs to it (single_amount_column: + credit, - debit)
    single_amount_column: str = ""             # one signed money column whose cells end in Dr/Cr; debit_column/credit_column are then virtual names
    side_marker_column: str = ""               # a text column (usually narration) whose Dr/Cr word supplies the side of single_amount_column when the marker prints outside the amount cell
    continuation_amounts: bool = False         # money cells may print on a row's continuation line: an undated line's amounts fill the current row's still-empty money cells
    wrapped_amount_tokens: bool = False        # a money cell too wide for its column splits mid-number across the row line and its continuation ("9,99,999.9" + "9"): join the continuation token onto a still-invalid amount only when the result matches amount_re
    row_order: str = "forward"                 # "reverse": newest first; "auto": reversed only when the balance chain holds newest-first and breaks oldest-first
    zero_amount_is_empty: bool = False         # both money cells are always printed; a zero in one is "no amount on this side"
    sign_is_decoration: bool = False           # a +/- printed on debit/credit amounts only restates the column, it is not a reversal
    merge_drcr_suffix: bool = False            # a separate "Cr"/"Dr" word right after an amount is part of that amount ("3514.56 Cr")
    drcr_suffix_decoration: bool = False       # a Dr/Cr word at the end of a SPLIT debit/credit amount only restates the column ("220.00 DR" in the debit column): strip it before parsing
    left_aligned_amounts: bool = False         # money data is left-aligned under its column titles: assign by the column's left edge instead of right-edge proximity
    amount_sign_gap: bool = False              # the sign and the digits are separated by space(s) inside the same cell ("-  4,928.58")
    page_footer_markers: Tuple[str, ...] = ()   # whitespace-free upper-case line starts: everything below such a line on a page is footer, the table goes on next page
    band_left_pad: Dict[str, float] = field(default_factory=dict)   # text column -> how far left of its header title its data may start (centred titles)
    summary_position: str = "after"             # "after": summary block follows the table; "before": printed above the header on page 1
    continuation_start: str = "marker"         # pages >= 2 without header: "marker" (after period line) or "top" (whole page)
    ignore_line_res: Tuple[Pattern[str], ...] = ()     # whitespace-free lines to drop (page numbers, running headers)
    clipped_drcr_suffix: bool = False        # page-edge-clipped balance cells print "…C"/"…D" instead of "…Cr"/"…Dr": a lone C/D suffix on the balance is treated as the clipped marker (chain must still prove the values)
    header_only_ok: bool = False             # opt-in policy: a header match alone (bank_evidence "none") may route this layout;
                                            # set only when the candidate table in docs/slice3/HEADER_ONLY_CANDIDATES.md proves it safe
    anchor_full: bool = False                # VERIFIED only when BOTH chain ends carry an independent printed figure:
                                             # opening AND (closing or printed debit/credit totals). A single anchor leaves the
                                             # far end of the chain self-derived -> first/last-row corruption survives as VERIFIED.

    @property
    def amount_columns(self) -> Tuple[str, ...]:
        if self.single_amount_column:
            return (self.single_amount_column, self.balance_column)
        return (self.debit_column, self.credit_column, self.balance_column)

    def validate(self) -> None:
        if len(self.text_columns) < 2 or self.text_columns[0] != "date" or "narration" not in self.text_columns:
            raise ValueError("text_columns must start with 'date' and include 'narration'")
        for col in (*self.text_columns, *self.amount_columns):
            if col not in self.columns:
                raise ValueError(f"column {col!r} has no header token sequence")
        if self.row_order not in ("forward", "reverse", "auto"):
            raise ValueError("row_order must be 'forward', 'reverse' or 'auto'")
        if self.single_amount_column and self.debit_column == self.credit_column:
            raise ValueError("single_amount_column needs distinct virtual debit/credit names")
        if self.summary_position not in ("after", "before"):
            raise ValueError("summary_position must be 'after' or 'before'")
        if self.continuation_start not in ("marker", "top"):
            raise ValueError("continuation_start must be 'marker' or 'top'")
        if self.side_flip_policy not in ("fail", "review"):
            raise ValueError("side_flip_policy must be 'fail' or 'review'")
        if self.secondary_date_column and self.secondary_date_column not in self.text_columns:
            raise ValueError("secondary_date_column must be one of text_columns")
        if self.side_marker_column:
            if not self.single_amount_column:
                raise ValueError("side_marker_column requires single_amount_column")
            if self.side_marker_column not in self.columns or self.side_marker_column not in self.text_columns:
                raise ValueError("side_marker_column must be a declared text column")
