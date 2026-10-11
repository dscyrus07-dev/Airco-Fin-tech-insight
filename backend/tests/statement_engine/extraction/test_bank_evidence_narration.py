"""Phase-8B blocker B1: a bank name inside a wrapped narration line (e.g. a UPI counterparty) must never count as the
statement's own bank evidence."""
from app.services.statement_engine.extraction import registry as reg
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extraction.words import Word


def _w(text, x, top):
    return Word(text, x, x + len(text) * 5, top, top + 9)


def _page(wrapped_tail=("HDFC", "BANK"), footer="FOOTER"):
    words = [_w("LETTERHEAD", 10, 20), _w("URBANBANK", 60, 20)]
    y = 100
    for d in ("01-01-2024", "02-01-2024", "03-01-2024"):
        words += [_w(d, 10, y), _w("UPI", 80, y), _w("1,000.00", 300, y)]
        y += 12
    if wrapped_tail:
        words += [_w(t, 80 + 40 * i, y) for i, t in enumerate(wrapped_tail)]
    words += [_w(footer, 10, y + 90)]
    return Page(words)


def test_wrapped_narration_under_last_row_is_not_evidence():
    assert "HDFC" not in reg._outside_body_text([_page()])


def test_narration_between_rows_is_not_evidence():
    words = [_w("01-01-2024", 10, 100), _w("1,000.00", 300, 100), _w("HDFC", 80, 112),
             _w("02-01-2024", 10, 124), _w("2,000.00", 300, 124)]
    assert "HDFC" not in reg._outside_body_text([Page(words)])


def test_letterhead_and_footer_still_count():
    text = reg._outside_body_text([_page()])
    assert "URBANBANK" in text and "FOOTER" in text


def test_page_without_dated_rows_keeps_amount_free_lines():
    words = [_w("COVER", 10, 20), _w("HDFC", 60, 20), _w("1,000.00", 10, 60)]
    text = reg._outside_body_text([Page(words)])
    assert "HDFC" in text and "1,000.00".replace(",", "").upper() not in text
