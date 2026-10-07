from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import KARNATAKA_LAYOUT_1


class KarnatakaV2Extractor(LayoutExtractor):
    def __init__(self, spec=KARNATAKA_LAYOUT_1):
        super().__init__(spec, name="karnataka_v2")
