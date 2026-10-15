"""Default registry of the layouts available in this build."""
from ..extraction.registry import LayoutRegistry
from .hdfc.layout_spec import HDFC_LAYOUT_A, HDFC_LAYOUT_B
from .canara.layout_spec import CANARA_LAYOUT_1, CANARA_LAYOUT_2, CANARA_LAYOUT_3, CANARA_LAYOUT_4
from .axis.layout_spec import AXIS_LAYOUT_1, AXIS_LAYOUT_2, AXIS_LAYOUT_3, AXIS_LAYOUT_4
from .idfc.layout_spec import IDFC_LAYOUT_1
from .kotak.layout_spec import KOTAK_LAYOUT_1, KOTAK_LAYOUT_2, KOTAK_LAYOUT_3, KOTAK_LAYOUT_4, KOTAK_LAYOUT_5, KOTAK_LAYOUT_6, KOTAK_LAYOUT_7, KOTAK_LAYOUT_8, KOTAK_LAYOUT_9
from .federal.layout_spec import FEDERAL_LAYOUT_1, FEDERAL_LAYOUT_2, FEDERAL_LAYOUT_3, FEDERAL_LAYOUT_4, FEDERAL_LAYOUT_5
from .bob.layout_spec import BOB_LAYOUT_1, BOB_LAYOUT_2, BOB_LAYOUT_3
from .icici.layout_spec import ICICI_LAYOUT_1, ICICI_LAYOUT_2, ICICI_LAYOUT_3, ICICI_LAYOUT_4, ICICI_LAYOUT_5
from .union.layout_spec import UNION_LAYOUT_1, UNION_LAYOUT_2, UNION_LAYOUT_3, UNION_LAYOUT_4, UNION_LAYOUT_5
from .paytm.layout_spec import PAYTM_LAYOUT_1, PAYTM_LAYOUT_2
from .sbi.layout_spec import (SBI_LAYOUT_1, SBI_LAYOUT_2, SBI_LAYOUT_3, SBI_LAYOUT_4,
                            SBI_LAYOUT_5, SBI_LAYOUT_6, SBI_LAYOUT_7, SBI_LAYOUT_8, SBI_LAYOUT_9, SBI_LAYOUT_10)
from .scb.layout_spec import SCB_LAYOUT_1, SCB_LAYOUT_2
from ..extraction.registry import OTHER_BANK_MARKERS
from .indian_bank.layout_spec import INDIAN_BANK_LAYOUT_1, INDIAN_BANK_LAYOUT_2, INDIAN_BANK_LAYOUT_3
from .karnataka.layout_spec import KARNATAKA_LAYOUT_1
from .dbs.layout_spec import DBS_LAYOUT_1, DBS_LAYOUT_2, DBS_LAYOUT_3, DBS_LAYOUT_4
from .citibank.layout_spec import CITIBANK_LAYOUT_1
from .kvb.layout_spec import KVB_LAYOUT_1
from .hsbc.layout_spec import HSBC_LAYOUT_1, HSBC_LAYOUT_2
from .indusind.layout_spec import INDUSIND_LAYOUT_1, INDUSIND_LAYOUT_2, INDUSIND_LAYOUT_3, INDUSIND_LAYOUT_4
from .idbi.layout_spec import IDBI_LAYOUT_1, IDBI_LAYOUT_2, IDBI_LAYOUT_3, IDBI_LAYOUT_4, IDBI_LAYOUT_5, IDBI_LAYOUT_6
from .pnb.layout_spec import PNB_LAYOUT_1, PNB_LAYOUT_2, PNB_LAYOUT_3
from .yes.layout_spec import YES_LAYOUT_1, YES_LAYOUT_2, YES_LAYOUT_3, YES_LAYOUT_4, YES_LAYOUT_5
from .iob.layout_spec import IOB_LAYOUT_1, IOB_LAYOUT_2
from .south_indian.layout_spec import SIB_LAYOUT_1
from .central_bank.layout_spec import CBI_LAYOUT_1, CBI_LAYOUT_2, CBI_LAYOUT_3, CBI_LAYOUT_4
from .equitas.layout_spec import EQUITAS_LAYOUT_1, EQUITAS_LAYOUT_2, EQUITAS_LAYOUT_3
from .city_union.layout_spec import CUB_LAYOUT_1, CUB_LAYOUT_2
from .ujjivan.layout_spec import UJJIVAN_LAYOUT_1
from .bom.layout_spec import BOM_LAYOUT_1, BOM_LAYOUT_2, BOM_LAYOUT_3, BOM_LAYOUT_4
from .bandhan.layout_spec import BANDHAN_LAYOUT_1, BANDHAN_LAYOUT_2, BANDHAN_LAYOUT_3, BANDHAN_LAYOUT_4
from .au_sfb.layout_spec import AU_LAYOUT_1, AU_LAYOUT_2
from .dcb.layout_spec import DCB_LAYOUT_1
from .apgv.layout_spec import APGV_LAYOUT_1
from .csb.layout_spec import CSB_LAYOUT_1, CSB_LAYOUT_2, CSB_LAYOUT_3
from .airtel_pb.layout_spec import AIRTEL_LAYOUT_1
from .ippb.layout_spec import IPPB_LAYOUT_1
from .dhanlaxmi.layout_spec import DHANLAXMI_LAYOUT_1, DHANLAXMI_LAYOUT_2, DHANLAXMI_LAYOUT_3
from .bank_of_india.layout_spec import BANK_OF_INDIA_LAYOUT_1, BANK_OF_INDIA_LAYOUT_2
from .uco.layout_spec import UCO_LAYOUT_1, UCO_LAYOUT_2, UCO_LAYOUT_3, UCO_LAYOUT_4

