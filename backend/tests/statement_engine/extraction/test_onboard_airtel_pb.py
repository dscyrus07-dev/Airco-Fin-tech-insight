"""Synthetic layout tests for Airtel Payments Bank (airtel_pb). Pages built from word
coordinates; no PDFs, no customer data."""
from app.services.statement_engine import Confidence, detect_bank
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.extractors.airtel_pb.layout_spec import AIRTEL_LAYOUT_1 as SPEC
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, header, row, rt, w

MARKER = [w("AIRTEL", 30, 40), w("PAYMENTS", 100, 40), w("BANK", 170, 40), w("AIRP0001234", 240, 40)]


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


def test_airtel_pb_rows_parse_and_chain():
    r = route_pages(_page(_rows()), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert [str(t.balance) for t in txns] == ["900.00", "1900.00", "1500.00"]


def test_airtel_pb_detected_by_detector():
    text = "Airtel Payments Bank\nAccount Statement\nIFSC: AIRP0001234\n" \
           "Date Narration Withdrawal Deposit Balance\n" \
           "05 Jan 2024 UPI REF 100.00 900.00\n" * 3
    det = detect_bank([text])
    assert det.bank_id == "airtel_pb" and det.confidence.name in ("HIGH", "VERY_HIGH", "MEDIUM")


def test_airtel_pb_foreign_marker_refused():
    foreign = [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages(_page(_rows(), marker=False, extra=foreign), DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC.layout_id)


def test_airtel_pb_narration_with_other_bank_still_airtel_pb():
    rows = [row(SPEC, 220, "NEFTTOHDFCBANKLTD", debit="100.00", balance="900.00"),
            row(SPEC, 236, "IMPSICICIPAYOUT", credit="1,000.00", balance="1,900.00"),
            row(SPEC, 252, "AXISBANKREFUND", debit="400.00", balance="1,500.00")]
    r = route_pages(_page(rows), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_airtel_pb_unread_dated_line_caps_at_review():
    rows = _rows()
    pgs = _page(rows)
    pgs[0].words += [w("06-01-2024", 30, 400), w("DATEDLINE", 140, 400),
                     rt("50.00", 490, 400), rt("1,450.00", 570, 400)]
    r = route_pages(pgs, DEFAULT_REGISTRY)
    if r.status == "v2":
        extras = r.result.metadata.extras
        assert extras.get("verdict") != "VERIFIED" or \
            any("unread" in str(x) for x in extras.get("warnings", []))


def test_airtel_pb_opening_row_totals_and_closing_day_furniture():
    rows = _rows()
    ws = list(MARKER) + header(SPEC)
    ws += [w("05-01-2024", 30, 212), w("Opening Balance", 140, 212), rt("1,000.00", 500, 212)]
    for r in rows:
        ws += r
    ws += [w("08-01-2024", 30, 272), w("Closing Day Balance", 140, 272), rt("1,500.00", 500, 272)]
    ws += [w("Total Credits", 240, 288), rt("1,000.00", 330, 288),
           w("Total Debits", 460, 288), rt("500.00", 540, 288)]
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY)
    assert r.status == "v2"
    txns = r.result.transactions
    assert len(txns) == 3 and [str(t.balance) for t in txns] == ["900.00", "1900.00", "1500.00"]
    assert r.result.verification_status in ("VERIFIED", "REVIEW")
