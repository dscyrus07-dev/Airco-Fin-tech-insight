"""HDFC V2 extractor building blocks (Slice 3A). Raw rows only; no repair, no classification."""
from .anchors import AnchorError, ColumnAnchors, derive_anchors
from .checks import Checks, run_checks
from .engine import V2Outcome, extract_pages
from .layout_spec import HDFC_LAYOUT_A, HDFC_LAYOUT_A_ID, LayoutSpec
from .rows import AssembledTable, Page, RawRow, assemble
from .summary import PrintedSummary, parse_summary
from .words import Word, group_lines

__all__ = [
    "AnchorError", "ColumnAnchors", "derive_anchors", "Checks", "run_checks", "V2Outcome", "extract_pages",
    "HDFC_LAYOUT_A", "HDFC_LAYOUT_A_ID", "LayoutSpec", "AssembledTable", "Page", "RawRow", "assemble",
    "PrintedSummary", "parse_summary", "Word", "group_lines",
]
