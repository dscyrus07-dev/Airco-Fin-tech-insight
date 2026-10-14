"""N2 engine capability tests: whole-document anchor scan, per-account segments,
balance-less tables (NO_RUNNING_BALANCE ceiling), printed balance checkpoints, and
inline balance continuation lines. Synthetic word-coordinate pages only — no PDFs,
no customer data. Every mutation must end below VERIFIED."""
import re
from decimal import Decimal
from typing import List

import pytest

from app.services.statement_engine.extraction.layout_spec import LayoutSpec
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extraction.engine import extract_pages
from app.services.statement_engine.extraction.words import Word

from tests.statement_engine.extraction.onboarded_kit import W  # noqa: F401

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../tools/onboarding"))
from synth import table_shapes as ts  # noqa: E402


def geom(spec, start=60.0, width=130.0):
    out, x = {}, start
    for col in spec.columns:
        out[col] = (x, width)
        x += width
    return out


BASE = dict(
    bank_key="n2syn", bank_name="N2 Synth",
    bank_markers=("N2SYNBANK",),
    columns={
        "date": (("date",),),
        "narration": (("narration",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit", credit_column="credit", balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"), date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    summary_marker="^$", summary_label_text="",
    period_re=re.compile(r"a^"), period_date_format="%d/%m/%Y",
    continuation_start="top",
    summary_expected=False,
)


def _spec(**over):
    d = dict(BASE)
    d.update(over)
    if "columns" in over and "balance_column" not in over:
        pass
    return LayoutSpec(**d)


SPEC_ANCHOR = _spec(
    layout_id="n2syn_anchor_doc",
    anchor_scan="document",
    anchor_full=True,
    opening_balance_re=re.compile(r"OPENINGBALANCE:?([\d,]+\.\d{2})"),
    closing_balance_re=re.compile(r"CLOSINGBALANCE:?([\d,]+\.\d{2})"),
)

SPEC_SEG = _spec(
    layout_id="n2syn_segments",
    anchor_scan="document",
    opening_balance_re=re.compile(r"(?i)^openingbalance:?([\d,]+\.\d{2})$"),
    closing_balance_re=re.compile(r"(?i)^closingbalance:?([\d,]+\.\d{2})$"),
    segment_header_re=re.compile(r"(?i)^accountno:\d+$"),
    segment_count_re=re.compile(r"(?i)totalnumberoftransactions:?(\d+)"),
)

SPEC_BALLESS = LayoutSpec(
    **{**BASE, "layout_id": "n2syn_balanceless", "no_running_balance": True, "balance_column": "",
       "columns": {k: v for k, v in BASE["columns"].items() if k != "balance"},
       "totals_line_re": re.compile(r"(?i)totaldebits:?([\d,]+\.\d{2})totalcredits:?([\d,]+\.\d{2})")})

SPEC_BALLESS_DELTA = LayoutSpec(
    **{**BASE, "layout_id": "n2syn_balanceless_delta", "no_running_balance": True, "balance_column": "",
       "columns": {k: v for k, v in BASE["columns"].items() if k != "balance"},
       "anchor_scan": "document",
       "opening_balance_re": re.compile(r"OPENINGBALANCE:?([\d,]+\.\d{2})"),
       "closing_balance_re": re.compile(r"CLOSINGBALANCE:?([\d,]+\.\d{2})")})

SPEC_CHECKPT = _spec(
    layout_id="n2syn_checkpoints",
    balance_checkpoint_re=re.compile(r"BALANCE(?:CARRIED|BROUGHT)FORWARD:?([\d,]+\.\d{2})"),
)

SPEC_INLINE = _spec(
    layout_id="n2syn_inline_balance",
    balance_inline_re=re.compile(r"(?i)^balance:?([\d,]+\.\d{2})$"),
)


def _chain_rows(n, start=500.0, amount=100.0, day0=1):
    rows = []
    bal = start
    for i in range(n):
        if i % 2:
            bal += amount
            rows.append((f"{day0 + i:02d}/01/2024", "NARR TXN", None, f"{amount:.2f}", f"{bal:,.2f}"))
        else:
            bal -= amount
            rows.append((f"{day0 + i:02d}/01/2024", "NARR TXN", f"{amount:.2f}", None, f"{bal:,.2f}"))
    return rows


def _verdict(out):
    return out.checks.verdict if out and out.checks else out.failure if out else "NO_OUTCOME"


# ---------------------------------------------------------------- whole-document anchors

def test_document_anchor_scan_verified():
    g = geom(SPEC_ANCHOR)
    ra = _chain_rows(3, start=500.0)                    # balances 400 / 500 / 400
    rb = _chain_rows(2, start=400.0, day0=4)            # continues: 300 / 400
    rc = _chain_rows(2, start=400.0, day0=6)            # 300 / 400
    pages = ts.mid_document_anchors(SPEC_ANCHOR, g, ra, rb, rc, opening="500.00", closing="400.00")
    out = extract_pages(pages, SPEC_ANCHOR)
    assert out.failure is None, out.failure_detail
    assert _verdict(out) == "VERIFIED", out.checks.reasons if out.checks else out.failure_detail
    assert out.summary is not None and out.summary.opening == Decimal("500.00") and out.summary.closing == Decimal("400.00")


def test_document_anchor_conflict_is_review():
    g = geom(SPEC_ANCHOR)
    pages = ts.mid_document_anchors(SPEC_ANCHOR, g, _chain_rows(3, start=500.0),
                                    _chain_rows(2, start=400.0, day0=4), _chain_rows(1, start=400.0, day0=6),
                                    opening="500.00", closing="400.00")
    # a second, different printed opening later in the document: never silently pick one
    pages[1].words.append(ts.w("OPENINGBALANCE", 30, 700.0))
    pages[1].words.append(ts.rt("999.00", 320, 700.0))
    out = extract_pages(pages, SPEC_ANCHOR)
    assert out.checks.verdict in ("REVIEW", "FAILED")
    assert any(w.startswith("anchor_conflict:opening") for w in out.warnings)
    assert any("conflicting printed anchor" in r for r in out.checks.reasons)


def test_document_anchor_off_by_default():
    """Without anchor_scan='document' a mid-document anchor is invisible (unchanged baseline)."""
    spec = _spec(layout_id="n2syn_anchor_off", anchor_full=True,
                 opening_balance_re=re.compile(r"OPENINGBALANCE:?([\d,]+\.\d{2})"),
                 closing_balance_re=re.compile(r"CLOSINGBALANCE:?([\d,]+\.\d{2})"))
    g = geom(spec)
    pages = ts.mid_document_anchors(spec, g, _chain_rows(3, start=500.0), _chain_rows(2, start=400.0, day0=4),
                                    _chain_rows(1, start=400.0, day0=6),
                                    opening="500.00", closing="400.00")
    out = extract_pages(pages, spec)
    assert out.failure is None
    assert out.checks.verdict == "REVIEW"            # self-derived chain, no anchors -> REVIEW cap


# ---------------------------------------------------------------- per-account segments

def test_segments_verified_with_ids():
    g = geom(SPEC_SEG)
    pages = ts.segmented_statement(SPEC_SEG, g, [
        {"header": "ACCOUNTNO:1001", "count": 3, "rows": _chain_rows(3, start=500.0)},
        {"header": "ACCOUNTNO:2002", "count": 2, "rows": _chain_rows(2, start=40.0)},
    ], anchors=("500.00", "40.00"))
    out = extract_pages(pages, SPEC_SEG)
    assert out.checks.verdict == "VERIFIED", out.checks.reasons
    segs = [r.txn.extras.get("segment") for r in out.rows]
    assert segs == [0, 0, 0, 1, 1]          # first account precedes the anchors-bounded header line -> segment 0
    assert out.checks.results["segments"].status == "pass"


def test_segment_count_mismatch_review():
    g = geom(SPEC_SEG)
    pages = ts.segmented_statement(SPEC_SEG, g, [
        {"header": "ACCOUNTNO:1001", "count": 3, "rows": _chain_rows(3)},
        {"header": "ACCOUNTNO:2002", "count": 5, "rows": _chain_rows(2)},   # printed 5, read 2
    ])
    out = extract_pages(pages, SPEC_SEG)
    assert out.checks.verdict != "VERIFIED"
    assert out.checks.results["segments"].status in ("warn", "fail")
    assert any("segment" in r.lower() for r in out.checks.reasons)


def test_segment_chain_break_names_segment():
    g = geom(SPEC_SEG)
    bad = _chain_rows(2, start=40.0)
    bad[1] = (bad[1][0], bad[1][1], bad[1][2], "12,345.00", bad[1][4])   # same balance -> break
    pages = ts.segmented_statement(SPEC_SEG, g, [
        {"header": "ACCOUNTNO:1001", "count": 3, "rows": _chain_rows(3)},
        {"header": "ACCOUNTNO:2002", "count": 2, "rows": bad},
    ])
    out = extract_pages(pages, SPEC_SEG)
    assert out.checks.verdict == "FAILED"
    assert out.checks.results["chain"].detail.get("segments") == [1]


def test_single_segment_field_absent():
    g = geom(SPEC_SEG)
    pages = ts.segmented_statement(SPEC_SEG, g, [
        {"header": "ACCOUNTNO:1001", "count": 3, "rows": _chain_rows(3)},
    ])
    out = extract_pages(pages, SPEC_SEG)
    assert all("segment" not in r.txn.extras for r in out.rows)


# ---------------------------------------------------------------- balance-less tables

def test_balanceless_review_ceiling():
    g = geom(SPEC_BALLESS)
    rows = [("01/01/2024", "NARR TXN", "100.00", None), ("02/01/2024", "NARR TXN", None, "150.00")]
    pages = ts.balanceless_statement(SPEC_BALLESS, g, rows)
    out = extract_pages(pages, SPEC_BALLESS)
    assert out.failure is None
    assert out.checks.verdict == "REVIEW"
    assert any("NO_RUNNING_BALANCE" in r for r in out.checks.reasons)
    assert out.checks.results["chain"].status == "skipped"
    assert all(r.txn.balance is None for r in out.rows)
    assert all(r.txn.extras.get("no_running_balance") for r in out.rows)


def test_balanceless_totals_reconcile_review():
    g = geom(SPEC_BALLESS)
    rows = [("01/01/2024", "NARR TXN", "100.00", None), ("02/01/2024", "NARR TXN", None, "150.00")]
    pages = ts.balanceless_statement(SPEC_BALLESS, g, rows,
                                     totals=("2", "100.00", "150.00"))
    # printed totals reconcile -> still REVIEW (never VERIFIED for balance-less)
    out = extract_pages(pages, SPEC_BALLESS)
    assert out.checks.verdict == "REVIEW"
    assert out.checks.results["totals"].status == "pass"


def test_balanceless_delta_fail():
    g = geom(SPEC_BALLESS_DELTA)
    rows = [("01/01/2024", "NARR TXN", "100.00", None), ("02/01/2024", "NARR TXN", None, "150.00")]
    pages = ts.balanceless_statement(SPEC_BALLESS_DELTA, g, rows)
    pages[0].words += [ts.w("OPENINGBALANCE", 30, 700.0), ts.rt("500.00", 320, 700.0)]
    pages[0].words += [ts.w("CLOSINGBALANCE", 30, 716.0), ts.rt("999.00", 320, 716.0)]  # net +50 vs printed +499
    out = extract_pages(pages, SPEC_BALLESS_DELTA)
    assert out.checks.verdict == "FAILED"
    assert out.checks.results["balance_delta"].status == "fail"


def test_balanceless_delta_pass_still_review():
    g = geom(SPEC_BALLESS_DELTA)
    rows = [("01/01/2024", "NARR TXN", "100.00", None), ("02/01/2024", "NARR TXN", None, "150.00")]
    pages = ts.balanceless_statement(SPEC_BALLESS_DELTA, g, rows)
    pages[0].words += [ts.w("OPENINGBALANCE", 30, 700.0), ts.rt("500.00", 320, 700.0)]
    pages[0].words += [ts.w("CLOSINGBALANCE", 30, 716.0), ts.rt("550.00", 320, 716.0)]  # +50 correct
    out = extract_pages(pages, SPEC_BALLESS_DELTA)
    assert out.checks.results["balance_delta"].status == "pass"
    assert out.checks.verdict == "REVIEW" and any("NO_RUNNING_BALANCE" in r for r in out.checks.reasons)


def test_balanceless_never_verified_mutations():
    g = geom(SPEC_BALLESS)
    rows = [("0%d/01/2024" % (i + 1), "NARR TXN", f"{100 + i}.00" if i % 2 == 0 else None,
             None if i % 2 == 0 else f"{90 + i}.00") for i in range(4)]
    for mut in (
        lambda p: [w for w in p[0].words if not (w.top > 240.0 and w.top < 256.0)],       # drop row
        lambda p: [Word("9,999.00", w.x0, w.x1, w.top, w.bottom) if w.text == "100.00" and w.top > 240 else w
                   for w in p[0].words],                                                  # changed amount
        lambda p: p[:1],                                                                  # drop nothing (page kept)
    ):
        pages = ts.balanceless_statement(SPEC_BALLESS, g, rows)
        mut(pages)
        out = extract_pages(pages, SPEC_BALLESS)
        assert out.checks.verdict != "VERIFIED"


# ---------------------------------------------------------------- printed balance checkpoints

def _rows4(rows):
    return [(d, n, dr, cr) for d, n, dr, cr, _b in rows]


def test_checkpoints_pass():
    g = geom(SPEC_CHECKPT)
    rows_all = _chain_rows(4, start=0.0)       # balances -100 / 0 / -100 / 0
    pages = ts.checkpoint_statement(SPEC_CHECKPT, g, [
        ("0.00", rows_all[:2]),                # page 1 ends "CARRIED FORWARD 0.00"
        (rows_all[1][4], rows_all[2:]),        # page 2 opens "BROUGHT FORWARD 0.00"
    ])
    out = extract_pages(pages, SPEC_CHECKPT)
    assert out.checks.results["checkpoints"].status == "pass"
    assert out.checks.results["checkpoints"].detail["verified"] >= 2


def test_checkpoint_mismatch_fails():
    g = geom(SPEC_CHECKPT)
    rows_all = _chain_rows(4, start=0.0)
    pages = ts.checkpoint_statement(SPEC_CHECKPT, g, [
        ("0.00", rows_all[:2]),
        ("9,999.00", rows_all[2:]),           # printed B/F contradicts the running balance
    ])
    out = extract_pages(pages, SPEC_CHECKPT)
    assert out.checks.results["checkpoints"].status == "fail"
    assert out.checks.verdict == "FAILED"


def test_checkpoints_balanceless_delta():
    spec = _spec(layout_id="n2syn_checkpt_bl", no_running_balance=True, balance_column="",
                 columns={k: v for k, v in BASE["columns"].items() if k != "balance"},
                 balance_checkpoint_re=re.compile(r"BALANCE(?:CARRIED|BROUGHT)FORWARD:?([\d,]+\.\d{2})"))
    g = geom(spec)
    seg_a = [("01/01/2024", "NARR TXN", "100.00", None), ("02/01/2024", "NARR TXN", None, "150.00")]   # +50
    seg_b = [("03/01/2024", "NARR TXN", "60.00", None), ("04/01/2024", "NARR TXN", None, "10.00")]     # -50
    seg_c = [("05/01/2024", "NARR TXN", None, "5.00")]                                                 # +5
    pages = ts.checkpoint_statement(spec, g, [("0.00", seg_a), ("50.00", seg_b), ("0.00", seg_c)])
    out = extract_pages(pages, spec)
    res = out.checks.results["checkpoints"]
    assert res.status == "pass", res.detail          # delta 0->50 over seg_a, 50->0 over seg_b verified
    assert res.detail["verified"] >= 1
    assert out.checks.verdict == "REVIEW"            # still balance-less: REVIEW ceiling


def test_checkpoints_balanceless_delta_mismatch_fails():
    spec = _spec(layout_id="n2syn_checkpt_bl2", no_running_balance=True, balance_column="",
                 columns={k: v for k, v in BASE["columns"].items() if k != "balance"},
                 balance_checkpoint_re=re.compile(r"BALANCE(?:CARRIED|BROUGHT)FORWARD:?([\d,]+\.\d{2})"))
    g = geom(spec)
    seg_a = [("01/01/2024", "NARR TXN", "100.00", None), ("02/01/2024", "NARR TXN", None, "150.00")]
    seg_b = [("03/01/2024", "NARR TXN", "60.00", None)]
    seg_c = [("05/01/2024", "NARR TXN", None, "5.00")]
    pages = ts.checkpoint_statement(spec, g, [("0.00", seg_a), ("55.00", seg_b), ("0.00", seg_c)])
    out = extract_pages(pages, spec)
    assert out.checks.results["checkpoints"].status == "fail"   # printed delta contradicts the rows
    assert out.checks.verdict == "FAILED"


# ---------------------------------------------------------------- inline balance continuation

def test_inline_balance_attach():
    g = geom(SPEC_INLINE)
    pages = ts.inline_balance_statement(SPEC_INLINE, g, _chain_rows(3))
    out = extract_pages(pages, SPEC_INLINE)
    assert out.failure is None
    assert all(r.txn.balance is not None for r in out.rows)
    assert out.checks.results["chain"].status == "pass"


def test_inline_balance_wrong_breaks_chain():
    g = geom(SPEC_INLINE)
    bad = _chain_rows(3)
    bad[2] = (bad[2][0], bad[2][1], bad[2][2], bad[2][3], "1.00")
    pages = ts.inline_balance_statement(SPEC_INLINE, g, bad)
    out = extract_pages(pages, SPEC_INLINE)
    assert out.checks.results["chain"].status == "fail"
    assert out.checks.verdict == "FAILED"


# ---------------------------------------------------------------- mutation battery across shapes

def _mut_drop_row(pages):
    ts_drop = sorted({w.top for w in pages[0].words})
    mid = ts_drop[len(ts_drop) // 2]
    pages[0].words = [w for w in pages[0].words if abs(w.top - mid) > 1.0]
    return pages


def _mut_swap_sides(pages):
    """Swap a money word's x into the neighbouring column band on the first data row."""
    tops = sorted({w.top for w in pages[0].words})
    mid = [t for t in tops if t > 230.0][0]
    ws = list(pages[0].words)
    idx = [i for i, w in enumerate(ws) if abs(w.top - mid) < 1.0 and re.match(r"^[\d,]+\.\d{2}$", w.text)]
    if len(idx) >= 2:
        a, b = idx[-2], idx[-1]
        ws[a] = Word(ws[a].text, ws[b].x0, ws[b].x1, ws[a].top, ws[a].bottom)
        ws[b] = Word(ws[b].text, ws[a].x0, ws[a].x1, ws[b].top, ws[b].bottom)
        pages[0].words = ws
    return pages


def _mut_change_amount(pages):
    tops = sorted({w.top for w in pages[0].words})
    mid = [t for t in tops if t > 230.0][0]
    ws = list(pages[0].words)
    for i, w in enumerate(ws):
        if abs(w.top - mid) < 1.0 and re.match(r"^[\d,]+\.\d{2}$", w.text):
            ws[i] = Word("9,999.00", w.x0, w.x1, w.top, w.bottom)
            break
    pages[0].words = ws
    return pages


def _mut_missing_page(pages):
    return pages[:1]


def _mut_truncate(pages):
    tops = sorted({w.top for w in pages[0].words})
    pages[0].words = [w for w in pages[0].words if w.top <= tops[-2]]
    return pages


@pytest.mark.parametrize("mut", [_mut_drop_row, _mut_swap_sides, _mut_change_amount,
                                 _mut_missing_page, _mut_truncate])
def test_mutation_battery_segmented(mut):
    g = geom(SPEC_SEG)
    pages = ts.segmented_statement(SPEC_SEG, g, [
        {"header": "ACCOUNTNO:1001", "count": 4, "rows": _chain_rows(4)},
        {"header": "ACCOUNTNO:2002", "count": 2, "rows": _chain_rows(2, start=40.0)},
    ])
    mut(pages)
    out = extract_pages(pages, SPEC_SEG)
    assert _verdict(out) != "VERIFIED"


@pytest.mark.parametrize("mut", [_mut_drop_row, _mut_change_amount, _mut_truncate])
def test_mutation_battery_inline(mut):
    g = geom(SPEC_INLINE)
    pages = ts.inline_balance_statement(SPEC_INLINE, g, _chain_rows(5))
    mut(pages)
    out = extract_pages(pages, SPEC_INLINE)
    assert _verdict(out) != "VERIFIED"
