"""Per-job OCR reading (thorough | fast) and the honesty rules that come with it."""
from __future__ import annotations

from app.services.statement_engine.ocr import client as ocr_client
from app.services.statement_engine.ocr import serve as oserve
from app.services.statement_engine.ocr.contracts import OcrDocument
from app.services.statement_engine.ocr.grid import page_text
from app.services.statement_engine.ocr.reader import read_document
from app.services.statement_engine.ocr.verify import NOT_RUN

from . import synthetic as syn
from .test_ocr_line_layer import _doc as lines_doc


def test_reading_choice_and_default(monkeypatch):
    monkeypatch.delenv("STATEMENT_ENGINE_OCR_TEXT_LAYER", raising=False)
    assert oserve.reading_for("fast") == "fast" and oserve.reading_for("THOROUGH") == "thorough"
    assert oserve.reading_for(None) == "thorough" and oserve.reading_for("bogus") == "thorough"
    monkeypatch.setenv("STATEMENT_ENGINE_OCR_TEXT_LAYER", "lines")
    assert oserve.reading_for(None) == "fast"            # the deployment default follows the text layer


def _capture(monkeypatch, doc):
    seen = {}
    def fake(pdf_path, pages=None, **kw):
        seen.update(kw)
        return doc
    monkeypatch.setattr(ocr_client, "ocr_pdf", fake)
    return seen


def test_fast_reading_skips_the_vl_model_and_reads_the_lines(monkeypatch):
    rows = syn.make_rows(26)
    seen = _capture(monkeypatch, lines_doc(rows, with_blocks=False))
    res, rs = oserve.attempt("x.pdf", reading="fast")
    assert seen["vl"] is False and res.layer == "lines" and res.reading == "fast"
    assert res.ok and rs is not None


def test_thorough_reading_runs_the_vl_model_and_reads_the_markup(monkeypatch):
    doc, _ = syn.make_document()
    seen = _capture(monkeypatch, doc)
    res, _rs = oserve.attempt("x.pdf", reading="thorough")
    assert seen["vl"] is True and res.layer == "blocks" and res.reading == "thorough"


def test_lines_layer_never_claims_a_second_reading():
    """The rows came FROM the lines; checking them against the same lines would 'confirm' every amount."""
    res = read_document(lines_doc(syn.make_rows(26), with_blocks=False), layer="lines")
    assert res.ok
    assert res.verification.status == "not_run" and res.verification.confirmed == 0
    assert NOT_RUN in res.review_codes


def test_markup_layer_still_runs_the_independent_check():
    doc, _ = syn.make_document()
    res = read_document(doc, layer="blocks")
    assert res.verification.status == "ran" and res.verification.confirmed > 0


def test_thorough_on_a_lines_only_service_reads_the_lines_and_says_why():
    res = read_document(lines_doc(syn.make_rows(26), with_blocks=False), layer="blocks")
    assert res.layer == "lines" and res.layer_note == "VL_UNAVAILABLE" and res.ok
    assert res.to_block()["layer_note"] == "VL_UNAVAILABLE"


def test_catalog_is_off_unless_scans_will_really_be_processed(monkeypatch, tmp_path):
    monkeypatch.delenv("STATEMENT_ENGINE_OCR_MODE", raising=False)
    assert oserve.catalog_info()["enabled"] is False
    monkeypatch.setenv("STATEMENT_ENGINE_OCR_MODE", "shadow")
    monkeypatch.setenv("STATEMENT_ENGINE_OCR_URL", f"mock:{tmp_path}")
    assert oserve.catalog_info()["enabled"] is False      # shadow never serves a scan
    monkeypatch.setenv("STATEMENT_ENGINE_OCR_MODE", "serve")
    info = oserve.catalog_info()
    assert info["enabled"] is True and info["reading_modes"] == ["thorough", "fast"]
    assert info["default_reading"] == "thorough" and info["max_pages"] == ocr_client.max_pages()


def test_detection_text_comes_from_the_lines_when_there_is_no_markup():
    doc = lines_doc(syn.make_rows(6), with_blocks=False)
    text = page_text(doc.pages[0])
    assert "Withdrawal" in text and "Closing Balance" in text


def test_mock_fast_reading_answers_like_the_service(monkeypatch, tmp_path):
    import hashlib, json
    from app.services.statement_engine.ocr.contracts import document_to_dict
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    doc, _ = syn.make_document()
    (tmp_path / (hashlib.sha256(pdf.read_bytes()).hexdigest() + ".json")).write_text(json.dumps(document_to_dict(doc)))
    monkeypatch.setenv("STATEMENT_ENGINE_OCR_URL", f"mock:{tmp_path}")
    fast = ocr_client.ocr_pdf(str(pdf), vl=False)
    assert all(not p.blocks for p in fast.pages) and fast.verifier == ""
    full = ocr_client.ocr_pdf(str(pdf), vl=True)
    assert any(p.blocks for p in full.pages)
