"""T4 OCR: contracts, HTML grid, guards, verifier, reader policy. No model, no GPU, no network."""
from decimal import Decimal

import pytest

from app.services.statement_engine.ocr import client as ocr_client
from app.services.statement_engine.ocr.contracts import (
    OcrBlock, OcrLine, OcrPage, document_from_dict, document_to_dict, PAGE_FAILED)
from app.services.statement_engine.ocr.grid import page_from_ocr, page_text, pages_from_ocr
from app.services.statement_engine.ocr.guards import OCR_EMPTY, OCR_LOOP, apply_guards, compression_ratio
from app.services.statement_engine.ocr.html_table import parse_tables
from app.services.statement_engine.ocr.reader import (
    OCR_PARTIAL_PAGES, OCR_READER, OCR_UNCONFIRMED_AMOUNTS, read_document)
from app.services.statement_engine.ocr.verify import verify_rows
from tests.statement_engine.ocr.synthetic import make_document


def _amounts(res):
    return [(x.txn.debit, x.txn.credit, x.txn.balance) for x in res.universal.outcome.rows]


def test_html_table_spans_are_expanded_without_duplicating_values():
    g = parse_tables("<table><tr><th>A</th><th colspan=2>B</th></tr><tr><td rowspan=2>1</td><td>2</td><td>3</td></tr>"
                     "<tr><td>4</td><td>5</td></tr></table>")[0]
    assert g[0] == ["A", "B", ""]
    assert g[1] == ["1", "2", "3"]
    assert g[2] == ["", "4", "5"]          # rowspan cell is not repeated


def test_html_table_ignores_nested_tables_and_garbage():
    assert parse_tables("not html") == []
    g = parse_tables("<table><tr><td>x<table><tr><td>inner</td></tr></table></td><td>y</td></tr></table>")
    assert len(g) == 1 and g[0][0][1] == "y"


def test_grid_text_is_never_altered():
    p = OcrPage(page=1, blocks=[OcrBlock("table", [0, 0, 1, 1], "<table><tr><td>1,234.50</td><td>UPI/A B/C</td></tr></table>")])
    words = page_from_ocr(p).words
    assert [w.text for w in words] == ["1,234.50", "UPI/A", "B/C"]
    assert "1,234.50" in page_text(p)


def test_synthetic_statement_roundtrips_through_the_real_engine_and_checks():
    doc, rows = make_document(n_rows=24, per_page=12)
    res = read_document(doc)
    assert res.verdict == "REVIEW" and res.code == OCR_READER and res.ok
    got = _amounts(res)
    assert len(got) == len(rows)
    for (dr, cr, bal), r in zip(got, rows):
        assert Decimal(str(bal)) == r["bal"]
        assert (dr is not None and Decimal(str(dr)) == r["dr"]) or (cr is not None and Decimal(str(cr)) == r["cr"])
    assert res.universal.meta["checks_verdict"] == "VERIFIED"      # pre-cap
    assert res.review_codes[0] == OCR_READER and res.verification.status == "ran"
    assert res.verification.unconfirmed == 0 and res.verification.rows_flagged == 0


def test_ocr_result_is_never_verified_even_when_every_check_passes():
    doc, _ = make_document()
    res = read_document(doc)
    assert res.verdict != "VERIFIED" and res.to_block()["anchored"] is False
    assert res.to_block()["needs_review"] is True and res.to_block()["pre_cap_verdict"] == "VERIFIED"


def test_row_provenance_keeps_the_source_page():
    doc, _ = make_document(n_rows=24, per_page=12)
    res = read_document(doc)
    pages = {x.txn.extras["source_page"] for x in res.universal.outcome.rows}
    assert pages == {1, 2} and all(x.txn.extras["extraction"] == "ocr" for x in res.universal.outcome.rows)


