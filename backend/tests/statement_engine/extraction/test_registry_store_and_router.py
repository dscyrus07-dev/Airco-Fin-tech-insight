"""Registry rows <-> LayoutRegistry, seed script shape, and the v2 router's explicit fallback reasons."""
import json
import re
from dataclasses import replace

from app.services.statement_engine.extraction.layout_spec import LayoutSpec
from app.services.statement_engine.extraction.registry import LayoutRegistry
from app.services.statement_engine.extraction.registry_store import family_code, registry_from_rows, registry_to_rows, seed_sql
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extraction.words import Word
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.v2_router import route_pages


def test_default_registry_round_trips_through_rows_with_identical_specs():
    rows = registry_to_rows(DEFAULT_REGISTRY)
    again = registry_from_rows([{**r, "config_json": json.dumps(r["config_json"])} for r in rows])   # JSON string form as Postgres returns it
    assert [s.layout_id for s in again.specs()] == [s.layout_id for s in DEFAULT_REGISTRY.specs()]
    for a, b in zip(DEFAULT_REGISTRY.specs(), again.specs()):
        assert a == b, a.layout_id


def test_inactive_rows_are_skipped_and_priority_orders_the_registry():
    rows = registry_to_rows(DEFAULT_REGISTRY)
    rows[0]["active"] = False
    rows[1]["priority"], rows[2]["priority"] = max(r["priority"] for r in rows) + 10, 1
    reg = registry_from_rows(rows)
    ids = [s.layout_id for s in reg.specs()]
    assert rows[0]["layout_id"] not in ids and ids[0] == rows[2]["layout_id"] and ids[-1] == rows[1]["layout_id"]


def test_row_whose_layout_id_disagrees_with_its_configuration_is_refused():
    rows = registry_to_rows(DEFAULT_REGISTRY)
    rows[0]["layout_id"] = "somethingelse"
    try:
        registry_from_rows(rows[:1])
    except ValueError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("mismatch accepted")


def test_seed_sql_is_idempotent_and_never_deletes():
    sql = seed_sql(DEFAULT_REGISTRY)
    assert sql.startswith("BEGIN;") and sql.rstrip().endswith("COMMIT;")
    assert "ON CONFLICT (layout_id) DO UPDATE" in sql and "ON CONFLICT (code)" in sql
    assert not re.search(r"\b(DELETE|DROP|TRUNCATE)\b", sql, re.I)
    assert sql.count("INSERT INTO public.bank_layouts") == len(DEFAULT_REGISTRY.specs())


def test_family_code_groups_layouts_by_structure_not_by_bank():
    codes = {family_code(s) for s in DEFAULT_REGISTRY.specs()}
    assert len(codes) < len(DEFAULT_REGISTRY.specs())


def _spec(layout_id, bank_key, markers):
    from tests.statement_engine.extraction.test_generic_engine import ALPHA
    return replace(ALPHA, layout_id=layout_id, bank_key=bank_key, bank_markers=markers)


def test_router_reports_unsupported_for_pages_without_a_text_layer():
    routed = route_pages([Page([], 595.0)], DEFAULT_REGISTRY)
    assert routed.status == "unsupported" and routed.fallback_reason == "scanned_no_text" and not routed.use_v2


def test_router_reports_no_layout_with_an_explicit_reason():
    routed = route_pages([Page([Word("hello", 10, 40, 10, 18)], 595.0)], DEFAULT_REGISTRY)
    assert routed.status == "fallback" and routed.fallback_reason == "no_layout" and routed.result is None and not routed.use_v2


def test_router_routes_a_resolved_layout_through_the_engine():
    from tests.statement_engine.extraction.test_generic_engine import ALPHA, ALPHA_PERIOD, header, rt, w
    ws = list(ALPHA_PERIOD) + header(ALPHA) + [w("01-04-2022", 30, 220), w("SHOP", 120, 220), rt("100.00", 400, 220), rt("900.00", 560, 220)]
    # no bank name on the page and no detector bank: a header match alone is not trusted
    unconfirmed = route_pages([Page(ws, 600.0)], LayoutRegistry([ALPHA]))
    assert unconfirmed.status == "fallback" and unconfirmed.fallback_reason == "bank_unconfirmed" and not unconfirmed.use_v2
    routed = route_pages([Page(ws, 600.0)], LayoutRegistry([ALPHA]), ALPHA.bank_key)     # the detector names the same bank
    assert routed.status == "v2" and routed.layout_id == ALPHA.layout_id and routed.use_v2
    assert len(routed.result.transactions) == 1


