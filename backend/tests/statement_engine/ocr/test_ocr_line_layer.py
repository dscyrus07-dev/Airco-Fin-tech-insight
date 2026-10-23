"""The recogniser's own text boxes as the engine's text layer (ocr/line_layer.py).

The first real-GPU evaluation (docs/ocr/R8_DEVIN_REPORT.md) found the VL model merging two adjacent money
titles into one table cell on every split-layout statement, and collapsing the two money columns of each data
row into a single value. Markup like that has lost the column boundary altogether, so no amount can be
attributed to a side from it. The boundary does survive in the line boxes, as the gap between them.

These tests build a page both ways from the SAME statement and assert the difference.
"""
from __future__ import annotations

from decimal import Decimal

from app.services.statement_engine.ocr.contracts import OcrBlock, OcrDocument, OcrLine, OcrPage
from app.services.statement_engine.ocr.line_layer import line_words, page_from_lines
from app.services.statement_engine.ocr.reader import OCR_FUSED_AMOUNTS, OCR_NO_TEXT_BOXES, read_document, text_layer

from . import synthetic as syn

# a 200-dpi A4 page, with the bands a real statement prints
BANDS = {"date": (100, 210), "narr": (260, 690), "ref": (700, 860),
         "debit": (980, 1140), "credit": (1210, 1360), "balance": (1440, 1620)}
TITLES = {"date": "Date", "narr": "Narration", "ref": "Chq./Ref.No.",
          "debit": "Withdrawal Amt.", "credit": "Deposit Amt.", "balance": "Closing Balance"}
MERGED_HEADER = ("Date", "Narration", "Chq./Ref.No.", "Withdrawal Amt.Deposit Amt.", "Closing Balance")


def _box(band, text, right_aligned=False, y=0.0, h=22.0):
    x0, x1 = BANDS[band]
    if right_aligned:                      # amounts print flush to the column's right edge
        x0 = max(x0, x1 - max(len(text), 1) * 11.0)
    return OcrLine(text, [float(x0), float(y), float(x1), float(y + h)], 0.97)


def _lines(rows):
    out = [_box(b, TITLES[b], y=300.0) for b in BANDS]
    for i, r in enumerate(rows):
        y = 360.0 + i * 40.0
        out.append(_box("date", r["date"].strftime("%d/%m/%Y"), y=y))
        out.append(_box("narr", r["narr"], y=y))
        out.append(_box("ref", r["ref"], y=y))
        if r["dr"] is not None:
            out.append(_box("debit", syn._fmt(r["dr"]), right_aligned=True, y=y))
        if r["cr"] is not None:
            out.append(_box("credit", syn._fmt(r["cr"]), right_aligned=True, y=y))
        out.append(_box("balance", syn._fmt(r["bal"]), right_aligned=True, y=y))
    return out


def _collapsed_markup(rows):
    """What the VL model actually returned: titles merged, and one money value per row instead of two."""
    out = ["<table>", "<tr>" + "".join(f"<th>{c}</th>" for c in MERGED_HEADER) + "</tr>"]
    for r in rows:
        amt = syn._fmt(r["dr"]) if r["dr"] is not None else syn._fmt(r["cr"])
        cells = [r["date"].strftime("%d/%m/%Y"), r["narr"], r["ref"], amt, syn._fmt(r["bal"])]
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    return "".join(out + ["</table>"])


def _doc(rows, with_lines=True, with_blocks=True):
    blocks = []
    if with_blocks:
        blocks = [OcrBlock("text", [40, 70, 900, 120],
                           f"Statement of account from {rows[0]['date']:%d/%m/%Y} to {rows[-1]['date']:%d/%m/%Y}"),
                  OcrBlock("table", [40, 140, 1600, 1900], _collapsed_markup(rows))]
    return OcrDocument(pages=[OcrPage(page=1, width=1654, height=2339, blocks=blocks,
                                      lines=_lines(rows) if with_lines else [], elapsed_s=1.0)],
                       engine="test", verifier="test", dpi=200)


def test_default_text_layer_is_blocks():
    assert text_layer() == "blocks"


