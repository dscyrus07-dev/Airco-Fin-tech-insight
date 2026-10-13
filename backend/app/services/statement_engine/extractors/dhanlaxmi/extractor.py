from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import DHANLAXMI_LAYOUT_1


class DhanlaxmiV2Extractor(LayoutExtractor):
    def __init__(self, spec=DHANLAXMI_LAYOUT_1):
        super().__init__(spec, name="dhanlaxmi_v2")