def test_seed_sql_update_only_when_config_changed():
    from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
    from app.services.statement_engine.extraction.registry_store import seed_sql
    for line in seed_sql(DEFAULT_REGISTRY).splitlines():
        if "INTO public.bank_layouts" in line:
            assert "IS DISTINCT FROM EXCLUDED.config_json" in line


def _alpha_pages():
    from tests.statement_engine.extraction.test_generic_engine import ALPHA, ALPHA_PERIOD, header, rt, w
    ws = list(ALPHA_PERIOD) + header(ALPHA) + [w("01-04-2022", 30, 220), w("SHOP", 120, 220), rt("100.00", 400, 220), rt("900.00", 560, 220)]
    return ALPHA, [Page(ws, 600.0)]


def test_header_only_match_is_opt_in():
    alpha, pages = _alpha_pages()
    r = route_pages(pages, LayoutRegistry([alpha]), allow_header_only=True)
    assert r.status == "v2" and "bank_evidence:none" in r.notes


def test_other_bank_name_on_the_page_refuses_a_shared_header():
    from tests.statement_engine.extraction.test_generic_engine import w
    alpha, pages = _alpha_pages()
    pages[0].words.insert(0, w("YESBANK", 30, 5))
    assert LayoutRegistry([alpha], foreign_markers=("YESBANK",)).resolve(pages).status == "foreign_bank"
    assert LayoutRegistry([alpha]).resolve(pages).status == "resolved"          # without the global list nothing is known


def _detector_pages(*lines):
    """One Page whose words group into the given text lines (drives the real Slice 2 detector)."""
    from tests.statement_engine.extraction.test_generic_engine import w
    ws = []
    for i, ln in enumerate(lines):
        x = 30.0
        for tok in ln.split():
            ws.append(w(tok, x, 10 + i * 12))
            x += 5.5 * len(tok) + 12
    return [Page(ws, 600.0)]


def test_legacy_only_bank_falls_back_before_layout_resolution():
    alpha, _ = _alpha_pages()
    pages = _detector_pages("Bank of India", "Detailed Statement", "IFSC: BKID0000123",
                            "Txn Date Particulars Debit Credit Balance",
                            *["01-04-2021 PAYMENT 100.00 5000.00"] * 30)
    r = route_pages(pages, LayoutRegistry([alpha]), use_detector=True)
    assert r.status == "fallback" and r.fallback_reason == "legacy_only:bank_of_india" and r.result is None


def test_legacy_only_hold_is_not_overridden_by_header_only_mode():
    alpha, _ = _alpha_pages()
    pages = _detector_pages("Bank of India", "Detailed Statement", "IFSC: BKID0000123",
                            "Txn Date Particulars Debit Credit Balance",
                            *["01-04-2021 PAYMENT 100.00 5000.00"] * 30)
    r = route_pages(pages, LayoutRegistry([alpha]), use_detector=True, allow_header_only=True)
    assert r.status == "fallback" and r.fallback_reason == "legacy_only:bank_of_india"


def test_legacy_only_hold_does_not_catch_other_india_banks():
    from tests.statement_engine.extraction.test_generic_engine import ALPHA
    for brand, ifsc in (("State Bank of India", "SBIN0004321"), ("Central Bank of India", "CBIN0284321")):
        pages = _detector_pages(brand, "Account Statement", f"IFSC: {ifsc}",
                                "Txn Date Particulars Debit Credit Balance",
                                *["01-04-2021 PAYMENT 100.00 5000.00"] * 30)
        r = route_pages(pages, LayoutRegistry([ALPHA]), use_detector=True)
        assert r.fallback_reason != "legacy_only:bank_of_india", brand


_NO_DETECTOR_ID = {"apgv"}   # banks with no banks/*.json detector: routing relies on bank_markers evidence


def test_detector_ids_map_to_registered_spec_banks():
    from app.services.statement_engine.v2_router import DETECTOR_TO_SPEC_BANK
    from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
    spec_banks = {s.bank_key for s in DEFAULT_REGISTRY.specs()}
    assert set(DETECTOR_TO_SPEC_BANK.values()) | _NO_DETECTOR_ID == spec_banks
    assert set(DETECTOR_TO_SPEC_BANK.values()) <= spec_banks


