"""Synthetic layout tests for CSB Bank (csb). Pages built from word
coordinates; no PDFs, no customer data."""
from app.services.statement_engine import Confidence, detect_bank
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.extractors.csb.layout_spec import CSB_LAYOUT_1 as SPEC
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, header, row, rt, w

MARKER = [w("CSB", 30, 40), w("BANK", 100, 40), w("CSBK0001234", 170, 40)]


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


def test_csb_rows_parse_and_chain():
    r = route_pages(_page(_rows()), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert [str(t.balance) for t in txns] == ["900.00", "1900.00", "1500.00"]


def test_csb_detected_by_detector():
    text = "CSB Bank\nAccount Statement\nIFSC: CSBK0001234\n" \
           "Date Narration Withdrawal Deposit Balance\n" \
           "05 Jan 2024 UPI REF 100.00 900.00\n" * 3
    det = detect_bank([text])
    assert det.bank_id == "csb" and det.confidence.name in ("HIGH", "VERY_HIGH", "MEDIUM")


def test_csb_foreign_marker_refused():
    foreign = [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages(_page(_rows(), marker=False, extra=foreign), DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC.layout_id)


def test_csb_narration_with_other_bank_still_csb():
    rows = [row(SPEC, 220, "NEFTTOHDFCBANKLTD", debit="100.00", balance="900.00"),
            row(SPEC, 236, "IMPSICICIPAYOUT", credit="1,000.00", balance="1,900.00"),
            row(SPEC, 252, "AXISBANKREFUND", debit="400.00", balance="1,500.00")]
    r = route_pages(_page(rows), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_csb_unread_dated_line_caps_at_review():
    rows = _rows()
    pgs = _page(rows)
    pgs[0].words += [w("06-01-2024", 30, 400), w("DATEDLINE", 140, 400),
                     rt("50.00", 490, 400), rt("1,450.00", 570, 400)]
    r = route_pages(pgs, DEFAULT_REGISTRY)
    if r.status == "v2":
        extras = r.result.metadata.extras
        assert extras.get("verdict") != "VERIFIED" or \
            any("unread" in str(x) for x in extras.get("warnings", []))


from app.services.statement_engine.extractors.csb.layout_spec import (
    CSB_LAYOUT_2 as SPEC2, CSB_LAYOUT_3 as SPEC3)
from tests.statement_engine.extraction.onboarded_kit import geometry, _place_amount

MARKER2 = [w("CSB", 30, 40), w("EPASSBOOK", 60, 40)]


def _page2(words, marker=True):
    ws = list(MARKER2 if marker else []) + words
    return [Page(ws, W)]


def _l2_header(top=200.0):
    # Date@10 Particulars@79 Withdrawal@378 Deposit@447 Balance@516
    return [w("Date", 10, top), w("Particulars", 79, top), w("Withdrawal", 378, top),
            w("Deposit", 447, top), w("Balance", 516, top)]


def test_csb_l2_parses_epassbook_rows():
    ws = _l2_header()
    ws += [w("15-Oct-2022", 10, 220), w("OPENING", 79, 220), w("BALANCE", 122, 220),
           w("3588.70", 447, 220), w("3588.70 CR", 516, 220)]
    ws += [w("15-Oct-2022", 10, 240), w("UPI", 79, 240), w("TRANSFER", 96, 240),
           w("300.00", 378, 240), w("3379.20 CR", 516, 240)]
    ws += [w("16-Oct-2022", 10, 260), w("NEFT", 79, 260),
           w("100.00", 447, 260), w("3479.20 CR", 516, 260)]
    ws += [w("Closing", 79, 290), w("Balance", 122, 290), w("3479.20 CR", 516, 290)]
    r = route_pages(_page2(ws), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC2.layout_id
    txns = r.result.transactions
    assert len(txns) == 2
    assert str(txns[0].debit) == "300.00" and str(txns[1].credit) == "100.00"


def test_csb_l2_split_date_and_continuation_amounts():
    # ePassbook variant: "08-Nov-" then the year on a lower line; the money
    # cells print on an undated continuation line between them.
    ws = _l2_header()
    ws += [w("08-Nov-", 10, 220), w("UPI", 79, 220), w("TRANSFER", 96, 220)]
    ws += [w("50.00", 378, 236), w("55.80 CR", 516, 236)]
    ws += [w("2023", 10, 252), w("RefNo:123", 79, 252)]
    ws += [w("09-Nov-", 10, 268), w("PAID", 79, 268)]
    ws += [w("2023", 10, 284), w("100.00", 447, 284), w("155.80 CR", 516, 284)]
    r = route_pages(_page2(ws), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC2.layout_id
    txns = r.result.transactions
    assert len(txns) == 2
    assert str(txns[0].debit) == "50.00" and str(txns[0].balance) == "55.80"
    assert str(txns[1].credit) == "100.00"


def test_csb_l2_foreign_marker_refused():
    ws = _l2_header()
    ws += [w("15-Oct-2022", 10, 220), w("X", 79, 220), w("1.00", 447, 220),
           w("1.00 CR", 516, 220)]
    ws += [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC2.layout_id)


def _l3_header(top=200.0):
    # TRANS/VALUE/DETAILS/REF NO./DEBITS/CREDITS/BALANCE + DATE/DATE//CHEQUE NO.
    return [w("TRANS", 36, top), w("VALUE", 80, top), w("DETAILS", 122, top),
            w("REF", 246, top), w("NO.", 266, top), w("DEBITS", 316, top),
            w("CREDITS", 385, top), w("BALANCE", 455, top),
            w("DATE", 36, top + 14), w("DATE", 80, top + 14),
            w("/CHEQUE", 246, top + 14), w("NO.", 296, top + 14)]


def test_csb_l3_parses_wrapped_header_rows():
    ws = list(MARKER) + _l3_header()
    ws += [w("Opening", 37, 236), w("Balance", 37 + 40, 236)]
    ws += [w("18,402.19", 37, 250), w("333,192.99", 172, 250),
           w("3,14,866.42", 298, 250), w("75.62", 433, 250)]
    ws += [w("01-JUL-", 36, 270), w("01-JUL-", 80, 270), w("B/F", 122, 270),
           w("...", 140, 270), w("0.00", 359, 270), w("18,402.19", 408, 270),
           w("18,402.19", 512, 270), w("2025", 36, 284), w("2025", 80, 284)]
    ws += [w("02-JUL-", 36, 300), w("02-JUL-", 80, 300), w("UPI/DR/5182", 122, 300),
           w("172666", 278, 300), w("18,400.00", 339, 300), w("0.00", 428, 300),
           w("2.19", 532, 300), w("2025", 36, 314), w("2025", 80, 314)]
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC3.layout_id
    txns = r.result.transactions
    assert len(txns) == 1
    assert str(txns[0].debit) == "18400.00" and str(txns[0].balance) == "2.19"
