from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import UNION_LAYOUT_1


class UnionV2Extractor(LayoutExtractor):
    def __init__(self, spec=UNION_LAYOUT_1):
        super().__init__(spec, name="union_v2")
