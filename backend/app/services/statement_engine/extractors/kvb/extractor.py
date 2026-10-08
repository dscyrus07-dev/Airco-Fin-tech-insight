from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import KVB_LAYOUT_1


class KVBV2Extractor(LayoutExtractor):
    def __init__(self, spec=KVB_LAYOUT_1):
        super().__init__(spec, name="kvb_v2")
