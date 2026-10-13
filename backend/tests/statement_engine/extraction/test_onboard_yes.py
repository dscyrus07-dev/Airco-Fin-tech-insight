"""Synthetic layout tests for Yes Bank (yes). Pages built from word
coordinates; no PDFs, no customer data."""
from app.services.statement_engine import Confidence, detect_bank
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.extractors.yes.layout_spec import YES_LAYOUT_1 as SPEC
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, header, row, rt, w

MARKER = [w("YES", 30, 40), w("BANK", 100, 40), w("YESB0001234", 170, 40)]


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


def test_yes_rows_parse_and_chain():
    r = route_pages(_page(_rows()), DEFAULT_REGISTRY, bank_key="yes")
    assert r.status == "v2" and r.layout_id == SPEC.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert [str(t.balance) for t in txns] == ["900.00", "1900.00", "1500.00"]


def test_yes_detected_by_detector():
    text = "Yes Bank\nAccount Statement\nIFSC: YESB0001234\n" \
           "Date Narration Withdrawal Deposit Balance\n" \
           "05 Jan 2024 UPI REF 100.00 900.00\n" * 3
    det = detect_bank([text])
    assert det.bank_id == "yes" and det.confidence.name in ("HIGH", "VERY_HIGH", "MEDIUM")


def test_yes_foreign_marker_refused():
    foreign = [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages(_page(_rows(), marker=False, extra=foreign), DEFAULT_REGISTRY, bank_key="yes")
    assert not (r.status == "v2" and r.layout_id == SPEC.layout_id)


def test_yes_narration_with_other_bank_still_yes():
    rows = [row(SPEC, 220, "NEFTTOHDFCBANKLTD", debit="100.00", balance="900.00"),
            row(SPEC, 236, "IMPSICICIPAYOUT", credit="1,000.00", balance="1,900.00"),
            row(SPEC, 252, "AXISBANKREFUND", debit="400.00", balance="1,500.00")]
    r = route_pages(_page(rows), DEFAULT_REGISTRY, bank_key="yes")
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_yes_unread_dated_line_caps_at_review():
    rows = _rows()
    pgs = _page(rows)
    pgs[0].words += [w("06-01-2024", 30, 400), w("DATEDLINE", 140, 400),
                     rt("50.00", 490, 400), rt("1,450.00", 570, 400)]
    r = route_pages(pgs, DEFAULT_REGISTRY, bank_key="yes")
    if r.status == "v2":
        extras = r.result.metadata.extras
        assert extras.get("verdict") != "VERIFIED" or \
            any("unread" in str(x) for x in extras.get("warnings", []))


# ---- newer export family: literal 0.00 in the unused side, dated B/F opening row,
# "Opening Balance: ... Closing Balance:" summary tail, yesbank.in footer marker ----
from app.services.statement_engine.extractors.yes.layout_spec import YES_LAYOUT_3 as SPEC3


def _summary_line(top, opening="1,000.00", wd="500.00", dep="1,000.00", closing="1,500.00"):
    x = 30.0
    ws = []
    for t in ("Opening", "Balance:", opening, "Total", "Withdrawals:", wd,
              "Total", "Deposits:", dep, "Closing", "Balance:", closing):
        ws.append(w(t, x, top))
        x += 5.5 * len(t) + 3
    return ws


def _bf_row(spec, top, balance):
    return row(spec, top, "B/F", balance=balance)


def test_yes_zero_amount_unused_side_parses():
    rows = [row(SPEC, 220, "UPI DR", debit="100.00", credit="0.00", balance="900.00"),
            row(SPEC, 236, "UPI CR", debit="0.00", credit="1,000.00", balance="1,900.00")]
    r = route_pages(_page(rows), DEFAULT_REGISTRY, bank_key="yes")
    assert r.status == "v2" and r.layout_id == SPEC.layout_id
    assert len(r.result.transactions) == 2


def test_yes_bf_opening_row_plus_summary_verifies():
    ws = list(MARKER) + header(SPEC)
    ws += _bf_row(SPEC, 220, "1,000.00")
    ws += [
        *row(SPEC, 236, "UPI DR", debit="100.00", credit="0.00", balance="900.00"),
        *row(SPEC, 252, "UPI CR", debit="0.00", credit="1,000.00", balance="1,900.00"),
        *row(SPEC, 268, "ATM DR", debit="400.00", credit="0.00", balance="1,500.00"),
    ]
    ws += _summary_line(300)
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY, bank_key="yes")
    assert r.status == "v2" and r.layout_id == SPEC.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert all("b/f" not in str(t.description).lower() for t in txns)
    assert r.result.metadata.extras.get("verdict") == "VERIFIED"


def test_yes_l3_summary_anchors_verify():
    ws = list(MARKER) + header(SPEC3)
    ws += _bf_row(SPEC3, 220, "1,000.00")
    ws += [
        *row(SPEC3, 236, "UPI DR", debit="100.00", credit="0.00", balance="900.00"),
        *row(SPEC3, 252, "UPI CR", debit="0.00", credit="1,000.00", balance="1,900.00"),
        *row(SPEC3, 268, "ATM DR", debit="400.00", credit="0.00", balance="1,500.00"),
    ]
    ws += _summary_line(300)
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY, bank_key="yes")
    assert r.status == "v2" and r.layout_id == SPEC3.layout_id
    assert r.result.metadata.extras.get("verdict") == "VERIFIED"


def test_yes_domain_marker_routes_without_wordmark():
    ws = [w("care@yesbank.in", 30, 700)] + header(SPEC)
    ws += _bf_row(SPEC, 220, "1,000.00")
    ws += [
        *row(SPEC, 236, "UPI DR", debit="100.00", credit="0.00", balance="900.00"),
        *row(SPEC, 252, "UPI CR", debit="0.00", credit="1,000.00", balance="1,900.00"),
        *row(SPEC, 268, "ATM DR", debit="400.00", credit="0.00", balance="1,500.00"),
    ]
    ws += _summary_line(300)
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_yes_trailing_dated_section_not_swallowed():
    ws = list(MARKER) + header(SPEC)
    ws += _bf_row(SPEC, 220, "1,000.00")
    ws += [
        *row(SPEC, 236, "UPI DR", debit="100.00", credit="0.00", balance="900.00"),
        *row(SPEC, 252, "UPI CR", debit="0.00", credit="1,000.00", balance="1,900.00"),
        *row(SPEC, 268, "ATM DR", debit="400.00", credit="0.00", balance="1,500.00"),
    ]
    ws += _summary_line(300)
    ws += [w("20/11/2021", 30, 330), w("FD", 140, 330), w("CERT", 170, 330),
           rt("2,00,000.00", 570, 330)]
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY, bank_key="yes")
    assert r.status == "v2"
    assert len(r.result.transactions) == 3
