from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import CSB_LAYOUT_1


class CsbV2Extractor(LayoutExtractor):
    def __init__(self, spec=CSB_LAYOUT_1):
        super().__init__(spec, name="csb_v2")
