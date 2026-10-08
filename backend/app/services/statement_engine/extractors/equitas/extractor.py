from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import EQUITAS_LAYOUT_1


class EquitasV2Extractor(LayoutExtractor):
    def __init__(self, spec=EQUITAS_LAYOUT_1):
        super().__init__(spec, name="equitas_v2")
