"""Synthetic layout tests for Standard Chartered Bank (scb). Pages built from word
coordinates; no PDFs, no customer data."""
from app.services.statement_engine import Confidence, detect_bank
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.extractors.scb.layout_spec import SCB_LAYOUT_1 as SPEC
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, header, row, rt, w

MARKER = [w("STANDARD", 30, 40), w("CHARTERED", 100, 40)]


def _rows():
    return [
        row(SPEC, 220, "UPIREF1234", debit="100.00", balance="900.00"),
        row(SPEC, 236, "NEFTSALARY5678", credit="1,000.00", balance="1,900.00"),
        row(SPEC, 252, "ATMCASH", debit="400.00", balance="1,500.00"),
    ]


def _page(rows, marker=True, extra=None):
    ws = list(MARKER if marker else [])
    if extra:
        ws += extra
    ws += header(SPEC)
    for r in rows:
        ws += r
    return [Page(ws, W)]


def test_scb_rows_parse_and_chain():
    r = route_pages(_page(_rows()), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert [str(t.balance) for t in txns] == ["900.00", "1900.00", "1500.00"]


def test_scb_detected_by_detector():
    text = "Standard Chartered Bank\nAccount Statement\nIFSC: SCBL0036001\n" \
           "Date Narration Withdrawal Deposit Balance\n" \
           "05 Jan 2024 UPI REF 100.00 900.00\n" * 3
    det = detect_bank([text])
    assert det.bank_id == "standard_chartered" and det.confidence.name in ("HIGH", "VERY_HIGH", "MEDIUM")


def test_scb_foreign_marker_refused():
    foreign = [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages(_page(_rows(), marker=False, extra=foreign), DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC.layout_id)


def test_scb_narration_with_other_bank_still_scb():
    rows = [row(SPEC, 220, "NEFTTOHDFCBANKLTD", debit="100.00", balance="900.00"),
            row(SPEC, 236, "IMPSICICIPAYOUT", credit="1,000.00", balance="1,900.00"),
            row(SPEC, 252, "AXISBANKREFUND", debit="400.00", balance="1,500.00")]
    r = route_pages(_page(rows), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_scb_unread_dated_line_caps_at_review():
    rows = _rows()
    pgs = _page(rows)
    pgs[0].words += [w("06-01-2024", 30, 400), w("DATEDLINE", 140, 400),
                     rt("50.00", 490, 400), rt("1,450.00", 570, 400)]
    r = route_pages(pgs, DEFAULT_REGISTRY)
    if r.status == "v2":
        extras = r.result.metadata.extras
        assert extras.get("verdict") != "VERIFIED" or \
            any("unread" in str(x) for x in extras.get("warnings", []))


def test_scb_ifsc_marker_routes_when_wordmark_absent():
    # SCB prints no "Standard Chartered" wordmark on these exports; the account block's "IFSC: SCBL..." is the
    # own-bank evidence. A foreign bank name in the header region (e.g. an address "NEAR ICICI BANK ATM") must not
    # refuse the route once own evidence exists.
    ws = [w("IFSC:", 30, 40), w("SCBL0036001", 90, 40), w("NEAR", 200, 40), w("ICICI", 260, 40), w("BANK", 310, 40)]
    ws += header(SPEC)
    for r in _rows():
        ws += r
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_scb_other_bank_ifsc_does_not_count_as_own():
    # a labelled foreign IFSC is not own evidence and a matching foreign marker elsewhere refuses the route
    ws = [w("IFSC:", 30, 40), w("HDFC0001234", 90, 40), w("HDFC", 200, 40), w("BANK", 255, 40)]
    ws += header(SPEC)
    for r in _rows():
        ws += r
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC.layout_id)
