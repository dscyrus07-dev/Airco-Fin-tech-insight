from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import IOB_LAYOUT_1


class IOBV2Extractor(LayoutExtractor):
    def __init__(self, spec=IOB_LAYOUT_1):
        super().__init__(spec, name="iob_v2")
