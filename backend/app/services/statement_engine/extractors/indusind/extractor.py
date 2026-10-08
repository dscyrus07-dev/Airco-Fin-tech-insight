from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import INDUSIND_LAYOUT_1


class IndusIndV2Extractor(LayoutExtractor):
    def __init__(self, spec=INDUSIND_LAYOUT_1):
        super().__init__(spec, name="indusind_v2")
