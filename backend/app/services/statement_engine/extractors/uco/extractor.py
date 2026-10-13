from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import UCO_LAYOUT_1, UCO_LAYOUT_2


class UcoV2Extractor(LayoutExtractor):
    def __init__(self, spec=UCO_LAYOUT_1):
        super().__init__(spec, name="uco_v2")
