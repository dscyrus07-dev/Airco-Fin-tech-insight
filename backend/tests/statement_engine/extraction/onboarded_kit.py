"""Shared builders for onboarded-bank synthetic tests.

Pages are built from word coordinates in code (same convention as
test_generic_engine.py): no PDFs and no customer data. The builder reads the
spec's own column titles, so a spec change that breaks the layout contract
breaks the test.
"""
import re
from typing import List, Optional

from app.services.statement_engine.extraction.layout_spec import LayoutSpec
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extraction.words import Word

W = 1200.0
DATE_SAMPLES = {
    "%d-%m-%Y": "05-01-2024", "%d/%m/%Y": "05/01/2024", "%d.%m.%Y": "05.01.2024",
    "%d-%m-%y": "05-01-24", "%d/%m/%y": "05/01/24",
    "%d %b %y": "05 Jan 24", "%d %b %Y": "05 Jan 2024",
    "%d-%b-%y": "05-Jan-24", "%d-%b-%Y": "05-Jan-2024",
    "%d %B %Y": "05 January 2024", "%d-%m-%Y %H:%M:%S": "05-01-2024 10:30:00",
    "%Y-%m-%d": "2024-01-05", "%m/%d/%Y": "01/05/2024", "%d%m%Y": "05012024",
    "%d %b, %Y": "05 Jan, 2024", "%d-%b-%Y %H:%M": "05-Jan-2024 10:30",
}


def w(text, x0, top):
    return Word(text, x0, x0 + 5.5 * len(text), top, top + 8)


def rt(text, edge, top):
    return Word(text, edge - 5.5 * len(text), edge, top, top + 8)


def sample_date(spec: LayoutSpec) -> str:
    for fmt in spec.date_format.split("|"):
        fmt = fmt.strip()
        if fmt in DATE_SAMPLES:
            return DATE_SAMPLES[fmt]
    return "05-01-2024"


def geometry(spec: LayoutSpec):
    """x0 for text columns, right-edge for money columns. Column start never
    precedes the previous column's title end."""
    money = [c for c in (spec.columns or {}) if c not in spec.text_columns]
    text_x = {}
    x = 30.0
    for c in spec.text_columns:
        text_x[c] = x
        toks = spec.columns[c][0]
        title_w = sum(5.5 * len(t) + 3 for t in toks)
        min_w = 60.0 if c in ("date", "value_date", "secondary_date") else 90.0
        x += max(min_w, title_w + 8)
    # money columns must start right of the last text column: classify_word assigns
    # the last text band to any word whose x0 is >= its header-left, so amounts placed
    # under a text column's band are swallowed as narration/ref text.
    edge = x + 10.0
    money_edge = {}
    money_left = {}
    for c in money:
        toks = spec.columns[c][0]
        width = max(75.0, sum(5.5 * len(t) + 3 for t in toks) + 8)
        money_left[c] = edge
        money_edge[c] = edge + width
        edge += width
    return text_x, money_edge, money_left


def header(spec: LayoutSpec, top=200.0):
    text_x, money_edge, _ = geometry(spec)
    ws = []
    for col in spec.text_columns:
        toks = spec.columns[col][0]
        tx = text_x[col]
        for t in toks:
            ws.append(w(t, tx, top))
            tx += 5.5 * len(t) + 3
    for col in spec.columns:
        if col in spec.text_columns:
            continue
        toks = spec.columns[col][0]
        edge = money_edge[col]
        for t in reversed(toks):
            ws.append(rt(t, edge, top))
            edge -= 5.5 * len(t) + 3
    return ws


def amount_text(spec: LayoutSpec, value: str, side: str) -> str:
    if spec.single_amount_column and not spec.side_marker_column:
        suf = "Cr" if side == "credit" else "Dr"
        return f"{value}{suf}" if spec.merge_drcr_suffix else f"{value} {suf}"
    return value


def _place_amount(spec: LayoutSpec, text, col, money_edge, money_left, top):
    if getattr(spec, "left_aligned_amounts", False):
        toks = spec.columns[col][0]
        title_w = sum(5.5 * len(t) + 3 for t in toks)
        return w(text, money_edge[col] - title_w + 2, top)
    return rt(text, money_edge[col], top)


def row(spec: LayoutSpec, top, narration="UPI REF 1234", debit=None, credit=None,
        balance="1,000.00", date=None):
    text_x, money_edge, money_left = geometry(spec)
    ws = [w(date or sample_date(spec), text_x[spec.text_columns[0]], top)]
    narr_col = next((c for c in spec.text_columns if "narr" in c or "desc" in c
                     or "partic" in c or "detail" in c), spec.text_columns[1])
    for col in spec.text_columns[1:]:
        if col == spec.secondary_date_column:
            ws.append(w(sample_date(spec), text_x[col], top))
        elif col == narr_col:
            tx = text_x[col]
            for t in narration.split():
                ws.append(w(t, tx, top))
                tx += 5.5 * len(t) + 3
            if spec.side_marker_column == col:
                ws.append(w("Cr" if credit is not None else "Dr", tx, top))
        else:
            tok = w("REF1", text_x[col], top)
            if tok.x1 < min(money_left.values()):
                ws.append(tok)
    if spec.single_amount_column:
        if debit or credit:
            ws.append(_place_amount(spec, amount_text(spec, debit or credit,
                                    "debit" if debit else "credit"),
                                    spec.single_amount_column, money_edge, money_left, top))
    else:
        if debit is not None:
            ws.append(_place_amount(spec, debit, spec.debit_column, money_edge, money_left, top))
        if credit is not None:
            ws.append(_place_amount(spec, credit, spec.credit_column, money_edge, money_left, top))
    ws.append(_place_amount(spec, balance, spec.balance_column, money_edge, money_left, top))
    if "side" in spec.columns and "side" not in spec.text_columns:
        ws.append(rt("Cr" if credit is not None else "Dr", money_edge["side"], top))
    return ws


def marker_words(spec: LayoutSpec, top=40.0):
    """Spec bank_markers as printed words (whitespace-free -> split camel/known words is
    not possible generically; callers pass the printed tokens they want)."""
    return [w(t, 30 + i * 90, top) for i, t in enumerate(marker_tokens(spec))]


def marker_tokens(spec: LayoutSpec) -> List[str]:
    toks = []
    for m in spec.bank_markers:
        # split an UPPERCASE marker into title words on common bank-word boundaries
        parts = re.findall(r"[A-Z]+(?:(?=[A-Z][a-z])|$)", m.title())
        toks.extend(parts or [m])
    return toks or ["BANK"]


def page(spec: LayoutSpec, rows_words: List[List[Word]], marker=True, extra: Optional[List[Word]] = None):
    ws = list(marker_words(spec) if marker else [])
    if extra:
        ws += extra
    ws += header(spec)
    for r in rows_words:
        ws += r
    return [Page(ws, W)]