def _pnb_markerless_pages(with_ifsc=True, second_mention=False):
    """ALPHA layout re-keyed to a marker-less detector bank (like pnb), plus issuer text for the real detector."""
    from dataclasses import replace
    from tests.statement_engine.extraction.test_generic_engine import ALPHA, ALPHA_PERIOD, header, rt, w
    spec = replace(ALPHA, bank_key="pnb", bank_name="Punjab National Bank", bank_markers=())
    ws = list(ALPHA_PERIOD)
    ws += [w("PUNJAB", 30, 5), w("NATIONAL", 62, 5), w("BANK", 112, 5)]
    if with_ifsc:
        ws += [w("IFSC:", 30, 17), w("PUNB0000123", 62, 17)]
    if second_mention:
        ws += [w("Punjab", 30, 500), w("National", 56, 500), w("Bank", 105, 500), w("customer", 132, 500), w("copy", 172, 500)]
    ws += header(spec) + [w("01-04-2022", 30, 220), w("SHOP", 120, 220), rt("100.00", 400, 220), rt("900.00", 560, 220)]
    return spec, [Page(ws, 600.0)]


def test_detector_driven_route_records_confidence_and_runner_up():
    spec, pages = _pnb_markerless_pages()
    r = route_pages(pages, LayoutRegistry([spec]), use_detector=True)
    assert r.status == "v2" and r.layout_id == spec.layout_id
    assert any(n.startswith("detector:pnb:VERY_HIGH:") or n.startswith("detector:pnb:HIGH:") for n in r.notes), r.notes
    assert any(n.startswith("runner_up:") for n in r.notes)


def test_markerless_bank_thin_medium_is_refused():
    # header name alone = a single-kind MEDIUM win: not enough when the layout prints no bank marker
    spec, pages = _pnb_markerless_pages(with_ifsc=False)
    r = route_pages(pages, LayoutRegistry([spec]), use_detector=True)
    assert r.status == "fallback" and r.fallback_reason == "detector_weak" and not r.use_v2


def test_markerless_bank_multi_kind_medium_routes():
    # header name + a second page-1 mention: MEDIUM with two kinds and no runner-up passes the gate
    spec, pages = _pnb_markerless_pages(with_ifsc=False, second_mention=True)
    r = route_pages(pages, LayoutRegistry([spec]), use_detector=True)
    assert r.status == "v2" and r.layout_id == spec.layout_id


def test_detector_only_gate_rule():
    from app.services.statement_engine.contracts import Confidence, DetectionResult, Evidence, EvidenceKind
    from app.services.statement_engine.v2_router import detector_only_confident
    ev = lambda k, w: Evidence(k, "pnb", w, "x", 1)
    assert detector_only_confident(DetectionResult("pnb", "PNB", Confidence.HIGH, 30, evidence=[ev(EvidenceKind.HEADER_NAME, 30)]))
    assert detector_only_confident(DetectionResult("pnb", "PNB", Confidence.MEDIUM, 28, runner_up_id="iob", runner_up_score=8,
                                                   evidence=[ev(EvidenceKind.HEADER_NAME, 20), ev(EvidenceKind.PAGE1_NAME, 8)]))
    assert not detector_only_confident(DetectionResult("pnb", "PNB", Confidence.MEDIUM, 28, runner_up_id="iob", runner_up_score=20,
                                                       evidence=[ev(EvidenceKind.HEADER_NAME, 20), ev(EvidenceKind.PAGE1_NAME, 8)]))
    assert not detector_only_confident(DetectionResult("pnb", "PNB", Confidence.MEDIUM, 30, evidence=[ev(EvidenceKind.HEADER_NAME, 30)]))
    assert not detector_only_confident(DetectionResult("pnb", "PNB", Confidence.LOW, 15, evidence=[ev(EvidenceKind.PAGE1_NAME, 8)]))


def test_header_only_ok_opt_in_field_accepts_header_evidence_none():
    from dataclasses import replace
    alpha, pages = _alpha_pages()
    ho = replace(alpha, layout_id="alpha_ho", header_only_ok=True)
    r = route_pages(pages, LayoutRegistry([ho]))
    assert r.status == "v2" and "bank_evidence:layout_policy" in r.notes
    default_off = route_pages(pages, LayoutRegistry([alpha]))
    assert default_off.status == "fallback" and default_off.fallback_reason == "bank_unconfirmed"


def test_low_confidence_detection_never_produces_other_bank():
    # a weak foreign-name mention (below MEDIUM) must not claim the file belongs to that bank
    pages = _detector_pages("Statement", "Txn Date Particulars Debit Credit Balance",
                            *["01-04-2021 PAYMENT 100.00 5000.00"] * 5,
                            "queries: contact YES BANK support")
    r = route_pages(pages, LayoutRegistry([]), use_detector=True)
    assert r.fallback_reason != "other_bank:yes" and r.fallback_reason == "no_layout"
    assert any(n.startswith("detector:") for n in r.notes)
