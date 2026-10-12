"""Synthetic layout tests for Standard Chartered (scb). Pages built from word
coordinates; no PDFs, no customer data."""
from app.services.statement_engine import Confidence, detect_bank
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.extractors.scb.layout_spec import SCB_LAYOUT_1 as SPEC
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, header, page, row, rt, w

MARKER = [w("STANDARD", 30, 40), w("CHARTERED", 92, 40)]


def _rows():
    return [
        row(SPEC, 220, "UPI REF 1234", debit="100.00", balance="900.00"),
        row(SPEC, 236, "NEFT SALARY 5678", credit="1,000.00", balance="1,900.00"),
        row(SPEC, 252, "ATM CASH", debit="400.00", balance="1,500.00"),
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
    bals = [t.balance for t in txns]
    assert [str(b) for b in bals] == ["900.00", "1900.00", "1500.00"]


def test_scb_detected_by_detector():
    text = "Standard Chartered Bank\nAccount Statement\nIFSC: SCBL0036001\n" \
           "Date Value Date Description Cheque Deposit Withdrawal Balance\n" \
           "05 Jan 24 05 Jan 24 UPI REF 100.00 900.00\n" * 3
    det = detect_bank([text])
    assert det.bank_id == "standard_chartered" and det.confidence in (Confidence.HIGH, Confidence.VERY_HIGH, Confidence.MEDIUM)


def test_scb_foreign_marker_refused():
    # a page whose header region belongs to another bank must not serve scb
    foreign = [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages(_page(_rows(), marker=False, extra=foreign), DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC.layout_id)


def test_scb_narration_with_other_bank_still_scb():
    rows = [row(SPEC, 220, "NEFT TO HDFC BANK LTD", debit="100.00", balance="900.00"),
            row(SPEC, 236, "IMPS ICICI PAYOUT", credit="1,000.00", balance="1,900.00"),
            row(SPEC, 252, "AXIS BANK REFUND", debit="400.00", balance="1,500.00")]
    r = route_pages(_page(rows), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_scb_unread_dated_line_caps_at_review():
    # a dated amount line left outside the parsed rows => completeness guard REVIEW
    rows = _rows()
    extra = [w("06", 30, 400), w("Jan", 50, 400), w("24", 75, 400),
             w("DATEDLINE", 140, 400), rt("50.00", 490, 400), rt("1,450.00", 570, 400)]
    pgs = _page(rows, extra=None)
    pgs[0].words += extra
    r = route_pages(pgs, DEFAULT_REGISTRY)
    if r.status == "v2":
        extras = r.result.metadata.extras
        assert extras.get("verdict") != "VERIFIED" or any("unread" in str(x) for x in extras.get("warnings", []))
