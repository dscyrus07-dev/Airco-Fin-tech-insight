from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import APGV_LAYOUT_1


class ApgvV2Extractor(LayoutExtractor):
    def __init__(self, spec=APGV_LAYOUT_1):
        super().__init__(spec, name="apgv_v2")
