"""Synthetic N2 table-shape generators (word-coordinate pages; no PDFs, no customer data).

Each generator returns ``(spec_fixtures)``-agnostic Page lists given a spec's column geometry:
the test builds the LayoutSpec, derives a geometry map (column -> x0), and these helpers emit
header/rows/summary words. Shapes:

- ``segmented_statement``   per-account sub-tables: each segment opens with a segment header
  line and may close with a printed per-segment transaction count
- ``balanceless_statement`` rows carry date/narration/debit/credit but NO balance column;
  a printed totals block may follow
- ``mid_document_anchors``  opening/closing anchor lines printed mid-document (a per-segment
  summary page between table runs), not on page 1 / last page
- ``checkpoint_statement``  no balance column; ``BALANCE CARRIED FORWARD`` / ``BROUGHT FORWARD``
  lines at page boundaries carry the running balance
- ``inline_balance_statement`` the row's balance prints on a ``Balance : <amt>`` continuation
  line, not on the dated line
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple

# local reimplementation of the test-kit builders (synth runs without pytest fixtures)
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../backend"))
from app.services.statement_engine.extraction.rows import Page  # noqa: E402
from app.services.statement_engine.extraction.words import Word  # noqa: E402


def w(text, x0, top):
    return Word(text, x0, x0 + 5.5 * len(text), top, top + 8)


def rt(text, edge, top):
    return Word(text, edge - 5.5 * len(text), edge, top, top + 8)


def header_words(spec, geom: Dict[str, Tuple[float, float]], top=200.0):
    """One header line: each column's alt-0 seq tokens laid out left to right inside its band."""
    ws = []
    for col, alts in spec.columns.items():
        x0, width = geom[col]
        cx = x0 + 2.0
        for tok in alts[0]:
            ws.append(w(tok, cx, top))
            cx += 5.5 * len(tok) + 4.0
    return ws


def title_edges(spec, geom):
    """Right edge of each column title, for right-aligned money cells."""
    edges = {}
    for col, alts in spec.columns.items():
        x0, width = geom[col]
        last = alts[0][-1]
        edges[col] = x0 + 2.0 + sum(5.5 * len(t) + 4.0 for t in alts[0]) - 4.0
        _ = last
    return edges


def row_words(spec, geom, top, date, narration, debit, credit, balance, edges=None, seg_offset=0.0):
    """One dated row line; money cells right-aligned under their titles."""
    ws = []
    edges = edges or title_edges(spec, geom)
    for col in spec.columns:
        x0, _wdt = geom[col]
        if col == spec.text_columns[0]:
            ws.append(w(date, x0, top))
        elif col in spec.amount_columns or (spec.balance_column and col == spec.balance_column):
            continue
        elif "narr" in col or "desc" in col or "partic" in col:
            for i, t in enumerate(narration.split()):
                ws.append(w(t, x0 + i * 45, top))
    def _amt(col, text):
        if text is not None:
            ws.append(rt(text, edges[col], top))
    if spec.single_amount_column:
        _amt(spec.single_amount_column, debit if debit is not None else credit)
    else:
        _amt(spec.debit_column, debit)
        _amt(spec.credit_column, credit)
    if spec.balance_column:
        _amt(spec.balance_column, balance)
    return ws


def balanceless_statement(spec, geom, rows: Sequence[Tuple[str, str, str, str]],
                          totals: Optional[Tuple[str, str, str]] = None, marker="N2SYNBANK"):
    """rows: (date, narration, debit, credit); totals: (count, debits, credits) printed after."""
    ws = [w(marker, 30, 40)] + header_words(spec, geom)
    top = 240.0
    for d, narr, dr, cr in rows:
        ws += row_words(spec, geom, top, d, narr, dr, cr, None)
        top += 16.0
    if totals:
        top += 10.0
        ws += [w("Total", 30, top), w("Transactions:", 60, top), w(str(totals[0]), 160, top)]
        top += 14.0
        ws += [w("TotalDebits:", 30, top), rt(totals[1], 320, top),
               w("TotalCredits:", 360, top), rt(totals[2], 620, top)]
    return [Page(ws, width=1200.0)]


