"""Mis-read OCR structure must produce an honest refusal, never a crash and never a shifted amount.

Regression cover for the three bugs the first real-GPU run hit (docs/ocr/R6_DEVIN_REPORT.md):
  F11  a header naming one money side plus a bare "Amount" made the inference declare a column it had never
       located -> KeyError deep in the engine -> ENGINE_ERROR on every statement.
  F13  the LOW_CONFIDENCE_COLUMNS message formatted None with :.2f -> TypeError, hiding the real code.
  F10  the recogniser omits empty cells, so a short row's cells sit one column left: an amount would be read
       under the wrong heading. Such rows must be left out and counted, never re-placed by guesswork.
"""
from __future__ import annotations

from app.services.statement_engine.ocr.contracts import OcrBlock, OcrDocument, OcrLine, OcrPage
from app.services.statement_engine.ocr.grid import pages_from_ocr
from app.services.statement_engine.ocr.reader import OCR_TABLE_ROWS_DROPPED, read_document

from . import synthetic as syn

FULL = ("Date", "Narration", "Chq./Ref.No.", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance")


def _doc(header=FULL, rows=None, drop_empty_on=()):
    rows = rows if rows is not None else syn.make_rows(26)
    out = ["<table>", "<tr>" + "".join(f"<th>{c}</th>" for c in header) + "</tr>"]
    for i, r in enumerate(rows):
        cells = [r["date"].strftime("%d/%m/%Y"), r["narr"], r["ref"],
                 syn._fmt(r["dr"]), syn._fmt(r["cr"]), syn._fmt(r["bal"])]
        if drop_empty_on == "all" or i in drop_empty_on:
            cells = [c for c in cells if c != ""]           # the recogniser omits the empty money cell
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    blocks = [OcrBlock("header", [40, 30, 900, 60], "SAMPLE COOPERATIVE BANK LTD"),
              OcrBlock("text", [40, 70, 900, 120],
                       f"Statement of account from {rows[0]['date']:%d/%m/%Y} to {rows[-1]['date']:%d/%m/%Y}"),
              OcrBlock("table", [40, 140, 1600, 1900], "".join(out + ["</table>"]))]
    lines = [OcrLine(syn._fmt(v), [0, 0, 10, 10], 0.99)
             for r in rows for v in (r["dr"], r["cr"], r["bal"]) if v is not None]
    return OcrDocument(pages=[OcrPage(page=1, width=1654, height=2339, blocks=blocks, lines=lines, elapsed_s=1.0)],
                       engine="test", verifier="test", dpi=200), rows


def test_well_formed_table_still_reads():
    doc, rows = _doc()
    res = read_document(doc)
    assert res.verdict == "REVIEW" and res.ok
    assert res.to_block()["rows"] == len(rows)
    assert res.to_block()["rows_dropped_total"] == 0


def test_one_money_side_plus_bare_amount_is_refused_not_crashed():
    """F11: was ENGINE_ERROR / KeyError 'credit'."""
    for header in (("Date", "Narration", "Chq./Ref.No.", "Withdrawal", "Amount", "Closing Balance"),
                   ("Date", "Narration", "Chq./Ref.No.", "Debit", "Amount", "Closing Balance"),
                   ("Date", "Narration", "Chq./Ref.No.", "Amount", "Deposit Amt.", "Closing Balance")):
        res = read_document(_doc(header)[0])
        assert res.verdict == "FAILED"
        assert res.code == "AMBIGUOUS_MONEY_COLUMNS", f"{header} -> {res.code}"
        assert "ENGINE_ERROR" not in res.code and "KeyError" not in (res.detail or "")


def test_refusal_names_the_header_titles_it_read():
    """Without the real titles a header mis-read cannot be diagnosed from a report."""
    res = read_document(_doc(("Date", "Narration", "Chq./Ref.No.", "Withdrawal", "Amount", "Closing Balance"))[0])
    titles = res.universal.meta.get("header_titles", "")
    assert "debit:withdrawal" in titles and "amount:amount" in titles


def test_empty_money_header_cell_reports_a_code_not_a_typeerror():
    """F13: the failure message itself used to crash, reporting INFER_ERROR/TypeError."""
    res = read_document(_doc(("Date", "Narration", "Chq./Ref.No.", "Withdrawal Amt.", "", "Closing Balance"))[0])
    assert res.verdict == "FAILED"
    assert res.code == "LOW_CONFIDENCE_COLUMNS" and "TypeError" not in (res.detail or "")
    assert "n/a" in res.detail            # formats cleanly when there is no margin to report


def test_inferred_spec_never_declares_an_unlocated_column():
    """The backstop: LayoutSpec.validate() runs on every inferred spec."""
    from app.services.statement_engine.ocr.grid import pages_from_ocr as _p
    from app.services.statement_engine.universal import infer as _i
    for header in (FULL, ("Date", "Narration", "Chq./Ref.No.", "Withdrawal", "Amount", "Closing Balance")):
        inf = _i.infer(_p(_doc(header)[0].pages))
        if inf.spec is not None:
            inf.spec.validate()           # must not raise
            assert all(c in inf.spec.columns for c in inf.spec.amount_columns)


def test_short_row_is_left_out_and_counted_not_shifted():
    """F10: a dropped empty cell shifts every later cell, so the row must not be placed at all."""
    doc, rows = _doc(drop_empty_on=(7,))
    res = read_document(doc)
    block = res.to_block()
    assert block["rows_dropped_total"] == 1 and block["rows_dropped"] == {"1": 1}
    assert OCR_TABLE_ROWS_DROPPED in res.review_codes
    assert block["rows"] == len(rows) - 1          # the shifted row is absent, not mis-placed
    assert res.verdict == "FAILED"                 # a missing transaction must break the balance chain


def test_every_row_short_keeps_the_header_and_refuses():
    """The majority shape is the broken one here: the header still states the true column count."""
    doc, rows = _doc(drop_empty_on="all")
    res = read_document(doc)
    assert res.to_block()["rows_dropped_total"] == len(rows)
    assert res.verdict == "FAILED" and res.ok is False


def test_dropped_rows_are_reported_per_source_page():
    doc, _ = _doc(drop_empty_on=(3, 9))
    dropped = {}
    pages_from_ocr(doc.pages, dropped)
    assert dropped == {1: 2}


# ---- cross-page column alignment (real Axis scan: page 1 had 7 columns, every later page 6) ---------------------
from app.services.statement_engine.ocr.grid import align_to_reference, _profile  # noqa: E402

HEAD7 = ["Tran Date", "Chq No", "Particulars", "Debit", "Credit", "Balance", "Init. Br"]


def _ref7(n=12):
    """The header table: Chq No present but empty on every row, as printed."""
    rows = [HEAD7]
    for i in range(n):
        dr, cr = ("120.50", "") if i % 3 else ("", "2,000.00")
        rows.append([f"{i + 1:02d}-04-2026", "", f"UPI/P2A/{100000 + i}/x", dr, cr, f"{5000 + i * 10}.25", "1234"])
    return _profile(rows[1:], 7)


def test_a_table_that_lost_its_empty_column_is_realigned():
    cont = [[f"{i + 1:02d}-05-2026", f"UPI/P2A/{200000 + i}/x", "75.00" if i % 2 else "", "" if i % 2 else "900.00",
             f"{6000 + i}.75", "1234"] for i in range(10)]
    out, moved = align_to_reference(cont, _ref7())
    assert moved
    assert out[0][1] == "" and out[0][2].startswith("UPI")             # the empty Chq No column is back in place
    assert out[1][3] == "75.00" and out[0][4] == "900.00"              # debits under Debit, credits under Credit
    assert out[0][5].endswith(".75") and out[0][6] == "1234"           # balance under Balance, branch under Branch


def test_a_page_that_could_have_lost_either_money_column_is_left_alone():
    """Debits only on this page AND no empty column in the header table: Debit or Credit could be the one missing.
    Two placements fit equally, so neither is chosen — the chain refuses the page instead of money moving sides."""
    rows = [["Date", "Particulars", "Debit", "Credit", "Balance"]]
    for i in range(12):
        dr, cr = ("120.50", "") if i % 2 else ("", "300.00")
        rows.append([f"{i + 1:02d}-04-2026", "NEFT X", dr, cr, f"{5000 + i}.25"])
    ref = _profile(rows[1:], 5)
    debits_only = [[f"{i + 1:02d}-05-2026", "NEFT Y", "75.00", f"{6000 + i}.75"] for i in range(10)]
    out, moved = align_to_reference(debits_only, ref)
    assert not moved and out is debits_only


def test_full_width_and_header_tables_are_never_touched():
    full = [[f"{i + 1:02d}-05-2026", "", "UPI", "1.00", "", "9.00", "1"] for i in range(5)]
    assert align_to_reference(full, _ref7()) == (full, False)
    head = [HEAD7[:6]] + [[f"{i + 1:02d}-05-2026", "UPI", "1.00", "", "9.00", "1"] for i in range(5)]
    assert align_to_reference(head, _ref7())[1] is False
