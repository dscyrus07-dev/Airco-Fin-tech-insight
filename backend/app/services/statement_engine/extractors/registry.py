"""Default registry of the layouts available in this build."""
from ..extraction.registry import LayoutRegistry
from .hdfc.layout_spec import HDFC_LAYOUT_A
from .canara.layout_spec import CANARA_LAYOUT_1
from .axis.layout_spec import AXIS_LAYOUT_1
from .idfc.layout_spec import IDFC_LAYOUT_1
from .kotak.layout_spec import KOTAK_LAYOUT_1, KOTAK_LAYOUT_2, KOTAK_LAYOUT_3
from .federal.layout_spec import FEDERAL_LAYOUT_1
from .sbi.layout_spec import SBI_LAYOUT_1

DEFAULT_REGISTRY = LayoutRegistry([HDFC_LAYOUT_A, SBI_LAYOUT_1, CANARA_LAYOUT_1, AXIS_LAYOUT_1, IDFC_LAYOUT_1,
                                   KOTAK_LAYOUT_1, KOTAK_LAYOUT_2, KOTAK_LAYOUT_3, FEDERAL_LAYOUT_1])
