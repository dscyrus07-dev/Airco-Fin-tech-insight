"""HDFC-defaulted wrapper over the layout-neutral engine."""
from ...extraction.engine import NO_ROWS, NO_TABLE_HEADER, V2Outcome  # noqa: F401
from ...extraction.engine import extract_pages as _extract
from .layout_spec import HDFC_LAYOUT_A


def extract_pages(pages, spec=HDFC_LAYOUT_A):
    return _extract(pages, spec)
