from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import DCB_LAYOUT_1


class DcbV2Extractor(LayoutExtractor):
    def __init__(self, spec=DCB_LAYOUT_1):
        super().__init__(spec, name="dcb_v2")
