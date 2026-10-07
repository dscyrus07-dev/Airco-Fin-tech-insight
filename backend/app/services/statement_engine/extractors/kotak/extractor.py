from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import KOTAK_LAYOUT_1, KOTAK_LAYOUT_2, KOTAK_LAYOUT_3


class KotakV2Extractor(LayoutExtractor):
    def __init__(self, spec=KOTAK_LAYOUT_1):
        super().__init__(spec, name="kotak_v2")


class KotakV2Layout2Extractor(KotakV2Extractor):
    def __init__(self):
        super().__init__(KOTAK_LAYOUT_2)


class KotakV2Layout3Extractor(KotakV2Extractor):
    def __init__(self):
        super().__init__(KOTAK_LAYOUT_3)
