from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import AXIS_LAYOUT_1


class AxisV2Extractor(LayoutExtractor):
    def __init__(self, spec=AXIS_LAYOUT_1):
        super().__init__(spec, name="axis_v2")
