"""Synthetic layout tests for Dhanlaxmi Bank (dhanlaxmi). Pages built from word
coordinates; no PDFs, no customer data."""
from app.services.statement_engine import Confidence, detect_bank
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.extractors.dhanlaxmi.layout_spec import DHANLAXMI_LAYOUT_1 as SPEC
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, geometry, header, row, rt, w

MARKER = [w("DHANLAXMI", 30, 40), w("BANK", 100, 40), w("DLXB0001234", 170, 40)]


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


def test_dhanlaxmi_rows_parse_and_chain():
    r = route_pages(_page(_rows()), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert [str(t.balance) for t in txns] == ["900.00", "1900.00", "1500.00"]


def test_dhanlaxmi_detected_by_detector():
    text = "Dhanlaxmi Bank\nAccount Statement\nIFSC: DLXB0001234\n" \
           "Date Narration Withdrawal Deposit Balance\n" \
           "05 Jan 2024 UPI REF 100.00 900.00\n" * 3
    det = detect_bank([text])
    assert det.bank_id == "dhanlaxmi" and det.confidence.name in ("HIGH", "VERY_HIGH", "MEDIUM")


def test_dhanlaxmi_foreign_marker_refused():
    foreign = [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages(_page(_rows(), marker=False, extra=foreign), DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC.layout_id)


def test_dhanlaxmi_narration_with_other_bank_still_dhanlaxmi():
    rows = [row(SPEC, 220, "NEFTTOHDFCBANKLTD", debit="100.00", balance="900.00"),
            row(SPEC, 236, "IMPSICICIPAYOUT", credit="1,000.00", balance="1,900.00"),
            row(SPEC, 252, "AXISBANKREFUND", debit="400.00", balance="1,500.00")]
    r = route_pages(_page(rows), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_dhanlaxmi_unread_dated_line_caps_at_review():
    rows = _rows()
    pgs = _page(rows)
    pgs[0].words += [w("06-01-2024", 30, 400), w("DATEDLINE", 140, 400),
                     rt("50.00", 490, 400), rt("1,450.00", 570, 400)]
    r = route_pages(pgs, DEFAULT_REGISTRY)
    if r.status == "v2":
        extras = r.result.metadata.extras
        assert extras.get("verdict") != "VERIFIED" or \
            any("unread" in str(x) for x in extras.get("warnings", []))


from app.services.statement_engine.extractors.dhanlaxmi.layout_spec import DHANLAXMI_LAYOUT_3 as SPEC3


def _page3(rows, totals=None, marker=True):
    ws = list(MARKER if marker else [])
    ws += header(SPEC3)
    for r in rows:
        ws += r
    if totals:
        edge = geometry(SPEC3)[1]
        top = max(x.top for x in ws) + 20
        ws.append(w("Total", 30, top))
        ws.append(rt(totals[0], edge["debit"], top))
        ws.append(rt(totals[1], edge["credit"], top))
    return [Page(ws, W)]


def _rows3():
    # B/F opening row prints its balance in the credit column and is counted in the Total line
    return [
        row(SPEC3, 220, "B/F ...", credit="22,634.01", balance="22,634.01"),
        row(SPEC3, 236, "UPI/CR/C999/PAY", credit="1,000.00", balance="23,634.01"),
        row(SPEC3, 252, "ATW using 5089XX", debit="400.00", balance="23,234.01"),
    ]


def test_dhanlaxmi_l3_rows_and_bf_counted_totals():
    r = route_pages(_page3(_rows3(), totals=("400.00", "23,634.01")), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC3.layout_id
    txns = r.result.transactions
    assert len(txns) == 3


def test_dhanlaxmi_l3_foreign_marker_refused():
    pgs = _page3(_rows3(), marker=False)
    pgs[0].words += [w("ICICI", 30, 40), w("BANK", 60, 40), w("ICIC0001234", 110, 40)]
    r = route_pages(pgs, DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC3.layout_id)
