from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import BOM_LAYOUT_1


class BankOfMaharashtraV2Extractor(LayoutExtractor):
    def __init__(self, spec=BOM_LAYOUT_1):
        super().__init__(spec, name="bom_v2")
