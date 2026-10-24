"""T3 universal reader unit tests.

Synthetic PDFs only — no corpus dependency. Covers: REVIEW cap (never
VERIFIED), T0 failure codes, non-statement refusal, meta hygiene (no PII),
and the serve-block shape.
"""
from __future__ import annotations

import io

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.services.statement_engine.universal import reader as univ
from app.services.statement_engine.universal import serve as userv


def _pdf(lines_per_page, path):
    """Render lines as (x, y, text) triples; one list per page."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for page in lines_per_page:
        for x, y, text in page:
            c.drawString(x, y, text)
        c.showPage()
    c.save()
    path.write_bytes(buf.getvalue())
    return str(path)


def _statement_pages(n_rows=12, header=("Date", "Particulars", "Debit", "Credit", "Balance")):
    """Simple headered statement: dd-Mon-yyyy dates, dr/cr cols, balance chain."""
    pages = []
    rows = [
        (50, 780, "Date"), (140, 780, "Particulars"), (330, 780, "Debit"),
        (410, 780, "Credit"), (490, 780, "Balance"),
    ]
    bal = 10000.0
    y = 750
    for i in range(n_rows):
        day = f"{i + 1:02d}-Jan-2024"
        is_debit = i % 3 == 0
        amt = 100.0 * (i + 1)
        bal += -amt if is_debit else amt
        rows.append((50, y, day))
        rows.append((140, y, f"NARRATION {i:03d}"))
        rows.append((330 if is_debit else 410, y, f"{amt:,.2f}"))
        rows.append((490, y, f"{bal:,.2f}"))
        y -= 20
        if y < 100:
            pages.append(rows)
            rows = [(50, 780, t) for t in header]
            y = 750
    pages.append(rows)
    return pages


def test_review_cap_never_verified(tmp_path):
    p = _pdf(_statement_pages(), tmp_path / "stmt.pdf")
    res = univ.read(p, bank_hint="Test Bank")
    assert res.verdict == "REVIEW"
    assert res.code == univ.GENERAL_READER
    assert res.meta.get("rows", 0) > 0
    # Even a clean checks pass is capped — never VERIFIED.
    assert res.verdict != "VERIFIED"


def test_no_text_layer(tmp_path):
    p = _pdf([[]], tmp_path / "blank.pdf")
    res = univ.read(p)
    assert res.verdict == "FAILED"
    assert res.code == univ.NO_TEXT_LAYER


def test_glyph_dump(tmp_path):
    page = [(50, 780 - i * 20, f"(cid:{100 + i}) (cid:{200 + i}) (cid:{300 + i}) (cid:{i})") for i in range(30)]
    p = _pdf([page], tmp_path / "glyph.pdf")
    res = univ.read(p)
    assert res.verdict == "FAILED"
    assert res.code == univ.GLYPH_DUMP


def test_non_statement_fails(tmp_path):
    page = [(50, 780 - i * 20, f"the quick brown fox jumps over the lazy dog {i} lorem ipsum dolor") for i in range(30)]
    p = _pdf([page], tmp_path / "prose.pdf")
    res = univ.read(p)
    assert res.verdict == "FAILED"
    assert res.code != ""


def test_page_cap(tmp_path):
    pages = _statement_pages(3) * 41  # >120 pages
    p = _pdf(pages, tmp_path / "huge.pdf")
    res = univ.read(p, max_pages=10)
    assert res.verdict == "FAILED"
    assert res.code == univ.TOO_MANY_PAGES


def test_meta_has_no_statement_content(tmp_path):
    p = _pdf(_statement_pages(), tmp_path / "stmt.pdf")
    res = univ.read(p)
    blob = str(res.meta) + str(res.notes) + res.detail
    assert "NARRATION" not in blob
    for k in ("pages", "rows"):
        assert k in res.meta


def test_reader_never_raises(tmp_path):
    # garbage bytes, not a PDF
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"\x00\x01\x02 not a pdf \xff" * 100)
    res = univ.read(str(bad))
    assert res.verdict == "FAILED"


def test_serve_block_shape(tmp_path):
    p = _pdf(_statement_pages(), tmp_path / "stmt.pdf")
    res = univ.read(p, bank_hint="Test Bank")
    block = userv.block_for(res, served=True, u_mode="serve")
    assert block["engine"] == "universal"
    assert block["tier"] == "T3"
    assert block["needs_review"] is True
    assert "GENERAL_READER" in block["review_codes"]
    eng = userv.engine_block_for(res, "serve", detected_bank=None)
    assert eng["engine"] == "universal"
    assert eng["verdict"] == "REVIEW"
    assert eng["needs_review"] is True


def test_failed_result_no_rows_served(tmp_path):
    p = _pdf([[]], tmp_path / "blank.pdf")
    res = univ.read(p)
    assert res.ok is False
    block = userv.block_for(res, served=False, u_mode="serve")
    assert block["served"] is False


# ---- single amount column whose bare cells carry no printed side -------------------------------------

def _signed_single_amount_pdf(path, n=14, unsigned_side="credit"):
    """A statement printing one money column: debits carry a '-', credits print bare (or the reverse).

    The bare cells state no side of their own, so the reading has to be proved against the balances.
    """
    from decimal import Decimal
    bal = Decimal("50000.00")
    signed_side = "debit" if unsigned_side == "credit" else "credit"
    sign = "-" if signed_side == "debit" else "+"
    head = [(40, 760, "Date"), (130, 760, "Narration"), (390, 760, "Amount"), (500, 760, "Balance")]
    rows, y = [], 740
    for i in range(n):
        amt = Decimal(500 + i * 137) + Decimal("0.25")
        bare = (i % 3 == 1)                                # most rows signed, the rest bare
        side = unsigned_side if bare else signed_side
        bal = bal - amt if side == "debit" else bal + amt
        printed = f"{amt:,.2f}" if bare else f"{sign}{amt:,.2f}"
        rows += [(40, y, f"{(i % 28) + 1:02d}/04/2026"), (130, y, f"NEFT TXN {i}"),
                 (430 - len(printed) * 6.7, y, printed), (500, y, f"{bal:,.2f}")]
        y -= 16
    return _pdf([head + rows], path)


def test_bare_cells_in_a_single_amount_column_are_read_by_proving_the_side(tmp_path):
    """Previously every bare row was dropped ('amount cell carries no Dr/Cr marker') and the statement
    reconciled on only the signed half."""
    res = univ.read(_signed_single_amount_pdf(tmp_path / "s.pdf"), bank_hint="Unknown bank")
    assert res.verdict == "REVIEW", f"{res.code}: {res.detail}"
    assert len(res.outcome.rows) == 14                      # not just the signed ones
    assert any(n.startswith("single_amount_default_side:") for n in res.notes)


def test_the_proved_side_follows_the_balances_not_a_default(tmp_path):
    """Flip which side the bare cells carry; the reading must follow the arithmetic."""
    out = {}
    for side in ("credit", "debit"):
        res = univ.read(_signed_single_amount_pdf(tmp_path / f"{side}.pdf", unsigned_side=side),
                        bank_hint="Unknown bank")
        note = [n for n in res.notes if n.startswith("single_amount_default_side:")]
        out[side] = note[0].split(":")[1] if note else None
    assert out["credit"] == "credit" and out["debit"] == "debit", out


def test_an_unprovable_side_is_still_refused(tmp_path):
    """Balances that fit neither reading must not be rescued by picking one."""
    from decimal import Decimal
    head = [(40, 760, "Date"), (130, 760, "Narration"), (390, 760, "Amount"), (500, 760, "Balance")]
    rows, y = [], 740
    for i in range(12):                                     # balances unrelated to the amounts
        rows += [(40, y, f"{i + 1:02d}/04/2026"), (130, y, f"NEFT TXN {i}"),
                 (370, y, f"{500 + i * 37}.25"), (500, y, f"{Decimal(90000 + i * 11):,.2f}")]
        y -= 16
    res = univ.read(_pdf([head + rows], tmp_path / "bad.pdf"), bank_hint="Unknown bank")
    assert res.verdict == "FAILED"
