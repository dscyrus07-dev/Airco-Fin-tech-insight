"""Default registry of the layouts available in this build."""
from ..extraction.registry import LayoutRegistry
from .hdfc.layout_spec import HDFC_LAYOUT_A
from .canara.layout_spec import CANARA_LAYOUT_1
from .axis.layout_spec import AXIS_LAYOUT_1
from .idfc.layout_spec import IDFC_LAYOUT_1
from .kotak.layout_spec import KOTAK_LAYOUT_1, KOTAK_LAYOUT_2, KOTAK_LAYOUT_3
from .federal.layout_spec import FEDERAL_LAYOUT_1
from .bob.layout_spec import BOB_LAYOUT_1, BOB_LAYOUT_2, BOB_LAYOUT_3
from .icici.layout_spec import ICICI_LAYOUT_1, ICICI_LAYOUT_2
from .union.layout_spec import UNION_LAYOUT_1
from .paytm.layout_spec import PAYTM_LAYOUT_1
from .sbi.layout_spec import SBI_LAYOUT_1
from .scb.layout_spec import SCB_LAYOUT_1, SCB_LAYOUT_2
from ..extraction.registry import OTHER_BANK_MARKERS
from .indian_bank.layout_spec import INDIAN_BANK_LAYOUT_1
from .karnataka.layout_spec import KARNATAKA_LAYOUT_1
from .dbs.layout_spec import DBS_LAYOUT_1
from .citibank.layout_spec import CITIBANK_LAYOUT_1
from .kvb.layout_spec import KVB_LAYOUT_1

DEFAULT_REGISTRY = LayoutRegistry([HDFC_LAYOUT_A, SBI_LAYOUT_1, CANARA_LAYOUT_1, AXIS_LAYOUT_1, IDFC_LAYOUT_1,
                                   KOTAK_LAYOUT_1, KOTAK_LAYOUT_2, KOTAK_LAYOUT_3, FEDERAL_LAYOUT_1,
                                   BOB_LAYOUT_1, BOB_LAYOUT_2, BOB_LAYOUT_3,
                                   ICICI_LAYOUT_1, ICICI_LAYOUT_2, UNION_LAYOUT_1, PAYTM_LAYOUT_1, SCB_LAYOUT_1, SCB_LAYOUT_2, INDIAN_BANK_LAYOUT_1, KARNATAKA_LAYOUT_1, DBS_LAYOUT_1, CITIBANK_LAYOUT_1, KVB_LAYOUT_1],
                                  foreign_markers=OTHER_BANK_MARKERS)
