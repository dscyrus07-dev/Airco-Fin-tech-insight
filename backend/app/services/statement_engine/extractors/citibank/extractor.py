from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import CITIBANK_LAYOUT_1


class CitibankV2Extractor(LayoutExtractor):
    def __init__(self, spec=CITIBANK_LAYOUT_1):
        super().__init__(spec, name="citibank_v2")
