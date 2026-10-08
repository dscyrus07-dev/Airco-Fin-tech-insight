from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import PNB_LAYOUT_1


class PNBV2Extractor(LayoutExtractor):
    def __init__(self, spec=PNB_LAYOUT_1):
        super().__init__(spec, name="pnb_v2")
