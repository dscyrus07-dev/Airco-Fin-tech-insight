"""Default registry of the layouts available in this build."""
from ..extraction.registry import LayoutRegistry
from .hdfc.layout_spec import HDFC_LAYOUT_A
from .canara.layout_spec import CANARA_LAYOUT_1, CANARA_LAYOUT_2, CANARA_LAYOUT_3, CANARA_LAYOUT_4
from .axis.layout_spec import AXIS_LAYOUT_1, AXIS_LAYOUT_2
from .idfc.layout_spec import IDFC_LAYOUT_1
from .kotak.layout_spec import KOTAK_LAYOUT_1, KOTAK_LAYOUT_2, KOTAK_LAYOUT_3, KOTAK_LAYOUT_4, KOTAK_LAYOUT_5, KOTAK_LAYOUT_6, KOTAK_LAYOUT_7, KOTAK_LAYOUT_8, KOTAK_LAYOUT_9
from .federal.layout_spec import FEDERAL_LAYOUT_1, FEDERAL_LAYOUT_2, FEDERAL_LAYOUT_3
from .bob.layout_spec import BOB_LAYOUT_1, BOB_LAYOUT_2, BOB_LAYOUT_3
from .icici.layout_spec import ICICI_LAYOUT_1, ICICI_LAYOUT_2, ICICI_LAYOUT_3, ICICI_LAYOUT_4
from .union.layout_spec import UNION_LAYOUT_1, UNION_LAYOUT_2, UNION_LAYOUT_3, UNION_LAYOUT_4, UNION_LAYOUT_5
from .paytm.layout_spec import PAYTM_LAYOUT_1
from .sbi.layout_spec import (SBI_LAYOUT_1, SBI_LAYOUT_2, SBI_LAYOUT_3, SBI_LAYOUT_4,
                            SBI_LAYOUT_5, SBI_LAYOUT_6, SBI_LAYOUT_7, SBI_LAYOUT_8)
from .scb.layout_spec import SCB_LAYOUT_1, SCB_LAYOUT_2
from ..extraction.registry import OTHER_BANK_MARKERS
from .indian_bank.layout_spec import INDIAN_BANK_LAYOUT_1, INDIAN_BANK_LAYOUT_2, INDIAN_BANK_LAYOUT_3
from .karnataka.layout_spec import KARNATAKA_LAYOUT_1
from .dbs.layout_spec import DBS_LAYOUT_1
from .citibank.layout_spec import CITIBANK_LAYOUT_1
from .kvb.layout_spec import KVB_LAYOUT_1
from .hsbc.layout_spec import HSBC_LAYOUT_1
from .indusind.layout_spec import INDUSIND_LAYOUT_1
from .idbi.layout_spec import IDBI_LAYOUT_1, IDBI_LAYOUT_2
from .pnb.layout_spec import PNB_LAYOUT_1
from .yes.layout_spec import YES_LAYOUT_1, YES_LAYOUT_2, YES_LAYOUT_3
from .iob.layout_spec import IOB_LAYOUT_1, IOB_LAYOUT_2
from .south_indian.layout_spec import SIB_LAYOUT_1
from .central_bank.layout_spec import CBI_LAYOUT_1, CBI_LAYOUT_2
from .equitas.layout_spec import EQUITAS_LAYOUT_1
from .city_union.layout_spec import CUB_LAYOUT_1, CUB_LAYOUT_2
from .ujjivan.layout_spec import UJJIVAN_LAYOUT_1
from .bom.layout_spec import BOM_LAYOUT_1, BOM_LAYOUT_2
from .bandhan.layout_spec import BANDHAN_LAYOUT_1, BANDHAN_LAYOUT_2
from .au_sfb.layout_spec import AU_LAYOUT_1
from .dcb.layout_spec import DCB_LAYOUT_1
from .apgv.layout_spec import APGV_LAYOUT_1

DEFAULT_REGISTRY = LayoutRegistry([HDFC_LAYOUT_A, SBI_LAYOUT_1, SBI_LAYOUT_3, SBI_LAYOUT_4, SBI_LAYOUT_5, SBI_LAYOUT_6, SBI_LAYOUT_7, SBI_LAYOUT_8, CANARA_LAYOUT_1, CANARA_LAYOUT_2, CANARA_LAYOUT_3, CANARA_LAYOUT_4, AXIS_LAYOUT_1, AXIS_LAYOUT_2, IDFC_LAYOUT_1,
                                   # SBI_LAYOUT_2 retired: dead code (0/12,249 corpus files route to it; 2,497 SBI-related files identical without it; L3 handles them)
                                   KOTAK_LAYOUT_1, KOTAK_LAYOUT_2, KOTAK_LAYOUT_3, KOTAK_LAYOUT_4, KOTAK_LAYOUT_5, KOTAK_LAYOUT_6, KOTAK_LAYOUT_7,
                                   # KOTAK_LAYOUT_8 parked: 0/9 files carried bank evidence
                                   # KOTAK_LAYOUT_9 parked: wrap-line side markers, unverifiable
                                   FEDERAL_LAYOUT_1,
                                   # FEDERAL_LAYOUT_2/3 parked: 0 VERIFIED across corpus (REVIEW/FAILED only)
                                   BOB_LAYOUT_1, BOB_LAYOUT_2, BOB_LAYOUT_3,
                                   # ICICI_LAYOUT_3/4 parked: 38%/41% trusted (stale-balance export prints fail chain honestly)
                                   ICICI_LAYOUT_1, ICICI_LAYOUT_2, UNION_LAYOUT_1, UNION_LAYOUT_2, UNION_LAYOUT_4, UNION_LAYOUT_5, PAYTM_LAYOUT_1, SCB_LAYOUT_1, SCB_LAYOUT_2, INDIAN_BANK_LAYOUT_1, INDIAN_BANK_LAYOUT_2,
                                   # INDIAN_BANK_LAYOUT_3 parked: 62%/56% trusted on build/hold-out (Mmm-first sub-variant embeds balances inside narration)
                                   KARNATAKA_LAYOUT_1, DBS_LAYOUT_1, CITIBANK_LAYOUT_1, KVB_LAYOUT_1, HSBC_LAYOUT_1, INDUSIND_LAYOUT_1, IDBI_LAYOUT_1, IDBI_LAYOUT_2, PNB_LAYOUT_1, YES_LAYOUT_1, YES_LAYOUT_3, IOB_LAYOUT_1, IOB_LAYOUT_2,
                                   # YES_LAYOUT_2 parked: wrapped 'Running|Balance' header routes 24% trusted (5V/16F chain+side) on fresh 97-file re-measure
                                   SIB_LAYOUT_1, CBI_LAYOUT_1, CBI_LAYOUT_2, EQUITAS_LAYOUT_1, CUB_LAYOUT_1, CUB_LAYOUT_2, UJJIVAN_LAYOUT_1, BOM_LAYOUT_1, BOM_LAYOUT_2, BANDHAN_LAYOUT_1, BANDHAN_LAYOUT_2, AU_LAYOUT_1, DCB_LAYOUT_1, APGV_LAYOUT_1],
                                  foreign_markers=OTHER_BANK_MARKERS)