def segmented_statement(spec, geom, segments: List[dict], marker="N2SYNBANK",
                        anchors: Optional[Tuple[str, str]] = None):
    """segments: [{"header": "ACCOUNTNO:1001", "count": 3 or None,
                   "rows": [(date, narr, dr, cr, bal), ...]}].
    anchors=(opening, closing) prints them before the first segment header / after the last."""
    ws = [w(marker, 30, 40)]
    top = 60.0
    if anchors:
        ws += [w("OPENINGBALANCE", 30, top), w(":", 110, top), w(anchors[0], 120, top)]
        top += 20.0
    for seg in segments:
        top += 20.0
        ws.append(w(seg["header"], 30, top))
        top += 24.0
        ws += header_words(spec, geom, top=top)
        top += 40.0
        for d, narr, dr, cr, bal in seg["rows"]:
            ws += row_words(spec, geom, top, d, narr, dr, cr, bal)
            top += 16.0
        if seg.get("count") is not None:
            top += 8.0
            ws += [w("Total", 30, top), w("Number", 80, top), w("of", 120, top),
                   w("Transactions", 145, top), w(":", 210, top), w(str(seg["count"]), 230, top)]
    if anchors:
        top += 20.0
        ws += [w("CLOSINGBALANCE", 30, top), w(":", 110, top), w(anchors[1], 120, top)]
    return [Page(ws, width=1200.0)]


def mid_document_anchors(spec, geom, rows_a, rows_b, rows_c, opening, closing,
                         anchor_text=("OPENINGBALANCE", "CLOSINGBALANCE"), marker="N2SYNBANK"):
    """Three pages; the printed opening sits mid-document on page 2, the closing on page 2's
    bottom (both strictly interior: not page 1, not the last page)."""
    ws1 = [w(marker, 30, 40)] + header_words(spec, geom)
    top = 240.0
    for d, narr, dr, cr, bal in rows_a:
        ws1 += row_words(spec, geom, top, d, narr, dr, cr, bal)
        top += 16.0
    ws2 = []
    top2 = 60.0
    ws2 += [w(anchor_text[0], 30, top2), rt(opening, 320, top2)]
    top2 += 30.0
    for d, narr, dr, cr, bal in rows_b:
        ws2 += row_words(spec, geom, top2, d, narr, dr, cr, bal)
        top2 += 16.0
    ws2 += [w(anchor_text[1], 30, top2 + 10.0), rt(closing, 320, top2 + 10.0)]
    ws3 = []
    top3 = 60.0
    for d, narr, dr, cr, bal in rows_c:
        ws3 += row_words(spec, geom, top3, d, narr, dr, cr, bal)
        top3 += 16.0
    return [Page(ws1, width=1200.0), Page(ws2, width=1200.0), Page(ws3, width=1200.0)]


def checkpoint_statement(spec, geom, segments: List[Tuple[str, List[Tuple[str, str, str, str]]]],
                         marker="N2SYNBANK"):
    """Balance-less rows bracketed by carried/brought-forward balances.

    segments: [(opening_balance, [(date, narr, dr, cr), ...]), ...] — each list element becomes
    one page ending in a CARRIED FORWARD line (except the last)."""
    pages = []
    for si, (start_bal, rows) in enumerate(segments):
        ws = []
        if si == 0:
            ws.append(w(marker, 30, 40))
            ws += header_words(spec, geom)
        top = 60.0
        if si > 0:
            ws += [w("BALANCE", 30, top), w("BROUGHT", 80, top), w("FORWARD", 140, top), rt(start_bal, 320, top)]
            top += 30.0
        else:
            top = 240.0
        for tup in rows:
            d, narr, dr, cr = tup[0], tup[1], tup[2], tup[3]
            ws += row_words(spec, geom, top, d, narr, dr, cr, tup[4] if len(tup) > 4 else None)
            top += 16.0
        end_bal = Decimal(start_bal.replace(",", "")) + sum(
            Decimal((tup[3] or "0").replace(",", "")) - Decimal((tup[2] or "0").replace(",", "")) for tup in rows)
        if si < len(segments) - 1:
            top += 10.0
            ws += [w("BALANCE", 30, top), w("CARRIED", 80, top), w("FORWARD", 140, top), rt(f"{end_bal:,.2f}", 320, top)]
        pages.append(Page(ws, width=1200.0))
    return pages


