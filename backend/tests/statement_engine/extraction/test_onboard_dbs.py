"""Synthetic layout tests for DBS Bank (dbs). Pages built from word
coordinates; no PDFs, no customer data."""
from app.services.statement_engine import Confidence, detect_bank
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.extractors.dbs.layout_spec import DBS_LAYOUT_1 as SPEC
from app.services.statement_engine.extractors.dbs.layout_spec import DBS_LAYOUT_2 as SPEC2
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, header, row, rt, w

MARKER = [w("DBS", 30, 40), w("BANK", 100, 40)]


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


def test_dbs_rows_parse_and_chain():
    r = route_pages(_page(_rows()), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert [str(t.balance) for t in txns] == ["900.00", "1900.00", "1500.00"]


def test_dbs_detected_by_detector():
    text = "DBS Bank\nAccount Statement\nIFSC: DBSS0IN0811\n" \
           "Date Narration Withdrawal Deposit Balance\n" \
           "05 Jan 2024 UPI REF 100.00 900.00\n" * 3
    det = detect_bank([text])
    assert det.bank_id == "dbs" and det.confidence.name in ("HIGH", "VERY_HIGH", "MEDIUM")


def test_dbs_foreign_marker_refused():
    foreign = [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages(_page(_rows(), marker=False, extra=foreign), DEFAULT_REGISTRY)
    assert not (r.status == "v2" and r.layout_id == SPEC.layout_id)


def test_dbs_narration_with_other_bank_still_dbs():
    rows = [row(SPEC, 220, "NEFT TO HDFC BANK LTD", debit="100.00", balance="900.00"),
            row(SPEC, 236, "IMPS ICICI PAYOUT", credit="1,000.00", balance="1,900.00"),
            row(SPEC, 252, "AXIS BANK REFUND", debit="400.00", balance="1,500.00")]
    r = route_pages(_page(rows), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_dbs_unread_dated_line_caps_at_review():
    rows = _rows()
    pgs = _page(rows)
    pgs[0].words += [w("06-01-2024", 30, 400), w("DATEDLINE", 140, 400),
                     rt("50.00", 490, 400), rt("1,450.00", 570, 400)]
    r = route_pages(pgs, DEFAULT_REGISTRY)
    if r.status == "v2":
        extras = r.result.metadata.extras
        assert extras.get("verdict") != "VERIFIED" or \
            any("unread" in str(x) for x in extras.get("warnings", []))


def _header2(top=200.0):
    """DBS_LAYOUT_2's real header: 'Cheque/Reference' wraps 'number' onto the next line."""
    return [
        w("Transaction date", 38, top), w("Value date", 106, top), w("Branch code", 157, top),
        w("Description", 209, top), w("Cheque/Reference", 283, top),
        rt("Debit", 418, top), rt("Credit", 475, top), rt("Balance", 566, top),
        w("number", 283, top + 10),
    ]


def _row2(top, narr, debit=None, credit=None, balance="1,000.00", branch="999"):
    ws = [w("01/12/2022", 38, top), w("01/12/2022", 106, top), w(branch, 157, top), w(narr, 209, top)]
    ws += [rt(debit, 418, top)] if debit else []
    ws += [rt(credit, 475, top)] if credit else []
    ws += [rt(balance, 566, top)]
    return ws


def test_dbs_layout2_wrapped_ref_header_parses_and_chains():
    ws = list(MARKER) + _header2()
    ws += _row2(220, "UPI DR 233548321138", debit="40.00", balance="2,367.63")
    ws += _row2(236, "NEFT SALARY", credit="1,000.00", balance="3,367.63")
    ws += _row2(252, "ATM CASH", debit="367.63", balance="3,000.00")
    r = route_pages([Page(ws, W)], DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC2.layout_id
    txns = r.result.transactions
    assert len(txns) == 3 and [str(t.balance) for t in txns] == ["2367.63", "3367.63", "3000.00"]
    assert txns[0].description.startswith("UPI")


def test_dbs_layout2_summary_anchor_regexes():
    # last-page joined text "Opening balance Total debit amount Debit count INR2,407.63 ..."
    import re as _re
    line = "OpeningbalanceTotaldebitamountDebitcountINR2,407.63INR12,07,921.80453" \
        "ClosingbalanceTotalcreditamountCreditcountINR5,266.31INR12,10,780.48140"
    mo = SPEC2.opening_balance_re.search(line)
    mc = SPEC2.closing_balance_re.search(line)
    assert mo and mo.group(1) == "2,407.63"
    assert mc and mc.group(1) == "5,266.31"
