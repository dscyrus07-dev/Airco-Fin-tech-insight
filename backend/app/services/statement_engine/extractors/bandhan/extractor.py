from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import BANDHAN_LAYOUT_1


class BandhanV2Extractor(LayoutExtractor):
    def __init__(self, spec=BANDHAN_LAYOUT_1):
        super().__init__(spec, name="bandhan_v2")
