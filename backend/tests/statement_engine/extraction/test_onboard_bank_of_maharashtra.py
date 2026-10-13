"""Synthetic layout tests for Bank of Maharashtra (bank_of_maharashtra). Pages built from word
coordinates; no PDFs, no customer data."""
from app.services.statement_engine import Confidence, detect_bank
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.extractors.bom.layout_spec import BOM_LAYOUT_1 as SPEC
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, header, row, rt, w

MARKER = [w("BANK", 30, 40), w("OF", 100, 40), w("MAHARASHTRA", 170, 40)]


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


def test_bank_of_maharashtra_rows_parse_and_chain():
    r = route_pages(_page(_rows()), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert [str(t.balance) for t in txns] == ["900.00", "1900.00", "1500.00"]


def test_bank_of_maharashtra_detected_by_detector():
    text = "Bank of Maharashtra\nAccount Statement\nIFSC: MAHB0001234\n" \
           "Date Narration Withdrawal Deposit Balance\n" \
           "05 Jan 2024 UPI REF 100.00 900.00\n" * 3
    det = detect_bank([text])
    assert det.bank_id == "bank_of_maharashtra" and det.confidence.name in ("HIGH", "VERY_HIGH", "MEDIUM")


def test_bank_of_maharashtra_foreign_marker_refused():
    foreign = [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages(_page(_rows(), marker=False, extra=foreign), DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC.layout_id)


def test_bank_of_maharashtra_narration_with_other_bank_still_bank_of_maharashtra():
    rows = [row(SPEC, 220, "NEFTTOHDFCBANKLTD", debit="100.00", balance="900.00"),
            row(SPEC, 236, "IMPSICICIPAYOUT", credit="1,000.00", balance="1,900.00"),
            row(SPEC, 252, "AXISBANKREFUND", debit="400.00", balance="1,500.00")]
    r = route_pages(_page(rows), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_bank_of_maharashtra_unread_dated_line_caps_at_review():
    rows = _rows()
    pgs = _page(rows)
    pgs[0].words += [w("06-01-2024", 30, 400), w("DATEDLINE", 140, 400),
                     rt("50.00", 490, 400), rt("1,450.00", 570, 400)]
    r = route_pages(pgs, DEFAULT_REGISTRY)
    if r.status == "v2":
        extras = r.result.metadata.extras
        assert extras.get("verdict") != "VERIFIED" or \
            any("unread" in str(x) for x in extras.get("warnings", []))


from app.services.statement_engine.extractors.bom.layout_spec import BOM_LAYOUT_3 as SPEC3
from app.services.statement_engine.extractors.bom.layout_spec import BOM_LAYOUT_4 as SPEC4


def _header3(top=200.0):
    return [w("Sr No", 65, top), w("Date", 165, top), w("Particulars", 283, top),
            rt("Debit", 560, top), rt("Credit", 640, top), rt("Balance", 760, top), w("Channel", 849, top)]


def _row3(top, narr, debit=None, credit=None, balance="1,000.00"):
    ws = [w("1", 65, top), w("05/01/2024", 165, top), w(narr, 283, top)]
    ws += [rt(debit, 560, top)] if debit else [w("-", 540, top)]
    ws += [rt(credit, 640, top)] if credit else [w("-", 620, top)]
    ws += [rt(balance, 760, top)]
    return ws


def test_bom_layout3_no_ref_column_parses_and_chains():
    ws = list(MARKER) + _header3()
    ws += _row3(220, "UPI REF 1234", debit="100.00", balance="900.00")
    ws += _row3(236, "NEFT SALARY", credit="1,000.00", balance="1,900.00")
    ws += _row3(252, "ATM CASH", debit="400.00", balance="1,500.00")
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC3.layout_id
    txns = r.result.transactions
    assert len(txns) == 3 and [str(t.balance) for t in txns] == ["900.00", "1900.00", "1500.00"]


def _header4(top=200.0):
    return [w("Date", 15, top), w("Particulars", 40, top), w("Cheque No", 384, top),
            rt("Withdrawals", 500, top), rt("Deposits", 555, top), rt("Balance", 610, top)]


def _row4(top, narr, debit=None, credit=None, balance="1,000.00 Cr"):
    ws = [w("01/10/22", 9, top), w(narr, 40, top)]
    ws += [rt(debit, 500, top)] if debit else [rt("0.00", 500, top)]
    ws += [rt(credit, 555, top)] if credit else [rt("0.00", 555, top)]
    ws += [rt(balance, 610, top)]
    return ws


def test_bom_layout4_withdrawals_variant_zero_empty_and_cr_suffix():
    ws = list(MARKER) + _header4()
    ws += [w("01/10/22", 9, 216), w("B/F ...", 40, 216), rt("66,557.82 Cr", 610, 216)]  # opening row
    ws += _row4(236, "UPI 227450145351PAYMENT", credit="7,500.00", balance="74,057.82 Cr")
    ws += _row4(252, "UPI 227446830977PAYMENT", debit="30.00", balance="74,027.82 Cr")
    ws += [w("Total", 208, 280), rt("30.00", 500, 280), rt("7,500.00", 555, 280), rt("74,027.82 Cr", 610, 280)]
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC4.layout_id
    txns = r.result.transactions
    assert len(txns) == 2 and [str(t.balance) for t in txns] == ["74057.82", "74027.82"]
    assert str(txns[0].credit) == "7500.00" and str(txns[1].debit) == "30.00"
