from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import BOB_LAYOUT_1


class BoBV2Extractor(LayoutExtractor):
    def __init__(self, spec=BOB_LAYOUT_1):
        super().__init__(spec, name="bob_v2")


class BoBV2Layout2Extractor(BoBV2Extractor):
    def __init__(self):
        from .layout_spec import BOB_LAYOUT_2
        super().__init__(BOB_LAYOUT_2)


class BoBV2Layout3Extractor(BoBV2Extractor):
    def __init__(self):
        from .layout_spec import BOB_LAYOUT_3
        super().__init__(BOB_LAYOUT_3)
