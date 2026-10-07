from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import FEDERAL_LAYOUT_1


class FederalV2Extractor(LayoutExtractor):
    def __init__(self, spec=FEDERAL_LAYOUT_1):
        super().__init__(spec, name="federal_v2")