def test_single_signed_amount_column_is_supported():
    from tests.statement_engine.ocr.synthetic import make_rows, table_html
    rows = make_rows(16)
    blocks = [OcrBlock("text", [0, 0, 1, 1], f"Statement from {rows[0]['date']:%d/%m/%Y} to {rows[-1]['date']:%d/%m/%Y}"),
              OcrBlock("table", [0, 0, 1, 1], table_html(rows, columns=("Date", "Details", "Ref", "Amount", "Balance"), single_signed=True))]
    doc = document_from_dict({"engine": "x", "pages": [{"page": 1, "blocks": [
        {"label": b.label, "bbox": list(b.bbox), "content": b.content} for b in blocks]}]})
    res = read_document(doc)
    if res.ok:                                   # accepted only if the engine proved the chain; never mis-signed
        for (dr, cr, bal), r in zip(_amounts(res), rows):
            assert Decimal(str(bal)) == r["bal"]
            assert (dr is not None and Decimal(str(dr)) == r["dr"]) or (cr is not None and Decimal(str(cr)) == r["cr"])
    else:
        assert res.verdict == "FAILED"           # honest failure, never wrong rows


def test_repetition_loop_page_is_failed_not_repaired():
    doc, _ = make_document(n_rows=24, per_page=12)
    doc.pages[1].blocks = [OcrBlock("text", [0, 0, 1, 1], "TOTAL 12,345.00 " * 400)]
    assert compression_ratio(doc.pages[1].blocks[0].content) > 4
    res = read_document(doc)
    assert res.failed_pages == {2: OCR_LOOP} and res.partial
    assert OCR_PARTIAL_PAGES in res.review_codes or not res.ok


def test_empty_page_is_failed():
    doc, _ = make_document()
    doc.pages[0].blocks = []
    assert apply_guards(doc) == [1] and doc.pages[0].error == OCR_EMPTY and doc.pages[0].status == PAGE_FAILED


def test_partial_statement_never_looks_complete():
    doc, rows = make_document(n_rows=36, per_page=12)
    doc.pages[1].status, doc.pages[1].error, doc.pages[1].blocks = PAGE_FAILED, "OCR_TIMEOUT", []
    res = read_document(doc)
    assert res.partial and res.failed_pages == {2: "OCR_TIMEOUT"}
    if res.ok:
        assert OCR_PARTIAL_PAGES in res.review_codes and res.to_block()["partial"] is True
        assert len(res.universal.outcome.rows) < len(rows)          # the gap is not hidden
    else:
        assert res.verdict == "FAILED"                              # the existing checks caught the gap


def test_all_pages_failed_is_failed_with_no_data():
    doc, _ = make_document()
    for p in doc.pages:
        p.status, p.error = PAGE_FAILED, "OCR_TIMEOUT"
    res = read_document(doc)
    assert res.verdict == "FAILED" and not res.ok and res.code == "OCR_NO_USABLE_PAGES"


def test_request_level_error_is_failed_with_its_code():
    from app.services.statement_engine.ocr.contracts import OcrDocument
    res = read_document(OcrDocument(error="OCR_SERVICE_UNAVAILABLE"))
    assert res.verdict == "FAILED" and res.code == "OCR_SERVICE_UNAVAILABLE"


def test_verifier_flags_an_amount_the_second_reader_disagrees_with():
    doc, _ = make_document(n_rows=12, per_page=12)
    page = doc.pages[0]
    # the verifier read one balance differently (a misread digit): that row must be flagged, not corrected
    for i, ln in enumerate(page.lines):
        if i == 5:
            page.lines[i] = OcrLine("9,999.99", ln.box, 0.99)
    res = read_document(doc)
    assert res.verification.unconfirmed >= 1 and res.verification.rows_flagged >= 1
    assert OCR_UNCONFIRMED_AMOUNTS in res.review_codes
    flagged = [x for x in res.universal.outcome.rows if x.txn.extras.get("ocr_flags")]
    assert flagged and all("OCR_AMOUNT_UNCONFIRMED" in x.txn.extras["ocr_flags"] for x in flagged)


