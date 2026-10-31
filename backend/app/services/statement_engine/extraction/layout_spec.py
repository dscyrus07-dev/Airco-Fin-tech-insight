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
    header_wraps: bool = False                 # True when a column title may wrap onto the next visual line; the
                                               # pair is matched as one header (row scan starts after both lines)
    header_lines: int = 1                      # opt-in: merge up to this many adjacent visual lines into one header
                                               # stream (fragments of one column title may sit on non-adjacent lines).
                                               # Words cluster by horizontal overlap (x-ranges within header_merge_tol);
                                               # each cluster emits its fragments top-to-bottom. Refusal unchanged: the
                                               # merged view must complete the column set with no unknown token inside.
    header_merge_tol: float = 4.0              # x-gap (pt) still counted as one title cluster when merging header lines
    date_join_words: bool = False              # opt-in: the date cell prints as several same-line words
                                               # ("08 Aug 2021" -> three tokens): join all words of the date band
                                               # with spaces before parsing (secondary date column already joins)
    untitled_date_column: bool = False         # opt-in: the leftmost column prints dates but no title. The header must
                                               # complete every other column with no token left of the first title; the
                                               # date span is then read from the data rows below (the leftmost x-cluster
                                               # whose cells all match date_re). Refuses when 0 or >=2 candidates exist.
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
    zero_effect_rows_ok: bool = False         # a dated row with NO amount whose printed balance equals the previous row's moved no
                                              # money (a waived charge, a notice): it is noted and kept out of the transactions
                                              # instead of failing the schema. Proven by the balances, so nothing is assumed.
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
    date_left_pad: float = 3.0               # extra left pad for the date column when data dates sit left of the
                                             # first anchored date cell (centred "Date" title over a wide column)
    header_only_ok: bool = False             # opt-in policy: a header match alone (bank_evidence "none") may route this layout;
                                            # set only when the candidate table in docs/engine/HEADER_ONLY_CANDIDATES.md proves it safe
    anchor_full: bool = False                # VERIFIED only when BOTH chain ends carry an independent printed figure:
                                             # opening AND (closing or printed debit/credit totals). A single anchor leaves the
                                             # far end of the chain self-derived -> first/last-row corruption survives as VERIFIED.
    implicit_header: Tuple[str, ...] = ()     # headerless table: no column titles print; the first
                                            # dated line defines the geometry. Lists column roles left-to-right as the
                                            # dated line prints them; "narration" carries no token on that line (its
                                            # band is the gap between the flanking roles). Anchors are still measured
                                            # from the document (the dated line's own cell positions), never hard-coded.
                                            # A narration-only line immediately above a dated line belongs to that row
                                            # (the printed txn-type prefix), not to the previous one.
    anchor_scan: str = "edges"               # "edges": opening/closing/totals searched on page 1 + last page and
                                           # the summary tail only. "document": every page's text is scanned;
                                           # the FIRST opening and LAST closing match in statement order are used;
                                           # two different printed values for the same anchor -> REVIEW (never
                                           # silently pick one).
    leading_amounts: bool = False          # like leading_narration, but the buffered leading line may carry
                                           # any column cells (amount, side marker, ref): they merge into the
                                           # dated row that follows instead of dropping as junk.
    leading_narration: bool = False        # narration-band lines print immediately ABOVE the dated line of their
                                           # own row (and below it): bind them to the dated row they precede
                                           # (the pending-prefix rule). Independent of implicit_header.
    full_width_narration: bool = False     # narration lines span the full page width starting left of the date
                                           # column (no column zone): a wholly unclassified letter line is read
                                           # as narration. Opt-in: only layouts whose narrations live outside
                                           # every declared column may set it.
    digits_only_columns: Tuple[str, ...] = ()   # text columns whose values are always numeric refs (branch codes,
                                           # cheque numbers): an alphabetic token landing in such a column's band
                                           # is narration that began left of its own title (blank ref cells shift
                                           # the narration start left).
    balance_optional: bool = False         # the balance column exists but prints only on some rows
                                           # (carried-forward-style sparse prints): a missing balance cell is
                                           # allowed; the chain verifies long-range deltas between the
                                           # printed positions instead of every adjacent pair.
    no_running_balance: bool = False         # the table prints no running balance column: balance_column must be
                                           # empty and is dropped from amount_columns. The chain and every
                                           # chain-derived check are skipped; completeness (dated lines vs rows)
                                           # and printed totals/counts still apply. Best verdict: REVIEW with code
                                           # NO_RUNNING_BALANCE — never VERIFIED. Rows carry balance=None.
    segment_header_re: Optional[Pattern[str]] = None   # a non-dated line matching this opens a new account segment
                                                     # (whitespace-free match). Rows carry segment ids; the chain runs
                                                     # per segment. Any segment that fails caps the verdict at REVIEW.
    segment_count_re: Optional[Pattern[str]] = None    # a line carrying a segment's printed transaction count;
                                                     # group 1 = the count (matched on the squashed line)
    balance_checkpoint_re: Optional[Pattern[str]] = None  # a non-row line asserting the running balance at that point
                                                        # (BALANCE CARRIED/BROUGHT FORWARD style); group 1 = amount.
                                                        # Checkpoints verify the balance delta over the rows they
                                                        # bracket: closing-of-segment = opening + credits - debits.
    balance_inline_re: Optional[Pattern[str]] = None   # a continuation line that IS the preceding row's balance
                                                     # ("Balance : 1,234.56"); group 1 = amount. The balance is
                                                     # attached to the current row; per-row balances then work
                                                     # normally.
    chain_reorder_same_date: bool = False              # some banks print same-date rows out of balance order; when
                                                       # set, chain/side breaks fully explained by a reorderable
                                                       # same-date window downgrade FAIL->WARN (REVIEW, never silent)
    single_amount_default_side: str = ""               # "" | "debit" | "credit": an unsigned single_amount_column cell
                                                     # carries no Dr/Cr marker; every value is this side (e.g. an
                                                     # all-one-side column). Without it, unsigned cells error.
    section_date_re: Optional[Pattern[str]] = None     # date-grouped rows: a bare section-date line (every word of it
                                                     # inside the date-column zone) opens a section; rows beneath it
                                                     # print no date and inherit the section's. Sections persist across
                                                     # pages. A row before any section date is a defect: skipped and
                                                     # counted as a rows_without_section_date warning (REVIEW).
    derive_side_from_balance: bool = False             # no printed Dr/Cr anywhere: each row's side is the direction of
                                                     # its balance move (requires single_amount_column + balance). The
                                                     # first row of a segment derives from the printed opening anchor;
                                                     # without one it is flagged side_unproven (a warning, never VERIFIED
                                                     # anyway because the independent-anchor check cannot pass).
    doubled_header_glyphs: bool = False                # the app export prints every header letter twice ("DDaattee"):
                                                     # collapse doubled letters before header title matching only.
    summary_truncated: bool = False                    # the printed summary shows whole-unit amounts (rupee-truncated
                                                     # display, e.g. "₹693" for 693.67): reference and totals compare
                                                     # floor(derived) == printed. Counts still compare exactly.
    totals_sum_tail: bool = False                      # the totals/counts line prints the second metric in several
                                                     # buckets: group 1 = first metric, every further group sums into
                                                     # the second (totals_credit_first still fixes which is credits).
    period_from_borrows_end_year: bool = False         # the printed period's from-date carries no year
                                                     # ("1 Dec to 31 Dec '22"): parse it by borrowing the end year
                                                     # (a start month after the end month wraps to end_year - 1).
    doc_counts_re: Optional[Pattern[str]] = None       # document-region line carrying printed transaction counts
                                                     # (e.g. "186 Transactions 235 Transactions"): group order follows
                                                     # totals_credit_first / totals_sum_tail like totals_line_re.

    @property
    def amount_columns(self) -> Tuple[str, ...]:
        bal = () if (self.no_running_balance or self.balance_inline_re is not None) else (self.balance_column,)
        if self.single_amount_column:
            return (self.single_amount_column,) + bal
        return (self.debit_column, self.credit_column) + bal

    def validate(self) -> None:
        if len(self.text_columns) < 2 or self.text_columns[0] != "date" or "narration" not in self.text_columns:
            raise ValueError("text_columns must start with 'date' and include 'narration'")
        for col in (*self.text_columns, *self.amount_columns):
            if col == self.balance_column and self.balance_inline_re is not None:
                continue                      # balances come from labelled continuation lines, not a title column
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
        if self.header_lines < 1:
            raise ValueError("header_lines must be >= 1")
        if self.header_merge_tol < 0:
            raise ValueError("header_merge_tol must be >= 0")
        if self.untitled_date_column and self.implicit_header:
            raise ValueError("untitled_date_column and implicit_header are mutually exclusive")
        if self.implicit_header:
            if "narration" not in self.implicit_header or self.implicit_header[0] != "date":
                raise ValueError("implicit_header must start with 'date' and include 'narration'")
            for col in self.implicit_header:
                if col not in self.columns:
                    raise ValueError(f"implicit_header role {col!r} is not a declared column")
            if not all(c in self.implicit_header for c in (*self.text_columns, *self.amount_columns)):
                raise ValueError("implicit_header must cover every text and amount column")
        if self.anchor_scan not in ("edges", "document"):
            raise ValueError("anchor_scan must be 'edges' or 'document'")
        if self.no_running_balance and self.balance_column:
            raise ValueError("no_running_balance requires balance_column = ''")
        if self.derive_side_from_balance and not self.single_amount_column:
            raise ValueError("derive_side_from_balance requires single_amount_column")
        if self.derive_side_from_balance and self.no_running_balance:
            raise ValueError("derive_side_from_balance requires a printed balance column")
        # segment_header_re / segment_count_re are independent: headers without counts run the
        # chain per segment; a count alone treats the whole document as one implicit segment
        if self.balance_inline_re is not None and self.no_running_balance:
            raise ValueError("balance_inline_re supplies balances; no_running_balance forbids a balance column")
        if self.single_amount_default_side:
            if self.single_amount_default_side not in ("debit", "credit"):
                raise ValueError("single_amount_default_side must be '', 'debit' or 'credit'")
            if not self.single_amount_column:
                raise ValueError("single_amount_default_side requires single_amount_column")
