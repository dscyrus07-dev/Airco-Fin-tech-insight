from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import SIB_LAYOUT_1


class SouthIndianV2Extractor(LayoutExtractor):
    def __init__(self, spec=SIB_LAYOUT_1):
        super().__init__(spec, name="south_indian_v2")
