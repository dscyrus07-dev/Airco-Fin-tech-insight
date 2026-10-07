import json

from app.services.statement_engine.extraction.spec_codec import spec_from_dict, spec_to_dict
from app.services.statement_engine.extractors.hdfc.layout_spec import HDFC_LAYOUT_A
from app.services.statement_engine.extractors.sbi.layout_spec import SBI_LAYOUT_1
from app.services.statement_engine.extractors.axis.layout_spec import AXIS_LAYOUT_1
from app.services.statement_engine.extractors.idfc.layout_spec import IDFC_LAYOUT_1
from app.services.statement_engine.extractors.kotak.layout_spec import KOTAK_LAYOUT_1, KOTAK_LAYOUT_2, KOTAK_LAYOUT_3
from app.services.statement_engine.extractors.canara.layout_spec import CANARA_LAYOUT_1
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
    for spec in (HDFC_LAYOUT_A, SBI_LAYOUT_1, CANARA_LAYOUT_1, AXIS_LAYOUT_1, IDFC_LAYOUT_1, KOTAK_LAYOUT_1, KOTAK_LAYOUT_2, KOTAK_LAYOUT_3, ALPHA, BETA, GAMMA, DELTA):
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
