from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import PAYTM_LAYOUT_1


class PaytmV2Extractor(LayoutExtractor):
    def __init__(self, spec=PAYTM_LAYOUT_1):
        super().__init__(spec, name="paytm_v2")