def test_markup_path_refuses_the_collapsed_table(monkeypatch):
    """Control: with the merged titles the markup cannot say which side an amount belongs to."""
    monkeypatch.setenv("STATEMENT_ENGINE_OCR_TEXT_LAYER", "blocks")
    res = read_document(_doc(syn.make_rows(26)))
    assert res.verdict == "FAILED"
    assert res.code in ("AMBIGUOUS_MONEY_COLUMNS", "INVALID_SPEC", "LOW_CONFIDENCE_COLUMNS", "NO_TABLE_HEADER")


def test_line_boxes_read_the_same_statement_with_the_right_sides(monkeypatch):
    """The boundary the markup lost is the gap between boxes, so the sides survive."""
    monkeypatch.setenv("STATEMENT_ENGINE_OCR_TEXT_LAYER", "lines")
    rows = syn.make_rows(26)
    res = read_document(_doc(rows))
    assert res.verdict == "REVIEW" and res.ok, f"{res.code}: {res.detail}"
    got = res.universal.outcome.rows
    assert len(got) == len(rows)
    for want, nrow in zip(rows, got):
        txn = nrow.txn
        assert txn.date == want["date"].isoformat()
        assert (txn.debit or None) == (Decimal(str(want["dr"])) if want["dr"] is not None else None)
        assert (txn.credit or None) == (Decimal(str(want["cr"])) if want["cr"] is not None else None)
        assert txn.balance == Decimal(str(want["bal"]))
    assert res.to_block()["text_layer"] == "lines"


def test_line_layer_needs_no_markup_at_all(monkeypatch):
    monkeypatch.setenv("STATEMENT_ENGINE_OCR_TEXT_LAYER", "lines")
    res = read_document(_doc(syn.make_rows(26), with_blocks=False))
    assert res.verdict == "REVIEW" and res.to_block()["rows"] == 26


def test_page_without_text_boxes_is_reported_not_treated_as_empty(monkeypatch):
    monkeypatch.setenv("STATEMENT_ENGINE_OCR_TEXT_LAYER", "lines")
    res = read_document(_doc(syn.make_rows(26), with_lines=False))
    assert res.verdict == "FAILED"
    assert res.failed_pages == {1: OCR_NO_TEXT_BOXES}
    assert res.to_block()["rows"] == 0


def test_a_box_holding_two_amounts_is_counted_as_estimated(monkeypatch):
    """Adjacent values fuse into one box; the split between them is a guess and must be visible."""
    monkeypatch.setenv("STATEMENT_ENGINE_OCR_TEXT_LAYER", "lines")
    rows = syn.make_rows(26)
    doc = _doc(rows)
    page = doc.pages[0]
    page.lines.append(OcrLine("3,58,814.09 6,65,814.32", [980.0, 1500.0, 1360.0, 1522.0], 0.95))
    res = read_document(doc)
    assert res.fused_amounts >= 1
    assert OCR_FUSED_AMOUNTS in res.review_codes or res.verdict == "FAILED"


def test_single_token_box_keeps_its_measured_edges():
    w = line_words(OcrLine("1,234.56", [1000.0, 50.0, 1140.0, 72.0], 0.99))
    assert len(w) == 1 and w[0].x0 == 1000.0 and w[0].x1 == 1140.0 and w[0].top == 50.0


def test_multi_token_box_pins_its_outer_edges():
    w = line_words(OcrLine("UPI SWIGGY 402911", [260.0, 50.0, 690.0, 72.0], 0.99))
    assert [x.text for x in w] == ["UPI", "SWIGGY", "402911"]
    assert w[0].x0 == 260.0 and w[-1].x1 == 690.0
    assert all(a.x1 <= b.x0 + 0.01 for a, b in zip(w, w[1:]))      # in order, non-overlapping


def test_unusable_boxes_are_skipped_not_placed_at_the_origin():
    page = OcrPage(page=1, width=1654, height=2339, lines=[OcrLine("x", [0.0, 0.0, 0.0, 0.0], 0.9),
                                                           OcrLine("", [10.0, 0.0, 90.0, 20.0], 0.9)])
    stats = {}
    assert page_from_lines(page, stats) is None and stats["unusable_lines"] == 2
