"""HDFC-defaulted wrapper over the layout-neutral summary parser."""
from ...extraction.summary import PrintedSummary  # noqa: F401
from ...extraction.summary import parse_summary as _parse
from .layout_spec import HDFC_LAYOUT_A


def parse_summary(lines, spec=HDFC_LAYOUT_A):
    return _parse(lines, spec)
