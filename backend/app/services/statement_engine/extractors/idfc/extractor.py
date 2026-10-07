from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import IDFC_LAYOUT_1


class IDFCV2Extractor(LayoutExtractor):
    def __init__(self, spec=IDFC_LAYOUT_1):
        super().__init__(spec, name="idfc_v2")
