"""Synthetic layout tests for UCO Bank (uco). Pages built from word
coordinates; no PDFs, no customer data."""
from app.services.statement_engine import Confidence, detect_bank
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.extractors.uco.layout_spec import UCO_LAYOUT_1 as SPEC
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, header, row, rt, w

MARKER = [w("UCO", 30, 40), w("BANK", 100, 40), w("UCBA0001234", 170, 40)]


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


def test_uco_rows_parse_and_chain():
    r = route_pages(_page(_rows()), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert [str(t.balance) for t in txns] == ["900.00", "1900.00", "1500.00"]


def test_uco_detected_by_detector():
    text = "UCO Bank\nAccount Statement\nIFSC: UCBA0001234\n" \
           "Date Narration Withdrawal Deposit Balance\n" \
           "05 Jan 2024 UPI REF 100.00 900.00\n" * 3
    det = detect_bank([text])
    assert det.bank_id == "uco" and det.confidence.name in ("HIGH", "VERY_HIGH", "MEDIUM")


def test_uco_foreign_marker_refused():
    foreign = [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages(_page(_rows(), marker=False, extra=foreign), DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC.layout_id)


def test_uco_narration_with_other_bank_still_uco():
    rows = [row(SPEC, 220, "NEFTTOHDFCBANKLTD", debit="100.00", balance="900.00"),
            row(SPEC, 236, "IMPSICICIPAYOUT", credit="1,000.00", balance="1,900.00"),
            row(SPEC, 252, "AXISBANKREFUND", debit="400.00", balance="1,500.00")]
    r = route_pages(_page(rows), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_uco_unread_dated_line_caps_at_review():
    rows = _rows()
    pgs = _page(rows)
    pgs[0].words += [w("06-01-2024", 30, 400), w("DATEDLINE", 140, 400),
                     rt("50.00", 490, 400), rt("1,450.00", 570, 400)]
    r = route_pages(pgs, DEFAULT_REGISTRY)
    if r.status == "v2":
        extras = r.result.metadata.extras
        assert extras.get("verdict") != "VERIFIED" or \
            any("unread" in str(x) for x in extras.get("warnings", []))


def test_uco_newest_first_rows_reverse_on_chain_evidence():
    # newest-first print order: balances chain only when read bottom-to-top
    ws = list(MARKER) + header(SPEC)
    ws += row(SPEC, 220, "TXN C", debit="400.00", balance="1,500.00")   # newest
    ws += row(SPEC, 236, "TXN B", credit="1,000.00", balance="1,900.00")
    ws += row(SPEC, 252, "TXN A", debit="100.00", balance="900.00")     # oldest
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY)
    assert r.status == "v2"
    txns = r.result.transactions
    assert [t.date for t in txns] == sorted(t.date for t in txns)
    assert [str(t.balance) for t in txns] == ["900.00", "1900.00", "1500.00"]


def test_uco_layout4_monthname_dates_and_integer_amounts():
    from app.services.statement_engine.extractors.uco.layout_spec import UCO_LAYOUT_4 as S4
    ws = list(MARKER)
    ws += [w("Date", 63, 200), w("Particulars", 192, 200), rt("Withdrawals", 402, 200),
           rt("Deposits", 481, 200), rt("Balance", 559, 200)]
    ws += [w("01-Jan-2023", 54, 220), w("UPI PAY", 115, 220), rt("100", 481, 220), rt("7615.18", 560, 220)]
    ws += [w("02-Jan-2023", 54, 236), w("ATM WDL", 115, 236), rt("5000", 402, 236), rt("2615.18", 560, 236)]
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == S4.layout_id
    txns = r.result.transactions
    assert len(txns) == 2 and str(txns[0].credit) == "100" and str(txns[1].debit) == "5000"
    assert str(txns[1].balance) == "2615.18"


def test_uco_layout3_cr_suffixed_balance_left_aligned():
    from app.services.statement_engine.extractors.uco.layout_spec import UCO_LAYOUT_3 as S3
    ws = list(MARKER)
    ws += [w("DATE", 135, 200), w("PARTICULARS", 192, 200), w("CHQ.NO.", 397, 200),
           rt("WITHDRAW", 546, 200), rt("DEPOSITS", 611, 200), rt("BALANCE", 687, 200)]
    ws += [w("ALS", 474, 210)]
    ws += [w("03-04-2023", 128, 224), w("MPAY/UPI/TRTR/REF", 192, 224), rt("867.00", 547, 224), rt("5292.64 CR", 727, 224)]
    ws += [w("05-04-2023", 128, 240), w("INT PD", 192, 240), rt("33.00", 624, 240), rt("5325.64 CR", 727, 240)]
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == S3.layout_id
    txns = r.result.transactions
    assert len(txns) == 2 and str(txns[0].debit) == "867.00" and str(txns[1].credit) == "33.00"
    assert str(txns[0].balance) == "5292.64" and str(txns[1].balance) == "5325.64"
