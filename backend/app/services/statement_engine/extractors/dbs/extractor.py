from ...extraction.pdf_extractor import LayoutExtractor
from .layout_spec import DBS_LAYOUT_1


class DBSV2Extractor(LayoutExtractor):
    def __init__(self, spec=DBS_LAYOUT_1):
        super().__init__(spec, name="dbs_v2")
