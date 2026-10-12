from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import AIRTEL_LAYOUT_1


class AirtelPbV2Extractor(LayoutExtractor):
    def __init__(self, spec=AIRTEL_LAYOUT_1):
        super().__init__(spec, name="airtel_pb_v2")
