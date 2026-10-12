from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import IPPB_LAYOUT_1


class IppbV2Extractor(LayoutExtractor):
    def __init__(self, spec=IPPB_LAYOUT_1):
        super().__init__(spec, name="ippb_v2")
