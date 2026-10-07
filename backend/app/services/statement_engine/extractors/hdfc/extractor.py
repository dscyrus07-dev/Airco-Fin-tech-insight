"""HDFC extractor: the shared LayoutExtractor bound to the HDFC layout A configuration."""
from __future__ import annotations

from ...extraction.pdf_extractor import LOCKED, READ_ERROR, SCANNED_NO_TEXT, LayoutExtractor, read_pages  # noqa: F401
from ...extraction.pdf_extractor import to_extraction_result as _to_result
from .layout_spec import HDFC_LAYOUT_A, LayoutSpec


def to_extraction_result(outcome, spec: LayoutSpec = HDFC_LAYOUT_A):
    return _to_result(outcome, spec)


class HDFCV2Extractor(LayoutExtractor):
    def __init__(self, spec: LayoutSpec = HDFC_LAYOUT_A):
        super().__init__(spec, name="hdfc_v2")