def test_low_score_lines_do_not_confirm_an_amount():
    rep = verify_rows([(1, [Decimal("10.00")])], [OcrPage(page=1, lines=[OcrLine("10.00", [0, 0, 1, 1], 0.40)])])
    assert rep.low_confidence == 1 and rep.confirmed == 0


def test_verifier_absence_is_reported_not_assumed():
    doc, _ = make_document(with_lines=False)
    res = read_document(doc)
    assert res.verification.status == "not_run" and "OCR_VERIFIER_NOT_RUN" in res.review_codes


def test_scores_are_never_invented():
    d = document_from_dict({"pages": [{"page": 1, "lines": [{"text": "1.00", "box": [0, 0, 1, 1]}]}]})
    assert d.pages[0].lines == []


def test_contract_roundtrip():
    doc, _ = make_document()
    again = document_from_dict(document_to_dict(doc))
    assert len(again.pages) == len(doc.pages) and again.engine == doc.engine
    assert again.pages[0].blocks[0].content == doc.pages[0].blocks[0].content


def test_client_unconfigured_and_unreachable_never_raise(monkeypatch, tmp_path):
    f = tmp_path / "a.pdf"; f.write_bytes(b"%PDF-1.4 x")
    monkeypatch.delenv("STATEMENT_ENGINE_OCR_URL", raising=False)
    assert ocr_client.ocr_pdf(str(f)).error == "OCR_UNCONFIGURED"
    monkeypatch.setenv("STATEMENT_ENGINE_OCR_URL", "http://127.0.0.1:9")
    assert ocr_client.ocr_pdf(str(f), [1], timeout_s=1).error in ("OCR_SERVICE_UNAVAILABLE", "OCR_TIMEOUT")
    assert ocr_client.health(0.5) is False


def test_client_page_cap(monkeypatch, tmp_path):
    f = tmp_path / "a.pdf"; f.write_bytes(b"%PDF-1.4 x")
    monkeypatch.setenv("STATEMENT_ENGINE_OCR_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("STATEMENT_ENGINE_OCR_MAX_PAGES", "3")
    assert ocr_client.ocr_pdf(str(f), page_count=10).error == "OCR_TOO_MANY_PAGES"


def test_mock_fixture_service(monkeypatch, tmp_path):
    import json
    from app.services.statement_engine.ocr.client import _sha256
    f = tmp_path / "a.pdf"; f.write_bytes(b"%PDF-1.4 fixture")
    doc, _ = make_document()
    (tmp_path / f"{_sha256(str(f))}.json").write_text(json.dumps(document_to_dict(doc)))
    monkeypatch.setenv("STATEMENT_ENGINE_OCR_URL", f"mock:{tmp_path}")
    got = ocr_client.ocr_pdf(str(f), [1])
    assert [p.page for p in got.pages] == [1]
    g = tmp_path / "b.pdf"; g.write_bytes(b"%PDF-1.4 other")
    assert ocr_client.ocr_pdf(str(g)).error == "OCR_NO_FIXTURE"        # never fabricates output


def test_mode_defaults_off(monkeypatch):
    from app.services.statement_engine.ocr import serve as s
    monkeypatch.delenv("STATEMENT_ENGINE_OCR_MODE", raising=False)
    assert s.mode() == "off" and not s.enabled() and not s.wants("SCANNED")
    monkeypatch.setenv("STATEMENT_ENGINE_OCR_MODE", "serve")
    monkeypatch.delenv("STATEMENT_ENGINE_OCR_URL", raising=False)
    assert not s.wants("SCANNED")                                      # mode alone is not enough: needs a service
    monkeypatch.setenv("STATEMENT_ENGINE_OCR_URL", "http://x:1")
    assert s.wants("SCANNED") and s.wants("MIXED") and not s.wants("TEXT")
