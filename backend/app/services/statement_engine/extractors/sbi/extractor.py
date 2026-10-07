from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import SBI_LAYOUT_1


class SBIV2Extractor(LayoutExtractor):
    def __init__(self, spec=SBI_LAYOUT_1):
        super().__init__(spec, name="sbi_v2")
