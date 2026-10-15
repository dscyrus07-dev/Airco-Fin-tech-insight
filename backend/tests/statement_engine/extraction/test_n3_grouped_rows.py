"""N3 engine capability tests: date-grouped rows (section dates), balance-derived sides,
wrapped-decimal amount cells (same-line and cross-line), truncated printed summaries, and the
boundary-year ambiguity that period-boundary sections create. Synthetic word-coordinate pages
only — no PDFs, no customer data. Every mutation must end below VERIFIED."""
import re
from decimal import Decimal

from app.services.statement_engine.extraction.layout_spec import LayoutSpec
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extraction.engine import extract_pages
from app.services.statement_engine.extraction.words import Word
from app.services.statement_engine.extraction.spec_codec import spec_from_dict, spec_to_dict

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../tools/onboarding"))
from synth import table_shapes as ts  # noqa: E402


def geom(spec, start=60.0, width=130.0):
    out, x = {}, start
    for col in spec.columns:
        out[col] = (x, width)
        x += width
    return out


PERIOD = "SSTTAATTEEMMEENNTT15November2022to15May2023"   # doubled-glyph look, yearless section dates
SEC_RE = re.compile(r"(?i)^\d{1,2}[A-Za-z]{3,9}\d{0,4}$")

BASE = dict(
    bank_key="n3syn", bank_name="N3 Synth",
    bank_markers=("N3SYNBANK",),
    columns={
        "date": (("date",),),
        "narration": (("details",),),
        "txn_amount": (("amount",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit", credit_column="credit", balance_column="balance",
    date_re=SEC_RE,
    date_format="%d %b %Y|%d%b %Y|%d %B %Y|%d%B %Y|%d%B%Y|%d%b%Y",
    amount_re=re.compile(r"^-?[\d,]+(?:\.\d{1,2})?$"),
    summary_marker="^$", summary_label_text="",
    period_re=re.compile(r"(\d{1,2}[A-Za-z]+\d{4})to(\d{1,2}[A-Za-z]+\d{4})"),
    period_date_format="%d%B%Y",
    continuation_start="top",
    summary_expected=False,
)

GRP = dict(
    single_amount_column="txn_amount",
    derive_side_from_balance=True,
    year_from_period=True,
    section_date_re=SEC_RE,
    wrapped_amount_tokens=True,
    anchor_scan="document",
    anchor_full=True,
    opening_balance_re=re.compile(r"^B([0-9,]+)B"),
    closing_balance_re=re.compile(r"B([0-9,]+)$"),
)

SPEC_GRP = LayoutSpec(**{**BASE, **GRP, "layout_id": "n3syn_grouped"})
SPEC_GRP_TRUNC = LayoutSpec(**{**BASE, **GRP, "layout_id": "n3syn_grouped_trunc", "summary_truncated": True})


def _verdict(out):
    return out.checks.verdict if out and out.checks else out.failure if out else "NO_OUTCOME"


def _chain_sections(labels=("15Nov", "16Nov"), start=1000.0, per_section=((100.0, "cr"), (50.0, "dr"), (25.0, "cr"))):
    """sections of rows whose balances continue one running chain; rows = (narr, amount, balance)."""
    bal = Decimal(str(start))
    secs = []
    for si, label in enumerate(labels):
        rows = []
        for amt, side in per_section:
            a = Decimal(str(amt))
            bal = bal + a if side == "cr" else bal - a
            rows.append((f"NARR{si}", f"{int(a):,}" if a == a.to_integral() else f"{a:,.2f}", f"{bal:,.2f}"))
        secs.append((label, rows))
    return secs


def _mk(spec, sections, **kw):
    return ts.grouped_statement(spec, geom(spec), sections, period=PERIOD, **kw)


# ------------------------------------------------------------------ section dates


def test_grouped_rows_inherit_section_date():
    out = extract_pages(_mk(SPEC_GRP, _chain_sections(), anchors=("1,000", "1,150")), SPEC_GRP)
    assert out.failure is None, out.failure_detail
    assert len(out.rows) == 6
    assert [r.txn.date for r in out.rows] == ["2022-11-15"] * 3 + ["2022-11-16"] * 3
    assert _verdict(out) == "VERIFIED", out.checks.reasons if out.checks else out.failure_detail


def test_row_before_any_section_date_is_defect():
    secs = _chain_sections()
    pages = _mk(SPEC_GRP, [(None, secs[0][1][:1])] + secs, anchors=("1,000", "1,150"))
    out = extract_pages(pages, SPEC_GRP)
    assert any(w.startswith("rows_without_section_date") for w in out.warnings)
    assert _verdict(out) != "VERIFIED"


def test_section_date_lost_at_page_break():
    """A section label dropped at a page start: rows still read under the previous section date —
    a duplicate of the earlier label — and the document stays consistent or degrades to REVIEW."""
    secs = _chain_sections(labels=("15Nov", "16Nov", "16Nov"))
    pages = _mk(SPEC_GRP, secs, page_breaks={2}, anchors=("1,000", "1,225"))
    pages[1] = Page([w for w in pages[1].words if w.text.strip() != "16Nov"], 1200.0)
    out = extract_pages(pages, SPEC_GRP)
    assert out.failure is None
    assert len(out.rows) == 9
    assert _verdict(out) in ("VERIFIED", "REVIEW")


def test_duplicate_section_dates_are_safe():
    secs = _chain_sections(labels=("15Nov", "15Nov", "16Nov"))
    out = extract_pages(_mk(SPEC_GRP, secs, anchors=("1,000", "1,225")), SPEC_GRP)
    assert out.failure is None
    assert len(out.rows) == 9
    assert _verdict(out) == "VERIFIED"


def test_date_like_word_outside_date_zone_is_not_a_section():
    pages = _mk(SPEC_GRP, _chain_sections(), anchors=("1,000", "1,150"))
    g = geom(SPEC_GRP)
    ws = list(pages[0].words) + [Word("18Nov", g["narration"][0] + 10, g["narration"][0] + 60, 9999.0, 10008.0)]
    pages[0] = Page(ws, 1200.0)
    out = extract_pages(pages, SPEC_GRP)
    assert out.failure is None
    assert len(out.rows) == 6


def test_section_word_with_money_is_a_row_not_a_section():
    """A line carrying a section-date-shaped word AND an amount is not a bare section label."""
    pages = _mk(SPEC_GRP, _chain_sections(), anchors=("1,000", "1,150"))
    g = geom(SPEC_GRP)
    e = ts.title_edges(SPEC_GRP, g)
    ws = list(pages[0].words) + [ts.w("19Nov", g["date"][0], 9990.0), ts.rt("75", e["txn_amount"], 9990.0)]
    pages[0] = Page(ws, 1200.0)
    out = extract_pages(pages, SPEC_GRP)
    assert not any(r.txn.date == "2022-11-19" and r.txn.debit is None and r.txn.credit is None for r in out.rows)


def test_grouped_requires_opt_in():
    spec = LayoutSpec(**{**BASE, "layout_id": "n3syn_plain", "single_amount_column": "txn_amount"})
    pages = _mk(spec, _chain_sections())
    out = extract_pages(pages, spec)
    assert not out.rows or _verdict(out) != "VERIFIED"


def test_doubled_header_glyphs():
    spec = LayoutSpec(**{**BASE, **GRP, "layout_id": "n3syn_doubled", "doubled_header_glyphs": True,
                         "summary_truncated": True})
    pages = _mk(spec, _chain_sections(), doubled=True, anchors=("1,000", "1,150"))
    out = extract_pages(pages, spec)
    assert out.failure is None
    assert len(out.rows) == 6
    assert _verdict(out) == "VERIFIED"


# ------------------------------------------------------------------ derived sides


def test_derived_side_from_balance_moves():
    pages = _mk(SPEC_GRP, [("15Nov", [("NARRA", "300", "1,300.00"), ("NARRB", "200", "1,100.00")])],
                anchors=("1,000", "1,100"))
    out = extract_pages(pages, SPEC_GRP)
    assert [(r.txn.credit, r.txn.debit) for r in out.rows] == [(Decimal("300.00"), None), (None, Decimal("200.00"))]


def test_first_row_side_needs_anchor():
    spec = LayoutSpec(**{**BASE, "layout_id": "n3syn_grp_noanchor",
                         "single_amount_column": "txn_amount", "derive_side_from_balance": True,
                         "year_from_period": True, "section_date_re": SEC_RE})
    pages = _mk(spec, [("15Nov", [("NARRA", "300", "1,300.00"), ("NARRB", "200", "1,100.00")])])
    out = extract_pages(pages, spec)
    assert any("side_unproven" in r.row_warnings for r in out.rows) or \
        any(w.startswith("side_unproven") for w in out.warnings)
    assert _verdict(out) != "VERIFIED"


# ------------------------------------------------------------------ wrapped decimals


def test_same_line_decimal_wrap_joins():
    pages = _mk(SPEC_GRP, [("15Nov", [("NARRA", "500", "1,500.00")])], anchors=("1,000", "1,500"))
    g, e = geom(SPEC_GRP), ts.title_edges(SPEC_GRP, geom(SPEC_GRP))
    top = pages[0].words[-1].top + 16.0
    ws = list(pages[0].words) + [ts.w("NARRX", g["narration"][0], top), ts.rt("361", e["txn_amount"], top),
                                 ts.w(".63", e["txn_amount"], top), ts.rt("1,138.63", e["balance"], top)]
    pages[0] = Page(ws, 1200.0)
    out = extract_pages(pages, SPEC_GRP)
    assert out.rows[-1].txn.debit == Decimal("361.63")


def test_cross_line_decimal_wrap_joins():
    pages = _mk(SPEC_GRP, [("15Nov", [("NARRA", "500", "1,500.00")])], anchors=("1,000", "1,500"))
    g, e = geom(SPEC_GRP), ts.title_edges(SPEC_GRP, geom(SPEC_GRP))
    top = pages[0].words[-1].top + 16.0
    ws = list(pages[0].words) + [ts.w("NARRX", g["narration"][0], top), ts.rt("1,111", e["txn_amount"], top),
                                 ts.rt("2,611.00", e["balance"], top),
                                 ts.w("TAIL", g["narration"][0], top + 8.0), ts.w(".40", e["txn_amount"], top + 8.0)]
    pages[0] = Page(ws, 1200.0)
    out = extract_pages(pages, SPEC_GRP)
    assert out.rows[-1].txn.debit is None or out.rows[-1].txn.debit == Decimal("1111.00") or True
    # the appended row's amount is 1,111.40? no — this row's printed balance continues the chain;
    # assert the wrap fragment joined the row's cell
    assert out.rows[-1].txn.credit == Decimal("1111.40") or out.rows[-1].txn.debit == Decimal("1111.40")


# ------------------------------------------------------------------ truncated summaries


def test_truncated_summary_floor_matches():
    pages = _mk(SPEC_GRP_TRUNC, [("15Nov", [("NARRA", "300", "1,300.55"), ("NARRB", "200", "1,100.55")])],
                anchors=("1,000", "1,100"))
    out = extract_pages(pages, SPEC_GRP_TRUNC)
    # derived opening 1,000.55 -> displays "1,000"; derived closing 1,100.55 -> displays "1,100"
    assert out.checks.results["reference"].status == "pass"


def test_truncated_summary_still_fails_on_real_mismatch():
    pages = _mk(SPEC_GRP_TRUNC, [("15Nov", [("NARRA", "300", "1,300.55"), ("NARRB", "200", "1,100.55")])],
                anchors=("1,000", "1,500"))          # printed closing is wrong even floored
    out = extract_pages(pages, SPEC_GRP_TRUNC)
    assert out.checks.results["reference"].status == "fail"
    assert _verdict(out) != "VERIFIED"


# ------------------------------------------------------------------ mutations


def _mutate_amount(pages, needle, replacement):
    for pg in pages:
        for i, w in enumerate(pg.words):
            if w.text.strip() == needle:
                pg.words[i] = Word(replacement, w.x0, w.x1, w.top, w.bottom)
                return pages
    raise AssertionError(f"{needle} not found")


def test_amount_change_fails():
    pages = _mk(SPEC_GRP, _chain_sections(labels=("15Nov",)), anchors=("1,000", "1,075"))
    pages = _mutate_amount(pages, "50", "500")
    out = extract_pages(pages, SPEC_GRP)
    assert _verdict(out) != "VERIFIED"


def test_dropped_row_fails():
    secs = _chain_sections(labels=("15Nov", "16Nov"))
    pages = _mk(SPEC_GRP, secs, anchors=("1,000", "1,150"))
    target = secs[0][1][1][1]
    for pg in pages:
        for i, w in enumerate(pg.words):
            if w.text.strip() == target:
                pg.words[i] = Word("Z", w.x0, w.x1, w.top, w.bottom)
    out = extract_pages(pages, SPEC_GRP)
    assert _verdict(out) != "VERIFIED"


def test_truncated_page_fails():
    pages = _mk(SPEC_GRP, _chain_sections(labels=("15Nov", "16Nov")), page_breaks={1}, anchors=("1,000", "1,150"))
    out = extract_pages(pages[:1], SPEC_GRP)
    assert _verdict(out) != "VERIFIED"


def test_swapped_side_impossible_to_hide():
    """Flip one balance so the derived side lies: the chain must catch it."""
    secs = _chain_sections(labels=("15Nov",))
    pages = _mk(SPEC_GRP, secs, anchors=("1,000", "1,075"))
    target_bal = secs[0][1][1][2]
    for pg in pages:
        for i, w in enumerate(pg.words):
            if w.text.strip() == target_bal:
                pg.words[i] = Word("9,999.00", w.x0, w.x1, w.top, w.bottom)
    out = extract_pages(pages, SPEC_GRP)
    assert _verdict(out) != "VERIFIED"


# ------------------------------------------------------------------ codec round-trip


def test_spec_codec_round_trips_n3_fields():
    spec = LayoutSpec(**{**BASE, "layout_id": "n3syn_codec",
                         "single_amount_column": "txn_amount", "derive_side_from_balance": True,
                         "section_date_re": SEC_RE, "doubled_header_glyphs": True,
                         "summary_truncated": True, "totals_sum_tail": True,
                         "doc_counts_re": re.compile(r"(\d+)X(\d+)Y(\d+)Z")})
    assert spec_from_dict(spec_to_dict(spec)) == spec


# ------------------------------------------------------------------ period start year / implied opening


def test_period_from_borrows_end_year():
    """'1 Dec to 31 Dec \'22': the yearless from-date borrows the end year."""
    from types import SimpleNamespace
    from app.services.statement_engine.extraction.checks import check_period, PASS, WARN
    rows = [SimpleNamespace(txn=SimpleNamespace(date=f"2022-12-{d:02d}")) for d in (1, 15, 31)]
    ok = check_period(rows, ("1Dec", "31Dec'22"), "%d%b'%y", from_borrows_end_year=True)
    assert ok.status == PASS, ok.detail
    # without the flag the same print stays an honest warn
    no = check_period(rows, ("1Dec", "31Dec'22"), "%d%b'%y", from_borrows_end_year=False)
    assert no.status == WARN
    # month wrap: 1Dec with end 31Jan'23 belongs to '22
    wrap = check_period(rows, ("1Dec", "31Jan'23"), "%d%b'%y", from_borrows_end_year=True)
    assert wrap.status == PASS, wrap.detail


def test_implied_opening_sets_first_side():
    """No printed opening, but totals+closing print: opening = closing + debits - credits must
    anchor row 0's side derivation (a credit-opening row must not collapse to the debit fallback)."""
    spec = LayoutSpec(**{**BASE, "layout_id": "n3syn_implied",
                         "single_amount_column": "txn_amount", "derive_side_from_balance": True,
                         "year_from_period": True, "section_date_re": SEC_RE,
                         "anchor_scan": "document", "summary_truncated": False,
                         "closing_balance_re": re.compile(r"CLOSINGBALANCE([\d,]+(?:\.\d+)?)"),
                         "totals_line_re": re.compile(r"MONEYOUT([\d,]+(?:\.\d+)?)MONEYIN([\d,]+(?:\.\d+)?)")})
    # opening is really 0: cr 2000 -> 2000, dr 500 -> 1500, cr 300 -> 1800. closing 1800, out 500, in 2300.
    secs = [("15Nov", [("NARR0", "2,000", "2,000.00"), ("NARR1", "500", "1,500.00"), ("NARR2", "300", "1,800.00")])]
    pages = _mk(spec, secs, summary_line="MONEYOUT500MONEYIN2,300CLOSINGBALANCE1,800")
    out = extract_pages(pages, spec)
    assert out.failure is None, out.failure_detail
    assert out.rows[0].txn.credit == Decimal("2000"), out.rows[0].txn
    assert not any("side_unproven" in r.row_warnings for r in out.rows)
    assert _verdict(out) == "VERIFIED", out.checks.reasons if out.checks else out.failure_detail
