from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import AU_LAYOUT_1


class AuSfbV2Extractor(LayoutExtractor):
    def __init__(self, spec=AU_LAYOUT_1):
        super().__init__(spec, name="au_sfb_v2")
