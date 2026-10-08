from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import IDBI_LAYOUT_1


class IDBIV2Extractor(LayoutExtractor):
    def __init__(self, spec=IDBI_LAYOUT_1):
        super().__init__(spec, name="idbi_v2")
