from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import HSBC_LAYOUT_1


class HSBCV2Extractor(LayoutExtractor):
    def __init__(self, spec=HSBC_LAYOUT_1):
        super().__init__(spec, name="hsbc_v2")
