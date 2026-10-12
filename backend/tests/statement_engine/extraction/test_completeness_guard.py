"""Completeness guard: transaction lines outside the span of rows that were read must stop VERIFIED."""
from app.services.statement_engine.extraction.engine import _unread_transaction_lines, _CARRY_LINE
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extraction.words import Word
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY


class _Txn:
    def __init__(self, bal): self.balance = bal
class _Row:
    def __init__(self, bal): self.txn = _Txn(bal)


def _w(t, x, top): return Word(t, x, x + len(t) * 5, top, top + 9)


def _spec():
    return next(s for s in DEFAULT_REGISTRY.specs() if s.layout_id.startswith("axis_trandate"))


def _page(lines):
    ws = []
    for i, (d, amts) in enumerate(lines):
        y = 100 + i * 12
        ws.append(_w(d, 10, y))
        for j, a in enumerate(amts):
            ws.append(_w(a, 300 + 60 * j, y))
    return Page(ws)


def test_no_unread_when_all_lines_read():
    from decimal import Decimal
    p = _page([("01-01-2024", ["10.00", "110.00"]), ("02-01-2024", ["5.00", "105.00"])])
    assert _unread_transaction_lines([p], _spec(), [_Row(Decimal("110.00")), _Row(Decimal("105.00"))]) == 0


def test_lines_after_last_read_row_are_counted():
    from decimal import Decimal
    p = _page([("01-01-2024", ["10.00", "110.00"]), ("02-01-2024", ["5.00", "105.00"]),
               ("03-01-2024", ["7.00", "98.00"]), ("04-01-2024", ["1.00", "97.00"])])
    assert _unread_transaction_lines([p], _spec(), [_Row(Decimal("110.00")), _Row(Decimal("105.00"))]) == 2


def test_carry_lines_are_not_transactions():
    for t in ("OPENINGBALANCE", "BALANCEBROUGHTFORWARD", "CLOSINGBALANCE", "TOTAL"):
        assert _CARRY_LINE.search(t)