DEFAULT_REGISTRY = LayoutRegistry([HDFC_LAYOUT_A, HDFC_LAYOUT_B, SBI_LAYOUT_1, SBI_LAYOUT_3, SBI_LAYOUT_4, SBI_LAYOUT_5, SBI_LAYOUT_6, SBI_LAYOUT_7, SBI_LAYOUT_8, SBI_LAYOUT_9, SBI_LAYOUT_10, CANARA_LAYOUT_1, CANARA_LAYOUT_2, CANARA_LAYOUT_3, CANARA_LAYOUT_4, AXIS_LAYOUT_1, AXIS_LAYOUT_2, AXIS_LAYOUT_3, AXIS_LAYOUT_4, IDFC_LAYOUT_1,
                                   # SBI_LAYOUT_2 retired: dead code (0/12,249 corpus files route to it; 2,497 SBI-related files identical without it; L3 handles them)
                                   KOTAK_LAYOUT_1, KOTAK_LAYOUT_2, KOTAK_LAYOUT_3, KOTAK_LAYOUT_4, KOTAK_LAYOUT_5, KOTAK_LAYOUT_6, KOTAK_LAYOUT_7,
                                   # wave7: KOTAK_LAYOUT_8/9 unparked — original park reason was "no bank evidence" in a
                                   # detector-less measure; the detector identifies this export family VERY_HIGH (evidence
                                   # "detector"), and foreign-marker refusal still applies, so routing is evidence-gated
                                   KOTAK_LAYOUT_8, KOTAK_LAYOUT_9,
                                   FEDERAL_LAYOUT_1, FEDERAL_LAYOUT_2, FEDERAL_LAYOUT_3,
                                   # wave7: L2/L3 unparked — their printed opening balance now anchors both ends
                                   # (park reason "0 VERIFIED" predates anchor_full; honesty preserved by REVIEW cap)
                                   BOB_LAYOUT_1, BOB_LAYOUT_2, BOB_LAYOUT_3,
                                   # ICICI_LAYOUT_3/4 parked: 38%/41% trusted (stale-balance export prints fail chain honestly)
                                   ICICI_LAYOUT_1, ICICI_LAYOUT_2,
                                   # wave10: L5 two-line-header ICICI export ("amountinr withdrawal" merge order) —
                                   # chains clean on sample, anchorless family so REVIEW is its ceiling
                                   ICICI_LAYOUT_5,
                                   UNION_LAYOUT_1, UNION_LAYOUT_2, UNION_LAYOUT_4, UNION_LAYOUT_5, PAYTM_LAYOUT_1,
                                   # wave10: L2 debit/credit export ("Transaction Date|Instrument Id|Narration|Debit|Credit|
                                   # Balance", dd-Mmm-yyyy, '-' empties) — anchorless, REVIEW ceiling
                                   PAYTM_LAYOUT_2, SCB_LAYOUT_1, SCB_LAYOUT_2, INDIAN_BANK_LAYOUT_1, INDIAN_BANK_LAYOUT_2,
                                   # INDIAN_BANK_LAYOUT_3 parked: 62%/56% trusted on build/hold-out (Mmm-first sub-variant embeds balances inside narration)
                                   KARNATAKA_LAYOUT_1, DBS_LAYOUT_1, CITIBANK_LAYOUT_1, KVB_LAYOUT_1, HSBC_LAYOUT_1, HSBC_LAYOUT_2, INDUSIND_LAYOUT_1,
                                   # unblock-1: IndusInd newer export ("Chq No/Ref No" ref title, B/F+C/F anchor rows,
                                   # 0.00-empty money cells; dashed and space-separated date prints)
                                   INDUSIND_LAYOUT_2, INDUSIND_LAYOUT_3, IDBI_LAYOUT_1, IDBI_LAYOUT_2, IDBI_LAYOUT_4, IDBI_LAYOUT_5, PNB_LAYOUT_1, YES_LAYOUT_1, YES_LAYOUT_3, YES_LAYOUT_4, IOB_LAYOUT_1, IOB_LAYOUT_2,
                                   # n1: IDBI_LAYOUT_3 unblocked by period-suffixed Dr./Cr. side markers;
                                   # PNB L2/L3 = landscape passbook header over 2-3 interleaved lines;
                                   # YES_LAYOUT_5 = 3-line interleaved header + three-word date cells;
                                   # CBI_LAYOUT_4 = 15-column header over 3 lines with mid-word splits
                                   IDBI_LAYOUT_3, PNB_LAYOUT_2, PNB_LAYOUT_3, YES_LAYOUT_5, CBI_LAYOUT_4,
                                   # n2: IDBI_LAYOUT_6 = balance-less 'Date|Description|Amount|Type' export
                                   #     (Type marker on the dated line, amount on the continuation line)
                                   IDBI_LAYOUT_6,
                                   # YES_LAYOUT_2 parked: wrapped 'Running|Balance' header routes 24% trusted (5V/16F chain+side) on fresh 97-file re-measure
                                   SIB_LAYOUT_1, CBI_LAYOUT_1, CBI_LAYOUT_2, CBI_LAYOUT_3, EQUITAS_LAYOUT_1, EQUITAS_LAYOUT_2, EQUITAS_LAYOUT_3, CUB_LAYOUT_1, CUB_LAYOUT_2, UJJIVAN_LAYOUT_1, BOM_LAYOUT_1, BOM_LAYOUT_2, BANDHAN_LAYOUT_1, BANDHAN_LAYOUT_2, BANDHAN_LAYOUT_3, BANDHAN_LAYOUT_4, AU_LAYOUT_1,
                                   # promote-1: AU newer export (wrapped 2-line header, rupee-marked money cols, AUBANK.IN footer marker)
                                   AU_LAYOUT_2,
                                   DBS_LAYOUT_2, DBS_LAYOUT_3,
                                   BOM_LAYOUT_3, BOM_LAYOUT_4, DCB_LAYOUT_1, APGV_LAYOUT_1,
                                   # onboard-all: CSB "Statement of Account" export (federal-shaped; CSB marker evidence)
                                   CSB_LAYOUT_1, CSB_LAYOUT_2, CSB_LAYOUT_3,
                                   # onboard-all: UCO "Statement of Account" exports (with/without instrument column)
                                   UCO_LAYOUT_1, UCO_LAYOUT_2, UCO_LAYOUT_3, UCO_LAYOUT_4, AIRTEL_LAYOUT_1, IPPB_LAYOUT_1, DHANLAXMI_LAYOUT_1, DHANLAXMI_LAYOUT_2, DHANLAXMI_LAYOUT_3,
                                   # n3: FEDERAL_LAYOUT_4 = Fi/Jupiter app export (section dates, derived sides)
                                   #     FEDERAL_LAYOUT_5 = same family, "Reference ID" left column + apostrophe-year
                                   #     section labels + currency-marked cells + truncated Money out/in summary
                                   FEDERAL_LAYOUT_4, FEDERAL_LAYOUT_5,
                                   # n5: INDUSIND_LAYOUT_4 = 'DATE|TYPE|DESCRIPTION|DEBIT|CREDIT|BALANCE'
                                   #     two-line export (type/narration line above the dated amount line)
                                   INDUSIND_LAYOUT_4,
                                   # n5: DBS_LAYOUT_4 = balance-less 'Details of Transaction' with yearless
                                   #     '02 Jul' rows; year from the printed Transaction History period
                                   DBS_LAYOUT_4,
                                   # n6: Bank of India "DetailedStatement" web export.
                                   # BANK_OF_INDIA_LAYOUT_1 parked: branch passbook prints every line as ONE glued
                                   # word; find_header runs before _split_monospace, so the header can never
                                   # match (same gap as central_bank glued files, ENGINE_GAPS §3).
                                   BANK_OF_INDIA_LAYOUT_2],
                                  foreign_markers=OTHER_BANK_MARKERS)
