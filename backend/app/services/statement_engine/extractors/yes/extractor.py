from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import YES_LAYOUT_1


class YesV2Extractor(LayoutExtractor):
    def __init__(self, spec=YES_LAYOUT_1):
        super().__init__(spec, name="yes_v2")
