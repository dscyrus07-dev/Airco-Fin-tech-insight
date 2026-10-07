import json

from app.services.statement_engine.extraction.spec_codec import spec_from_dict, spec_to_dict
from app.services.statement_engine.extractors.hdfc.layout_spec import HDFC_LAYOUT_A
from tests.statement_engine.extraction.test_generic_engine import ALPHA, BETA, GAMMA, alpha_rows, ALPHA_PERIOD, alpha_summary, page
from app.services.statement_engine.extraction.engine import extract_pages


def _same(a, b):
    ra = {**a.__dict__, "date_re": a.date_re.pattern, "amount_re": a.amount_re.pattern, "period_re": a.period_re.pattern,
          "ifsc_re": a.ifsc_re.pattern if a.ifsc_re else None}
    rb = {**b.__dict__, "date_re": b.date_re.pattern, "amount_re": b.amount_re.pattern, "period_re": b.period_re.pattern,
          "ifsc_re": b.ifsc_re.pattern if b.ifsc_re else None}
    return ra == rb


def test_roundtrip_through_json_for_all_layouts():
    for spec in (HDFC_LAYOUT_A, ALPHA, BETA, GAMMA):
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
