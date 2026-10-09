import json

from app.services.statement_engine.extraction.spec_codec import spec_from_dict, spec_to_dict
from app.services.statement_engine.extractors.hdfc.layout_spec import HDFC_LAYOUT_A
from app.services.statement_engine.extractors.sbi.layout_spec import SBI_LAYOUT_1
from app.services.statement_engine.extractors.axis.layout_spec import AXIS_LAYOUT_1
from app.services.statement_engine.extractors.idfc.layout_spec import IDFC_LAYOUT_1
from app.services.statement_engine.extractors.kotak.layout_spec import KOTAK_LAYOUT_1, KOTAK_LAYOUT_2, KOTAK_LAYOUT_3
from app.services.statement_engine.extractors.federal.layout_spec import FEDERAL_LAYOUT_1
from app.services.statement_engine.extractors.icici.layout_spec import ICICI_LAYOUT_1, ICICI_LAYOUT_2
from app.services.statement_engine.extractors.scb.layout_spec import SCB_LAYOUT_1, SCB_LAYOUT_2
from app.services.statement_engine.extractors.indian_bank.layout_spec import INDIAN_BANK_LAYOUT_1, INDIAN_BANK_LAYOUT_2
from app.services.statement_engine.extractors.karnataka.layout_spec import KARNATAKA_LAYOUT_1
from app.services.statement_engine.extractors.union.layout_spec import UNION_LAYOUT_1
from app.services.statement_engine.extractors.paytm.layout_spec import PAYTM_LAYOUT_1
from app.services.statement_engine.extractors.canara.layout_spec import CANARA_LAYOUT_1
from app.services.statement_engine.extractors.bob.layout_spec import BOB_LAYOUT_1, BOB_LAYOUT_2, BOB_LAYOUT_3
from app.services.statement_engine.extractors.idbi.layout_spec import IDBI_LAYOUT_1, IDBI_LAYOUT_2
from app.services.statement_engine.extractors.pnb.layout_spec import PNB_LAYOUT_1
from app.services.statement_engine.extractors.yes.layout_spec import YES_LAYOUT_1
from app.services.statement_engine.extractors.iob.layout_spec import IOB_LAYOUT_1, IOB_LAYOUT_2
from app.services.statement_engine.extractors.south_indian.layout_spec import SIB_LAYOUT_1
from app.services.statement_engine.extractors.central_bank.layout_spec import CBI_LAYOUT_1, CBI_LAYOUT_2
from app.services.statement_engine.extractors.equitas.layout_spec import EQUITAS_LAYOUT_1
from app.services.statement_engine.extractors.city_union.layout_spec import CUB_LAYOUT_1, CUB_LAYOUT_2
from app.services.statement_engine.extractors.ujjivan.layout_spec import UJJIVAN_LAYOUT_1
from app.services.statement_engine.extractors.bom.layout_spec import BOM_LAYOUT_1, BOM_LAYOUT_2
from app.services.statement_engine.extractors.bandhan.layout_spec import BANDHAN_LAYOUT_1, BANDHAN_LAYOUT_2
from app.services.statement_engine.extractors.au_sfb.layout_spec import AU_LAYOUT_1
from app.services.statement_engine.extractors.dcb.layout_spec import DCB_LAYOUT_1
from app.services.statement_engine.extractors.apgv.layout_spec import APGV_LAYOUT_1
from tests.statement_engine.extraction.test_generic_engine import ALPHA, BETA, GAMMA, DELTA, alpha_rows, ALPHA_PERIOD, alpha_summary, page
from app.services.statement_engine.extraction.engine import extract_pages


def _same(a, b):
    def norm(x):
        d = dict(x.__dict__)
        for k, v in d.items():
            if hasattr(v, "pattern"):
                d[k] = (v.pattern, v.flags)
            elif isinstance(v, tuple) and v and hasattr(v[0], "pattern"):
                d[k] = tuple((r.pattern, r.flags) for r in v)
        return d
    return norm(a) == norm(b)


def test_roundtrip_through_json_for_all_layouts():
    for spec in (HDFC_LAYOUT_A, SBI_LAYOUT_1, CANARA_LAYOUT_1, AXIS_LAYOUT_1, IDFC_LAYOUT_1, KOTAK_LAYOUT_1, KOTAK_LAYOUT_2, KOTAK_LAYOUT_3, FEDERAL_LAYOUT_1, BOB_LAYOUT_1, BOB_LAYOUT_2, BOB_LAYOUT_3, ICICI_LAYOUT_1, ICICI_LAYOUT_2, UNION_LAYOUT_1, PAYTM_LAYOUT_1, SCB_LAYOUT_1, SCB_LAYOUT_2, INDIAN_BANK_LAYOUT_1, INDIAN_BANK_LAYOUT_2, KARNATAKA_LAYOUT_1, IDBI_LAYOUT_1, IDBI_LAYOUT_2, PNB_LAYOUT_1, YES_LAYOUT_1, IOB_LAYOUT_1, IOB_LAYOUT_2, SIB_LAYOUT_1, CBI_LAYOUT_1, CBI_LAYOUT_2, EQUITAS_LAYOUT_1, CUB_LAYOUT_1, CUB_LAYOUT_2, UJJIVAN_LAYOUT_1, BOM_LAYOUT_1, BOM_LAYOUT_2, BANDHAN_LAYOUT_1, BANDHAN_LAYOUT_2, AU_LAYOUT_1, DCB_LAYOUT_1, APGV_LAYOUT_1, ALPHA, BETA, GAMMA, DELTA):
        again = spec_from_dict(json.loads(json.dumps(spec_to_dict(spec))))
        assert _same(spec, again), spec.layout_id


def test_spec_from_database_json_extracts_like_the_original():
    spec = spec_from_dict(json.loads(json.dumps(spec_to_dict(ALPHA))))
    out = extract_pages([page(ALPHA, alpha_rows(), ALPHA_PERIOD, alpha_summary())], spec)
    assert out.checks.verdict == "VERIFIED"


def test_invalid_configs_are_rejected():
    good = spec_to_dict(ALPHA)
    for mutate in (lambda d: d.pop("columns"), lambda d: d.update(date_re="("), lambda d: d.update(config_version=99),
                   lambda d: d.update(text_columns=["date"])):
        d = json.loads(json.dumps(good)); mutate(d)
        try:
            spec_from_dict(d)
        except ValueError:
            continue
        raise AssertionError("invalid config accepted")
