"""Synthetic layout tests for AU Small Finance Bank (au_sfb). Pages built from word
coordinates; no PDFs, no customer data."""
from app.services.statement_engine import Confidence, detect_bank
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.extractors.au_sfb.layout_spec import AU_LAYOUT_1 as SPEC
from app.services.statement_engine.extractors.au_sfb.layout_spec import AU_LAYOUT_2 as SPEC2
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, header, row, rt, w

MARKER = [w("AU", 30, 40), w("SMALL", 60, 40), w("FINANCE", 110, 40), w("BANK", 170, 40), w("AUBL0001234", 30, 56)]
MARKER2 = [w("IFSC:AUBL0001234", 30, 40), w("www.aubank.in", 30, 56), w("customercare@aubank.in", 120, 56)]


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


def _header2(top=200.0):
    """AU_LAYOUT_2's real two-line header: titles on the first line, 'Date'/'Reference No.'
    wrapped onto the second."""
    return [
        w("Transaction", 26, top), w("Value Date", 98, top), w("Description/Narration", 169, top),
        w("Cheque/", 295, top), w("Debit (₹)", 384, top), w("Credit (₹)", 452, top), w("Balance (₹)", 518, top),
        w("Date", 41, top + 10), w("Reference No.", 291, top + 10),
    ]


def _row2(top, narr, debit=None, credit=None, balance="1,000.00", ref="134545276"):
    ws = [w("05 Jan 2024", 26, top), w("05 Jan 2024", 95, top), w(narr, 159, top), w(ref, 278, top)]
    ws += [rt(debit, 420, top)] if debit else [w("-", 430, top)]
    ws += [rt(credit, 491, top)] if credit else [w("-", 500, top)]
    if balance is not None:
        ws += [rt(balance, 566, top)]
    return ws


def test_au_sfb_layout2_wrapped_header_parses_and_chains():
    ws = list(MARKER2) + _header2()
    ws += _row2(220, "OPENING", credit="1,000.00", balance="1,000.00")
    ws += _row2(236, "UPI REF 1234", debit="100.00", balance="900.00")
    ws += _row2(252, "NEFT SALARY", credit="400.00", balance="1,300.00")
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC2.layout_id
    txns = r.result.transactions
    assert len(txns) == 3 and [str(t.balance) for t in txns] == ["1000.00", "900.00", "1300.00"]
    assert txns[0].description.startswith("OPENING")


def test_au_sfb_layout2_sign_gap_negative_balance():
    ws = list(MARKER2) + _header2()
    ws += _row2(220, "OPENING", credit="1,000.00", balance="1,000.00")
    ws += _row2(236, "ACH DR RAZOR", debit="46,400.00", balance=None)  # placeholder replaced below
    ws[-1] = w("- 39,457.19", 531, 236)   # negative balance: sign and digits separated by a space
    ws += _row2(252, "ACH REVERSAL", credit="46,400.00", balance="6,942.81")
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC2.layout_id
    txns = r.result.transactions
    assert len(txns) == 3 and str(txns[1].balance) == "-39457.19"


def test_au_sfb_layout2_needs_aubank_marker():
    ws = _header2() + _row2(220, "UPI REF 1234", debit="100.00", balance="900.00") \
        + _row2(236, "NEFT SALARY", credit="1,000.00", balance="1,900.00")
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC2.layout_id)


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