def inline_balance_statement(spec, geom, rows, marker="N2SYNBANK"):
    """rows: (date, narr, dr, cr, bal) — the balance prints on a `Balance : <amt>` line below
    the dated line (the dated line itself carries no balance cell)."""
    ws = [w(marker, 30, 40)] + header_words(spec, geom)
    top = 240.0
    for d, narr, dr, cr, bal in rows:
        ws += row_words(spec, geom, top, d, narr, dr, cr, None)
        top += 16.0
        x0 = geom[spec.balance_column][0]
        ws += [w("Balance", x0, top), w(":", x0 + 40, top), w(bal, x0 + 50, top)]
        top += 16.0
    return [Page(ws, width=1200.0)]


def grouped_statement(spec, geom, sections, marker="N3SYNBANK", page_breaks=(),
                      doubled=False, repeated_header=True, header_top=200.0,
                      period=None, anchors=None, summary_line=None):
    """Date-grouped statement: each section is (label, [(narr, amount, balance), ...]); rows print
    no date and inherit the section's. ``sections`` is a list of (label, rows); ``page_breaks`` is a
    set of section indices that start a new page (the header re-prints when repeated_header).
    ``doubled`` doubles every letter of the header titles (app-export look).
    ``period`` prints the statement period text on page 1; ``anchors``=(opening, closing) prints
    truncated whole-unit anchor lines B<opening>B ... B<closing>."""
    """Date-grouped statement: each section is (label, [(narr, amount, balance), ...]); rows print
    no date and inherit the section's. ``sections`` is a list of (label, rows); ``page_breaks`` is a
    set of section indices that start a new page (the header re-prints when repeated_header).
    ``doubled`` doubles every letter of the header titles (app-export look)."""
    edges = title_edges(spec, geom)
    amt_col = spec.single_amount_column or spec.debit_column

    def hdr(top):
        ws = []
        for col, alts in spec.columns.items():
            x0, _wd = geom[col]
            cx = x0 + 2.0
            for tok in alts[0]:
                t = "".join(ch * 2 for ch in tok) if doubled else tok
                ws.append(w(t, cx, top))
                cx += 5.5 * len(t) + 4.0
        return ws

    pages, ws, top = [], [w(marker, 30, 40)], header_top
    if period:
        ws.append(w(period, 30, 60.0))
    if anchors:
        ws.append(w("B" + anchors[0] + "B", 30, 100.0))
    ws += hdr(top)
    top += 40.0
    for si, (label, rows) in enumerate(sections):
        if si in page_breaks:
            pages.append(Page(ws, width=1200.0))
            ws, top = [], 60.0
            if repeated_header:
                ws += hdr(top)
                top += 40.0
        if label is not None:
            ws.append(w(label, geom["date"][0], top))      # section date inside the date zone
            top += 16.0
        for narr, amt, bal in rows:
            x0, _wd = geom["narration"]
            for i, t in enumerate(narr.split()):
                ws.append(w(t, x0 + i * 45, top))
            if amt is not None:
                ws.append(rt(amt, edges[amt_col], top))
            if bal is not None and spec.balance_column:
                ws.append(rt(bal, edges[spec.balance_column], top))
            top += 16.0
    if anchors:
        ws.append(w("CLOSINGB", 30, top + 10.0))
        ws.append(w("B" + anchors[1], 900, top + 10.0))
    if summary_line:
        ws.append(w(summary_line, 30, top + 30.0))
    pages.append(Page(ws, width=1200.0))
    return pages
