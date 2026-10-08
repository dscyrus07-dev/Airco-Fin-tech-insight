from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import CBI_LAYOUT_1, CBI_LAYOUT_2


class CentralBankV2Extractor(LayoutExtractor):
    def __init__(self, spec=CBI_LAYOUT_1):
        super().__init__(spec, name="central_bank_v2")
