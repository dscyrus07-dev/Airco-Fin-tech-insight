"""The real-scan harness: its tiers and break classes, and that NOTHING it writes can carry statement content."""
import json
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(__file__))
import real_scan_eval as R  # noqa: E402

from app.services.statement_engine.ocr.contracts import OcrDocument, document_to_dict  # noqa: E402
from tests.statement_engine.ocr import synthetic as syn  # noqa: E402
from tests.statement_engine.ocr.test_ocr_line_layer import _lines  # noqa: E402


def _both_readers_doc(seed=3):
    """One page the way a real ocr call returns it: VL table markup AND line boxes, for the same rows."""
    doc, rows = syn.make_document(n_rows=26, per_page=26, seed=seed)
    doc.pages[0].lines = _lines(rows)
    return doc, rows


def _cache(tmp, docs):
    os.makedirs(tmp, exist_ok=True)
    with open(os.path.join(tmp, "index.jsonl"), "w") as idx:
        for i, (bank, doc) in enumerate(docs):
            sha = f"{i:02d}" + "ab" * 31
            with open(os.path.join(tmp, sha + ".json"), "w") as fh:
                json.dump(document_to_dict(doc), fh)
            idx.write(json.dumps({"sha256": sha, "sha8": sha[:8], "bank": bank, "pages": 1, "ocr_s": 6.0,
                                  "status": "cached"}) + "\n")


def test_tiers_and_cross_validation(tmp_path):
    good, _ = _both_readers_doc()
    empty = OcrDocument(pages=[], engine="x", verifier="", dpi=200)
    _cache(str(tmp_path / "c"), [("SBI", good), ("Other_Unknown", empty)])
    class A: cache = str(tmp_path / "c"); out = str(tmp_path / "o"); budget_s = 0; fresh = True
    R.cmd_eval(A)
    docs = {d["bank"]: d for d in map(json.loads, open(tmp_path / "o" / "docs.jsonl"))}
    sbi = docs["SBI"]
    assert sbi["layers"]["blocks"]["served"] and sbi["layers"]["lines"]["served"]
    assert sbi["cross"]["agree"] == 26 and sbi["cross"].get("side_disagree", 0) == 0
    assert sbi["tier"] in ("A+", "A")
    assert docs["Other_Unknown"]["tier"] == "R"
    rep = json.load(open(tmp_path / "o" / "report.json"))
    assert rep["documents"] == 2 and rep["cross_validation"]["documents_read_by_both"] == 1


def test_nothing_written_carries_statement_content(tmp_path):
    """Plant recognisable narrations, amounts and dates; none may appear in any output file."""
    doc, rows = _both_readers_doc(seed=11)
    _cache(str(tmp_path / "c"), [("HDFC Bank", doc)])
    class A: cache = str(tmp_path / "c"); out = str(tmp_path / "o"); budget_s = 0; fresh = True
    R.cmd_eval(A)
    blob = "".join(open(tmp_path / "o" / f).read() for f in ("docs.jsonl", "report.json", "report.md"))
    leaks = []
    for r in rows:
        for v in (r["dr"], r["cr"], r["bal"]):
            if v is not None and (syn._fmt(v) in blob or str(v) in blob):
                leaks.append("amount")
        if r["date"].strftime("%d/%m/%Y") in blob or r["date"].isoformat() in blob:
            leaks.append("date")
        for word in r["narr"].replace("/", " ").split():
            if len(word) > 4 and not word.isdigit() and word.lower() in blob.lower():
                leaks.append(f"narration:{word}")
        if r["ref"] in blob:
            leaks.append("ref")
    assert not leaks, sorted(set(leaks))


def test_break_classes():
    D = Decimal
    def rows(*triples):
        return [{"date": f"d{i}", "debit": d, "credit": c, "balance": b} for i, (d, c, b) in enumerate(triples)]
    ok = rows((None, None, D("1000.00")), (D("100.00"), None, D("900.00")), (None, D("50.00"), D("950.00")))
    assert sum(R.classify_breaks(ok).values()) == 0
    flip = rows((None, None, D("1000.00")), (None, D("100.00"), D("900.00")))
    assert R.classify_breaks(flip) == {"side_flip": 1}
    digit = rows((None, None, D("1000.00")), (D("180.00"), None, D("900.00")))          # 100.00 read as 180.00
    assert R.classify_breaks(digit) == {"amount_digit_misread": 1}
    dropped = rows((None, None, D("10000.00")), (D("150.00"), None, D("8500.00")))      # 1500.00 read as 150.00
    assert R.classify_breaks(dropped) in ({"amount_digit_dropped_or_extra": 1}, {"amount_decimal_shift": 1})


def test_round_robin_covers_every_bank_first(tmp_path):
    for bank, n in (("A", 3), ("B", 1), ("C", 2)):
        d = tmp_path / bank / "OCR"
        d.mkdir(parents=True)
        for i in range(n):
            (d / f"{i}.pdf").write_bytes(b"%PDF")
    order = [b for b, _ in R.iter_scans(str(tmp_path))]
    assert order[:3] == ["A", "B", "C"] and len(order) == 6
