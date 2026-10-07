"""HDFC layout configuration + thin bindings to the shared extraction engine (statement_engine.extraction)."""
from ...extraction.anchors import AnchorError, ColumnAnchors, derive_anchors
from ...extraction.checks import Checks, run_checks
from ...extraction.engine import V2Outcome
from ...extraction.rows import AssembledTable, Page, RawRow, assemble
from ...extraction.summary import PrintedSummary
from ...extraction.words import Word, group_lines
from .engine import extract_pages
from .layout_spec import HDFC_LAYOUT_A, HDFC_LAYOUT_A_ID, LayoutSpec
from .summary import parse_summary

__all__ = [
    "AnchorError", "ColumnAnchors", "derive_anchors", "Checks", "run_checks", "V2Outcome", "extract_pages",
    "HDFC_LAYOUT_A", "HDFC_LAYOUT_A_ID", "LayoutSpec", "AssembledTable", "Page", "RawRow", "assemble",
    "PrintedSummary", "parse_summary", "Word", "group_lines",
]
