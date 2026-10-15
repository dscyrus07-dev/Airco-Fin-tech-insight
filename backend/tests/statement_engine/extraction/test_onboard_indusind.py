"""Synthetic layout tests for IndusInd Bank (indusind). Pages built from word
coordinates; no PDFs, no customer data."""
from app.services.statement_engine import Confidence, detect_bank
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.extractors.indusind.layout_spec import INDUSIND_LAYOUT_1 as SPEC
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, header, row, rt, w

MARKER = [w("INDUSIND", 30, 40), w("BANK", 100, 40)]


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


def test_indusind_rows_parse_and_chain():
    r = route_pages(_page(_rows()), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert [str(t.balance) for t in txns] == ["900.00", "1900.00", "1500.00"]


def test_indusind_detected_by_detector():
    text = "IndusInd Bank\nAccount Statement\nIFSC: INDB0001234\n" \
           "Date Narration Withdrawal Deposit Balance\n" \
           "05 Jan 2024 UPI REF 100.00 900.00\n" * 3
    det = detect_bank([text])
    assert det.bank_id == "indusind" and det.confidence.name in ("HIGH", "VERY_HIGH", "MEDIUM")


def test_indusind_foreign_marker_refused():
    foreign = [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages(_page(_rows(), marker=False, extra=foreign), DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC.layout_id)


def test_indusind_narration_with_other_bank_still_indusind():
    rows = [row(SPEC, 220, "NEFTTOHDFCBANKLTD", debit="100.00", balance="900.00"),
            row(SPEC, 236, "IMPSICICIPAYOUT", credit="1,000.00", balance="1,900.00"),
            row(SPEC, 252, "AXISBANKREFUND", debit="400.00", balance="1,500.00")]
    r = route_pages(_page(rows), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_indusind_unread_dated_line_caps_at_review():
    rows = _rows()
    pgs = _page(rows)
    pgs[0].words += [w("06-01-2024", 30, 400), w("DATEDLINE", 140, 400),
                     rt("50.00", 490, 400), rt("1,450.00", 570, 400)]
    r = route_pages(pgs, DEFAULT_REGISTRY)
    if r.status == "v2":
        extras = r.result.metadata.extras
        assert extras.get("verdict") != "VERIFIED" or \
            any("unread" in str(x) for x in extras.get("warnings", []))


# ---- newer export family: "Chq No/Ref No" ref title, dated B/F + C/F anchor rows, 0.00-empty money cells ----
from app.services.statement_engine.extractors.indusind.layout_spec import (
    INDUSIND_LAYOUT_2 as SPEC2, INDUSIND_LAYOUT_3 as SPEC3)


def _bf(spec, top, balance):
    return row(spec, top, "Brought Forward", debit="0.00", credit="0.00", balance=balance)


def _cf(spec, top, balance):
    return row(spec, top, "Carried Forward", debit="0.00", credit="0.00", balance=balance)


def _page2(rows, marker=True, extra=None):
    ws = list(MARKER if marker else [])
    if extra:
        ws += extra
    ws += header(SPEC2)
    ws += _bf(SPEC2, 220, "5,048.83")
    ws += [
        *row(SPEC2, 236, "UPI DR", debit="70.00", credit="0.00", balance="4,978.83"),
        *row(SPEC2, 252, "UPI CR", debit="0.00", credit="640.00", balance="5,618.83"),
    ]
    ws += _cf(SPEC2, 268, "5,618.83")
    for r in rows:
        ws += r
    return [Page(ws, W)]


def test_indusind_l2_anchors_verify():
    r = route_pages(_page2([]), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC2.layout_id
    assert len(r.result.transactions) == 2


def test_indusind_l2_page2_carry_rows_dropped():
    p2 = list(header(SPEC2)) + _bf(SPEC2, 220, "5,618.83")
    p2 += row(SPEC2, 236, "NEFT DR", debit="100.00", credit="0.00", balance="5,518.83")
    p2 += _cf(SPEC2, 252, "5,518.83")
    pgs = _page2([]) + [Page(p2, W)]
    r = route_pages(pgs, DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC2.layout_id
    descs = [t.description for t in r.result.transactions]
    assert not any("forward" in d.lower() for d in descs)
    assert len(r.result.transactions) == 3


def test_indusind_l3_spaced_dates_route():
    ws = list(MARKER) + header(SPEC3)
    ws += row(SPEC3, 220, "UPI DR", debit="100.00", credit="0.00", balance="900.00", date="05 Jan 2024")
    ws += row(SPEC3, 236, "UPI CR", debit="0.00", credit="1,000.00", balance="1,900.00", date="05 Jan 2024")
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC3.layout_id


def test_indusind_l2_dashed_dates_stay_l2():
    r = route_pages(_page2([]), DEFAULT_REGISTRY)
    assert r.layout_id == SPEC2.layout_id   # same titles as L3: date shape decides


def test_indusind_l2_markerless_not_routed():
    r = route_pages(_page2([], marker=False), DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id in (SPEC2.layout_id, SPEC3.layout_id))


def test_indusind_l2_foreign_marker_refused():
    foreign = [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages(_page2([], marker=False, extra=foreign), DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id in (SPEC2.layout_id, SPEC3.layout_id))


# ---- newest export family: wrapped 2-line header, type line above each dated row,
#      "-" empty money cells, some files print newest-first (row_order="auto") ----
from app.services.statement_engine.extractors.indusind.layout_spec import (
    INDUSIND_LAYOUT_4 as SPEC4)

_TEXT_X4 = {"date": 30.0, "type": 120.0, "narration": 200.0}
_EDGE4 = {"debit": 480.0, "credit": 560.0, "balance": 660.0}


def _hdr4(top=200.0):
    ws = [w("Date", _TEXT_X4["date"], top), w("Type", _TEXT_X4["type"], top),
          w("Description", _TEXT_X4["narration"], top),
          rt("Debit", _EDGE4["debit"], top), rt("Credit", _EDGE4["credit"], top),
          rt("Balance", _EDGE4["balance"], top + 10)]
    return ws


def _row4(top, date, prefix, tail, debit=None, credit=None, balance="1,000.00"):
    ws = []
    tx = _TEXT_X4["type"]
    for t in prefix.split():
        ws.append(w(t, tx, top))
        tx += 5.5 * len(t) + 3
    tx = _TEXT_X4["narration"]
    for t in tail.split():
        ws.append(w(t, tx, top))
        tx += 5.5 * len(t) + 3
    top2 = top + 12
    ws.append(w(date, _TEXT_X4["date"], top2))
    tx = _TEXT_X4["narration"]
    for t in tail.split():
        ws.append(w(t, tx, top2))
        tx += 5.5 * len(t) + 3
    ws.append(w("-", _EDGE4["debit"] - 5.5, top2) if debit is None
              else rt(debit, _EDGE4["debit"], top2))
    ws.append(w("-", _EDGE4["credit"] - 5.5, top2) if credit is None
              else rt(credit, _EDGE4["credit"], top2))
    ws.append(rt(balance, _EDGE4["balance"], top2))
    return ws


def _page4(rows, marker=True, extra=None):
    ws = list(MARKER if marker else [])
    if extra:
        ws += extra
    ws += _hdr4()
    top = 240.0
    for r in rows:
        ws += r
        top += 24
    return [Page(ws, W)]


def test_indusind_l4_rows_parse_chain_review():
    rows = [_row4(240, "05 Jan 2024", "Transfer Credit", "UPI/REF1", credit="1,000.00", balance="2,000.00"),
            _row4(264, "06 Jan 2024", "Transfer Debit", "UPI/REF2", debit="400.00", balance="1,600.00"),
            _row4(288, "07 Jan 2024", "Transfer Debit", "ATM/REF3", debit="100.00", balance="1,500.00")]
    r = route_pages(_page4(rows), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC4.layout_id
    assert len(r.result.transactions) == 3
    ex = r.result.metadata.extras
    assert ex.get("verdict") == "REVIEW"  # no printed anchors: self-derived chain caps at REVIEW


def test_indusind_l4_comma_dates():
    rows = [_row4(240, "Jan 5, 2024", "Transfer Credit", "UPI/REF1", credit="1,000.00", balance="2,000.00"),
            _row4(264, "Jan 6, 2024", "Transfer Debit", "UPI/REF2", debit="400.00", balance="1,600.00")]
    r = route_pages(_page4(rows), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC4.layout_id
    assert [str(t.date) for t in r.result.transactions] == ["2024-01-05", "2024-01-06"]


def test_indusind_l4_newest_first_reversed():
    rows = [_row4(240, "07 Jan 2024", "Transfer Debit", "ATM/REF3", debit="100.00", balance="1,500.00"),
            _row4(264, "06 Jan 2024", "Transfer Debit", "UPI/REF2", debit="400.00", balance="1,600.00"),
            _row4(288, "05 Jan 2024", "Transfer Credit", "UPI/REF1", credit="1,000.00", balance="2,000.00")]
    r = route_pages(_page4(rows), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC4.layout_id
    txns = r.result.transactions
    assert [str(t.date) for t in txns] == ["2024-01-05", "2024-01-06", "2024-01-07"]
    assert [str(t.balance) for t in txns] == ["2000.00", "1600.00", "1500.00"]
