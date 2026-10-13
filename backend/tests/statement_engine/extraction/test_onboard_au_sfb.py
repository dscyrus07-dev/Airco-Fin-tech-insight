"""Synthetic layout tests for AU Small Finance Bank (au_sfb). Pages built from word
coordinates; no PDFs, no customer data."""
from app.services.statement_engine import Confidence, detect_bank
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.extractors.au_sfb.layout_spec import AU_LAYOUT_1 as SPEC
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, header, row, rt, w

MARKER = [w("AU", 30, 40), w("SMALL", 60, 40), w("FINANCE", 110, 40), w("BANK", 170, 40), w("AUBL0001234", 30, 56)]


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


def test_au_sfb_rows_parse_and_chain():
    r = route_pages(_page(_rows()), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert [str(t.balance) for t in txns] == ["900.00", "1900.00", "1500.00"]


def test_au_sfb_detected_by_detector():
    text = "AU Small Finance Bank\nAccount Statement\nIFSC: AUBL0001234\n" \
           "Date Narration Withdrawal Deposit Balance\n" \
           "05 Jan 2024 UPI REF 100.00 900.00\n" * 3
    det = detect_bank([text])
    assert det.bank_id == "au_sfb" and det.confidence.name in ("HIGH", "VERY_HIGH", "MEDIUM")


def test_au_sfb_foreign_marker_refused():
    foreign = [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages(_page(_rows(), marker=False, extra=foreign), DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC.layout_id)


def test_au_sfb_narration_with_other_bank_still_au_sfb():
    rows = [row(SPEC, 220, "NEFT TO HDFC BANK LTD", debit="100.00", balance="900.00"),
            row(SPEC, 236, "IMPS ICICI PAYOUT", credit="1,000.00", balance="1,900.00"),
            row(SPEC, 252, "AXIS BANK REFUND", debit="400.00", balance="1,500.00")]
    r = route_pages(_page(rows), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_au_sfb_unread_dated_line_caps_at_review():
    rows = _rows()
    pgs = _page(rows)
    pgs[0].words += [w("06-01-2024", 30, 400), w("DATEDLINE", 140, 400),
                     rt("50.00", 490, 400), rt("1,450.00", 570, 400)]
    r = route_pages(pgs, DEFAULT_REGISTRY)
    if r.status == "v2":
        extras = r.result.metadata.extras
        assert extras.get("verdict") != "VERIFIED" or \
            any("unread" in str(x) for x in extras.get("warnings", []))
