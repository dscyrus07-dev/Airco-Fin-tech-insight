"""Synthetic layout tests for Equitas Small Finance Bank (equitas_sfb). Pages built from word
coordinates; no PDFs, no customer data."""
from app.services.statement_engine import Confidence, detect_bank
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.extractors.equitas.layout_spec import EQUITAS_LAYOUT_1 as SPEC
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, header, row, rt, w

MARKER = [w("EQUITAS", 30, 40), w("SMALL", 100, 40), w("FINANCE", 170, 40), w("BANK", 240, 40)]


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


def test_equitas_sfb_rows_parse_and_chain():
    r = route_pages(_page(_rows()), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert [str(t.balance) for t in txns] == ["900.00", "1900.00", "1500.00"]


def test_equitas_sfb_detected_by_detector():
    text = "Equitas Small Finance Bank\nAccount Statement\nIFSC: ESFB0001234\n" \
           "Date Narration Withdrawal Deposit Balance\n" \
           "05 Jan 2024 UPI REF 100.00 900.00\n" * 3
    det = detect_bank([text])
    assert det.bank_id == "equitas_sfb" and det.confidence.name in ("HIGH", "VERY_HIGH", "MEDIUM")


def test_equitas_sfb_foreign_marker_refused():
    foreign = [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages(_page(_rows(), marker=False, extra=foreign), DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC.layout_id)


def test_equitas_sfb_narration_with_other_bank_still_equitas_sfb():
    rows = [row(SPEC, 220, "NEFTTOHDFCBANKLTD", debit="100.00", balance="900.00"),
            row(SPEC, 236, "IMPSICICIPAYOUT", credit="1,000.00", balance="1,900.00"),
            row(SPEC, 252, "AXISBANKREFUND", debit="400.00", balance="1,500.00")]
    r = route_pages(_page(rows), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_equitas_sfb_unread_dated_line_caps_at_review():
    rows = _rows()
    pgs = _page(rows)
    pgs[0].words += [w("06-01-2024", 30, 400), w("DATEDLINE", 140, 400),
                     rt("50.00", 490, 400), rt("1,450.00", 570, 400)]
    r = route_pages(pgs, DEFAULT_REGISTRY)
    if r.status == "v2":
        extras = r.result.metadata.extras
        assert extras.get("verdict") != "VERIFIED" or \
            any("unread" in str(x) for x in extras.get("warnings", []))


from app.services.statement_engine.extractors.equitas.layout_spec import (
    EQUITAS_LAYOUT_2 as SPEC2, EQUITAS_LAYOUT_3 as SPEC3)


def _header2(top=200.0):
    return [
        w("Tran Date", 23, top), w("Value Date", 95, top), w("Ref", 163, top),
        w("Description", 253, top), w("Debits", 383, top), w("Credits", 460, top),
        w("Balance", 523, top),
    ]


def _row2(top, narr="UPI REF 1234", debit="0.00", credit=None, balance="1,000.00", ref="RF001"):
    ws = [w("05-Jan-24", 23, top), w("05-Jan-24", 95, top), w(ref, 163, top),
          w(narr, 253, top), rt(debit, 401, top)]
    ws += [rt(credit, 487, top)] if credit else [rt("0.00", 487, top)]
    ws += [rt(balance, 550, top)]
    return ws


def test_equitas_l2_trandate_rows_parse_and_chain():
    ws = list(MARKER) + _header2()
    ws += _row2(220, narr="B/F ...", debit="0.00", credit="866.74", balance="866.74")
    ws += _row2(236, debit="0.00", credit="314.00", balance="1,180.74")
    ws += _row2(252, debit="100.00", balance="1,080.74")
    ws += [w("Statement Summary:", 30, 300), w("******END OF STATEMENT******", 30, 320)]
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC2.layout_id
    txns = r.result.transactions
    assert len(txns) == 2


def _header3(top=200.0):
    return [
        w("Date of TXN", 46, top), w("Value date of", 110, top), w("Reference or", 180, top),
        w("Narration", 288, top), w("Debit", 392, top), w("Credit", 455, top), w("Balance", 518, top),
        w("TXN", 129, top + 12), w("cheque no", 185, top + 12),
        w("(`)", 399, top + 12), w("(`)", 463, top + 12), w("(`)", 529, top + 12),
    ]


def _row3(top, narr="UPI REF NO 1234", debit=None, credit=None, balance="500.00"):
    ws = [w("01/12/2023", 47, top), w("01/12/2023", 113, top), w(narr, 247, top)]
    if debit:
        ws += [rt(debit, 432, top)]
    if credit:
        ws += [rt(credit, 496, top)]
    ws += [rt(balance, 565, top)]
    return ws


def test_equitas_l3_wrapped_txn_header_verified():
    ws = list(MARKER) + _header3()
    ws += [w("OPENING BALANCE", 247, 216), rt("1.95", 565, 216)]
    ws += _row3(230, credit="500.00", balance="501.95")
    ws += _row3(246, debit="100.00", balance="401.95")
    ws += _row3(262, credit="20.00", balance="421.95")
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC3.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert str(txns[-1].balance) == "421.95"
