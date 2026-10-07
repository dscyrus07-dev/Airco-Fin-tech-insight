from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import CANARA_LAYOUT_1


class CanaraV2Extractor(LayoutExtractor):
    def __init__(self, spec=CANARA_LAYOUT_1):
        super().__init__(spec, name="canara_v2")


class CanaraV2Layout2Extractor(CanaraV2Extractor):
    def __init__(self):
        from .layout_spec import CANARA_LAYOUT_2
        super().__init__(CANARA_LAYOUT_2)
