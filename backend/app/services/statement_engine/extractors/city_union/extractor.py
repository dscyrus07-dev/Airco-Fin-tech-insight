from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import CUB_LAYOUT_1, CUB_LAYOUT_2


class CityUnionV2Extractor(LayoutExtractor):
    def __init__(self, spec=CUB_LAYOUT_1):
        super().__init__(spec, name="city_union_v2")
