from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import UJJIVAN_LAYOUT_1


class UjjivanV2Extractor(LayoutExtractor):
    def __init__(self, spec=UJJIVAN_LAYOUT_1):
        super().__init__(spec, name="ujjivan_v2")
