"""Synthetic layout tests for Bank of India (bank_of_india) — "DetailedStatement"
web export: Sr No | Date | Remarks | Debit | Credit | Balance, ₹-prefixed balances.
Pages built from word coordinates; no PDFs, no customer data."""
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extractors.bank_of_india.layout_spec import (
    BANK_OF_INDIA_LAYOUT_2 as SPEC,
)
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, header, row, w

DX = 200.0  # shift spec columns right so the "Sr No" furniture sits left of "Date"
MARKER = [w("BANK", 30, 40), w("OF", 90, 40), w("INDIA", 130, 40)]


def _shift(ws, dx=DX):
    return [w(wd.text, wd.x0 + dx, wd.top) for wd in ws]


def _hdr(top=200.0):
    return [w("Sr", 30.0, top), w("No", 60.0, top)] + _shift(header(SPEC, top))


def _row(top, sr, narration, debit=None, credit=None, balance="₹1,000.00", date="05-01-2024"):
    return [w(sr, 30.0, top)] + _shift(
        row(SPEC, top, narration, debit=debit, credit=credit, balance=balance, date=date))


def _page(rows, marker=True, extra=None):
    ws = list(MARKER if marker else [])
    if extra:
        ws += extra
    ws += _hdr()
    for r in rows:
        ws += r
    return [Page(ws, W)]


def _rows():
    return [
        _row(220, "1", "UPIREF1234", debit="1,000.00", balance="₹900.00"),
        _row(236, "2", "NEFTSALARY5678", credit="1,000.00", balance="₹1,900.00"),
        _row(252, "3", "ATMCASH", debit="400.00", balance="₹1,500.00"),
    ]


def test_boi_rows_parse_and_chain():
    r = route_pages(_page(_rows()), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert [str(t.balance) for t in txns] == ["900.00", "1900.00", "1500.00"]
    assert str(txns[0].debit) == "1000.00" and str(txns[1].credit) == "1000.00"


def test_boi_ifsc_label_marker_routes():
    extra = [w("IFSC:BKID0005649", 30, 56)]
    r = route_pages(_page(_rows(), marker=False, extra=extra), DEFAULT_REGISTRY)
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_boi_foreign_marker_refused():
    foreign = [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages(_page(_rows(), marker=False, extra=foreign), DEFAULT_REGISTRY)
    assert r.status == "fallback" and "foreign" in (r.fallback_reason or "")


def test_boi_no_marker_unconfirmed():
    r = route_pages(_page(_rows(), marker=False), DEFAULT_REGISTRY)
    assert r.status == "fallback"


def test_boi_changed_amount_not_verified():
    rows = _rows()
    rows[1] = _row(236, "2", "NEFTSALARY5678", credit="2,000.00", balance="₹1,900.00")
    r = route_pages(_page(rows), DEFAULT_REGISTRY)
    assert r.status != "v2" or r.result.verification_status != "VERIFIED"


def test_boi_dropped_row_not_verified():
    rows = _rows()
    rows = rows[:1] + rows[2:]
    r = route_pages(_page(rows), DEFAULT_REGISTRY)
    assert r.status != "v2" or r.result.verification_status != "VERIFIED"
