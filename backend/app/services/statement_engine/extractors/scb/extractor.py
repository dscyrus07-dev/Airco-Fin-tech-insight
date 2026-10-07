from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import SCB_LAYOUT_1


class StandardCharteredV2Extractor(LayoutExtractor):
    def __init__(self, spec=SCB_LAYOUT_1):
        super().__init__(spec, name="scb_v2")
