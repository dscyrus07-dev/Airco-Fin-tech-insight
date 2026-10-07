from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import ICICI_LAYOUT_1


class ICICIV2Extractor(LayoutExtractor):
    def __init__(self, spec=ICICI_LAYOUT_1):
        super().__init__(spec, name="icici_v2")


class ICICIV2Layout2Extractor(ICICIV2Extractor):
    def __init__(self):
        from .layout_spec import ICICI_LAYOUT_2
        super().__init__(ICICI_LAYOUT_2)
