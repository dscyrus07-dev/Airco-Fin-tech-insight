"""Guards against bank-marker collisions found in the overnight verification (Paytm refused as foreign because
a bare IFSC prefix of another bank sat in its header region). Synthetic pages only."""
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extractors.paytm.layout_spec import PAYTM_LAYOUT_1 as SPEC
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, header, row, w


def test_spec_markers_are_not_bare_ifsc_prefixes():
    """A bank marker must be a name-like token (>= 7 chars). 4-letter IFSC prefixes such as IPPB/HDFC appear in
    counterparty codes inside page headers and narration and would make unrelated banks look foreign."""
    legacy = {"AUBL", "HSBC", "SBIN0"}  # present before the all-banks onboarding; behaviour pinned by the regression corpus
    bad = sorted({m for sp in DEFAULT_REGISTRY._specs.values() for m in sp.bank_markers if len(m) < 7} - legacy)
    assert not bad, f"short bank markers collide with IFSC prefixes: {bad}"


def test_counterparty_ifsc_codes_in_header_region_do_not_refuse_a_bank_with_no_printed_name():
    codes = [w("IPPB0000001", 30, 40), w("UCBA0000001", 150, 40), w("CSBK0000001", 270, 40)]
    ws = list(codes) + header(SPEC)
    ws += row(SPEC, 220, "UPIREF1234", debit="100.00", balance="900.00")
    ws += row(SPEC, 236, "NEFTSALARY5678", credit="1,000.00", balance="1,900.00")
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY, "paytm")
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_indian_bank_marker_inside_south_indian_bank_name_is_not_indian_bank_evidence():
    from app.services.statement_engine.extraction import registry as r
    assert r._strip("HEADER SOUTHINDIANBANK LTD", ["SOUTHINDIANBANK"]).count("INDIANBANK") == 0
    from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
    sib = DEFAULT_REGISTRY.for_bank("south_indian")
    assert sib and all("SOUTHINDIANBANK" in s.bank_markers for s in sib)
