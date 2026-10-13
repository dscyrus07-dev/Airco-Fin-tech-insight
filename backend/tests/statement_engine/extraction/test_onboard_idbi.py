"""Synthetic layout tests for IDBI Bank (idbi). Pages built from word
coordinates; no PDFs, no customer data."""
from app.services.statement_engine import Confidence, detect_bank
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.extractors.idbi.layout_spec import IDBI_LAYOUT_1 as SPEC
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, header, row, rt, w

MARKER = [w("IDBI", 30, 40), w("BANK", 100, 40)]


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


def test_idbi_rows_parse_and_chain():
    r = route_pages(_page(_rows()), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert [str(t.balance) for t in txns] == ["900.00", "1900.00", "1500.00"]


def test_idbi_detected_by_detector():
    text = "IDBI Bank\nAccount Statement\nIFSC: IBKL0001234\n" \
           "Date Narration Withdrawal Deposit Balance\n" \
           "05 Jan 2024 UPI REF 100.00 900.00\n" * 3
    det = detect_bank([text])
    assert det.bank_id == "idbi" and det.confidence.name in ("HIGH", "VERY_HIGH", "MEDIUM")


def test_idbi_foreign_marker_refused():
    foreign = [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages(_page(_rows(), marker=False, extra=foreign), DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC.layout_id)


def test_idbi_narration_with_other_bank_still_idbi():
    rows = [row(SPEC, 220, "NEFTTOHDFCBANKLTD", debit="100.00", balance="900.00"),
            row(SPEC, 236, "IMPSICICIPAYOUT", credit="1,000.00", balance="1,900.00"),
            row(SPEC, 252, "AXISBANKREFUND", debit="400.00", balance="1,500.00")]
    r = route_pages(_page(rows), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_idbi_unread_dated_line_caps_at_review():
    rows = _rows()
    pgs = _page(rows)
    pgs[0].words += [w("06-01-2024", 30, 400), w("DATEDLINE", 140, 400),
                     rt("50.00", 490, 400), rt("1,450.00", 570, 400)]
    r = route_pages(pgs, DEFAULT_REGISTRY)
    if r.status == "v2":
        extras = r.result.metadata.extras
        assert extras.get("verdict") != "VERIFIED" or \
            any("unread" in str(x) for x in extras.get("warnings", []))


# ---- passbook variants: "Cheque No | Debit | Credit | Closing Balance" (dd/mm/yy) and the
# "Chq No. | Chq Date" family with Cr-suffixed balances + Opening/Closing Balance anchors ----
from app.services.statement_engine.extractors.idbi.layout_spec import (
    IDBI_LAYOUT_4 as SPEC4, IDBI_LAYOUT_5 as SPEC5)


def _rows4():
    return [
        row(SPEC4, 220, "TWDSGB", credit="450.00", balance="8,952.81  CR", date="01/06/22"),
        row(SPEC4, 236, "UPIDR", debit="2,000.00", balance="6,952.81  CR", date="02/06/22"),
    ]


def _page4(extra=None):
    ws = list(MARKER)
    if extra:
        ws += extra
    ws += header(SPEC4)
    for r in _rows4():
        ws += r
    return [Page(ws, W)]


def test_idbi_l4_rows_parse_crsuffix_balances():
    r = route_pages(_page4(), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC4.layout_id
    assert len(r.result.transactions) == 2
    assert [str(t.balance) for t in r.result.transactions] == ["8952.81", "6952.81"]


def test_idbi_l4_opening_as_on_anchor():
    ws = [w("Opening", 30, 150), w("Balance", 90, 150), w("As", 150, 150), w("On", 170, 150),
          w("01/06/2022", 200, 150), w(":8,502.81", 280, 150), w("CR", 340, 150)]
    r = route_pages([Page(ws + _page4()[0].words, W)], DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC4.layout_id


def test_idbi_l4_foreign_marker_refused():
    foreign = [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages(_page4(extra=foreign), DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC4.layout_id)


def _page5():
    ws = list(MARKER) + header(SPEC5)
    ws += [w("Opening", 81, 216), w("Balance", 130, 216), w("463.00Cr", 527, 216)]
    ws += [
        *row(SPEC5, 236, "ACHAPBS", credit="3.95", balance="466.95Cr"),
        *row(SPEC5, 252, "SALARYCR", credit="1,000.00", balance="1,466.95Cr"),
        *row(SPEC5, 268, "ATM DR", debit="400.00", balance="1,066.95Cr"),
    ]
    ws += [w("Closing", 30, 316), w("Balance", 90, 316), w("1,403.95", 356, 316),
           w("403.95", 458, 316), w("1,066.95", 524, 316), w("Cr", 561, 316)]
    return [Page(ws, W)]


def test_idbi_l5_full_anchors_verify():
    r = route_pages(_page5(), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC5.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert r.result.metadata.extras.get("verdict") == "VERIFIED"
