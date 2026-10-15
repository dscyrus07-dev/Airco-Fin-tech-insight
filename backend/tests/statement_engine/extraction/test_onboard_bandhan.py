"""Synthetic layout tests for Bandhan Bank (bandhan). Pages built from word
coordinates; no PDFs, no customer data."""
from app.services.statement_engine import Confidence, detect_bank
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.extractors.bandhan.layout_spec import BANDHAN_LAYOUT_1 as SPEC
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, geometry, header, row, rt, w

MARKER = [w("BANDHAN", 30, 40), w("BANK", 100, 40)]


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


def test_bandhan_rows_parse_and_chain():
    r = route_pages(_page(_rows()), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert [str(t.balance) for t in txns] == ["900.00", "1900.00", "1500.00"]


def test_bandhan_detected_by_detector():
    text = "Bandhan Bank\nAccount Statement\nIFSC: BDBL0001234\n" \
           "Date Narration Withdrawal Deposit Balance\n" \
           "05 Jan 2024 UPI REF 100.00 900.00\n" * 3
    det = detect_bank([text])
    assert det.bank_id == "bandhan" and det.confidence.name in ("HIGH", "VERY_HIGH", "MEDIUM")


def test_bandhan_foreign_marker_refused():
    foreign = [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages(_page(_rows(), marker=False, extra=foreign), DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC.layout_id)


def test_bandhan_narration_with_other_bank_still_bandhan():
    rows = [row(SPEC, 220, "NEFTTOHDFCBANKLTD", debit="100.00", balance="900.00"),
            row(SPEC, 236, "IMPSICICIPAYOUT", credit="1,000.00", balance="1,900.00"),
            row(SPEC, 252, "AXISBANKREFUND", debit="400.00", balance="1,500.00")]
    r = route_pages(_page(rows), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_bandhan_unread_dated_line_caps_at_review():
    rows = _rows()
    pgs = _page(rows)
    pgs[0].words += [w("06-01-2024", 30, 400), w("DATEDLINE", 140, 400),
                     rt("50.00", 490, 400), rt("1,450.00", 570, 400)]
    r = route_pages(pgs, DEFAULT_REGISTRY)
    if r.status == "v2":
        extras = r.result.metadata.extras
        assert extras.get("verdict") != "VERIFIED" or \
            any("unread" in str(x) for x in extras.get("warnings", []))


from app.services.statement_engine.extractors.bandhan.layout_spec import (
    BANDHAN_LAYOUT_3 as SPEC3, BANDHAN_LAYOUT_4 as SPEC4)

IFSC = [w("IFSC", 30, 90), w(":", 60, 90), w("BDBL0002093", 80, 90)]


def _row_c(spec, top, date_words, narration, amount, side, balance=None):
    """TransactionDate|ValueDate|Description|Amount|Dr/Cr[|Balance] row:
    multi-word date cells, INR-prefixed amount, side marker in its own column."""
    text_x, money_edge, money_left = geometry(spec)
    ws = []
    for col in ("date", "value_date"):
        tx = text_x[col]
        for t in date_words.split():
            ws.append(w(t, tx, top))
            tx += 4.0 * len(t) + 1.5        # tight: the printed date cell hugs the column left
    tx = text_x["narration"]
    for t in narration.split():
        ws.append(w(t, tx, top))
        tx += 5.5 * len(t) + 3
    ws.append(w("INR", money_left["amount"] + 2, top))
    ws.append(rt(amount, money_edge["amount"], top))
    ws.append(w(side, text_x["drcr"], top))
    if balance is not None and "balance" in money_edge:
        ws.append(w("INR", money_left["balance"] + 2, top))
        ws.append(rt(balance, money_edge["balance"], top))
    return ws


def _page_c(spec, rows, summary=None, top0=220.0):
    ws = list(IFSC) + header(spec)
    top = top0
    for r in rows:
        ws += r
        top += 16
    if summary:
        ws += [w("Statement", 30, top + 20), w("Summary", 110, top + 20)]
        top += 36
        tx = 30.0
        for t in ("Opening Balance Total Credits Total Debits Closing Balance").split():
            ws.append(w(t, tx, top))
            tx += 5.5 * len(t) + 3
        top += 16
        tx = 30.0
        for t in summary.split():
            ws.append(w(t, tx, top))
            tx += 5.5 * len(t) + 3
    return [Page(ws, W)]


def test_bandhan_l3_balance_less_rows_parse_as_review():
    rows = [_row_c(SPEC3, 220, "01 Jan 2024", "UPI/DR/D123/REF", "500.00", "Dr"),
            _row_c(SPEC3, 236, "31 Dec 2023", "UPI/CR/C999/PAY", "2,000.00", "Cr"),
            _row_c(SPEC3, 252, "30 Dec 2023", "ATW using 5089XX", "300.00", "Dr")]
    r = route_pages(_page_c(SPEC3, rows), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC3.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert str(txns[0].debit) == "500.00" and str(txns[1].credit) == "2000.00"


def test_bandhan_l3_ifsc_is_own_evidence():
    rows = [_row_c(SPEC3, 220, "01 Jan 2024", "UPI REF", "500.00", "Dr")]
    r = route_pages(_page_c(SPEC3, rows), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC3.layout_id


def test_bandhan_l3_foreign_only_marker_refused():
    rows = [_row_c(SPEC3, 220, "01 Jan 2024", "UPI REF", "500.00", "Dr")]
    pgs = _page_c(SPEC3, rows)
    pgs[0].words = [x for x in pgs[0].words if x not in IFSC]
    pgs[0].words += [w("HDFC", 30, 90), w("BANK", 60, 90), w("HDFC0001234", 110, 90)]
    r = route_pages(pgs, DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC3.layout_id)


def test_bandhan_l4_summary_anchors_verify():
    rows = [_row_c(SPEC4, 220, "July 10, 2024", "UPI/DR/D4192/REF", "400.00", "Dr", "1,500.00"),
            _row_c(SPEC4, 236, "July 09, 2024", "UPI/CR/C4558/PAY", "1,000.00", "Cr", "1,900.00"),
            _row_c(SPEC4, 252, "July 08, 2024", "ATW using 5089XX", "400.00", "Dr", "900.00")]
    pg = _page_c(SPEC4, rows, summary="INR 1,300.00 INR 1,000.00 INR 800.00 INR 1,500.00")
    r = route_pages(pg, DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC4.layout_id
    assert r.result.metadata.extras.get("verdict") == "VERIFIED"
