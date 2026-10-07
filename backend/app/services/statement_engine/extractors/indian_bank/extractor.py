from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import INDIAN_BANK_LAYOUT_1


class IndianBankV2Extractor(LayoutExtractor):
    def __init__(self, spec=INDIAN_BANK_LAYOUT_1):
        super().__init__(spec, name="indian_bank_v2")
