# gen_onboard_test.py — emit tests/statement_engine/extraction/test_onboard_<id>.py
# usage: python gen_onboard_test.py <bank_id> <SPEC_CONST> <pkg> "MARKER WORDS" "ifsc" [date_sample]
import os, sys

HERE = os.path.dirname(__file__)
TESTDIR = os.path.abspath(os.path.join(HERE, "..", "..", "backend", "tests",
                                        "statement_engine", "extraction"))

bid, spec_const, pkg = sys.argv[1], sys.argv[2], sys.argv[3]
marker = sys.argv[4].split() if len(sys.argv) > 4 else ["BANK"]
ifsc = sys.argv[5] if len(sys.argv) > 5 else "XXXX0000000"
display = sys.argv[6] if len(sys.argv) > 6 else bid.replace("_", " ").title()
use_bk = len(sys.argv) > 7 and sys.argv[7] == "bankkey"
BKARG = f', bank_key="{bid}"' if use_bk else ""

mk = ", ".join(f'w("{m}", {30 + i * 70}, 40)' for i, m in enumerate(marker))
mk = "MARKER = [" + mk + "]"

TPL = '''"""Synthetic layout tests for {display} ({bid}). Pages built from word
coordinates; no PDFs, no customer data."""
from app.services.statement_engine import Confidence, detect_bank
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.extractors.{pkg}.layout_spec import {spec_const} as SPEC
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, header, row, rt, w

{mk}


def _rows():
    return [
        row(SPEC, 220, "UPIREF1234", debit="100.00", balance="900.00"),
        row(SPEC, 236, "NEFTSALARY5678", credit="1,000.00", balance="1,900.00"),
        row(SPEC, 252, "ATMCASH", debit="400.00", balance="1,500.00"),
    ]


def _page(rows, marker=True, extra=None):
    ws = list(MARKER if marker else [])
    if extra:
        ws += extra
    ws += header(SPEC)
    for r in rows:
        ws += r
    return [Page(ws, W)]


def test_{bid}_rows_parse_and_chain():
    r = route_pages(_page(_rows()), DEFAULT_REGISTRY{BKARG})
    assert r.status == "v2" and r.layout_id == SPEC.layout_id
    txns = r.result.transactions
    assert len(txns) == 3
    assert [str(t.balance) for t in txns] == ["900.00", "1900.00", "1500.00"]


def test_{bid}_detected_by_detector():
    text = "{display}\\nAccount Statement\\nIFSC: {ifsc}\\n" \\
           "Date Narration Withdrawal Deposit Balance\\n" \\
           "05 Jan 2024 UPI REF 100.00 900.00\\n" * 3
    det = detect_bank([text])
    assert det.bank_id == "{det_id}" and det.confidence.name in ("HIGH", "VERY_HIGH", "MEDIUM")


def test_{bid}_foreign_marker_refused():
    foreign = [w("HDFC", 30, 40), w("BANK", 60, 40), w("HDFC0001234", 30, 56)]
    r = route_pages(_page(_rows(), marker=False, extra=foreign), DEFAULT_REGISTRY{BKARG})
    assert not (r.status == "v2" and r.layout_id == SPEC.layout_id)


def test_{bid}_narration_with_other_bank_still_{bid}():
    rows = [row(SPEC, 220, "NEFTTOHDFCBANKLTD", debit="100.00", balance="900.00"),
            row(SPEC, 236, "IMPSICICIPAYOUT", credit="1,000.00", balance="1,900.00"),
            row(SPEC, 252, "AXISBANKREFUND", debit="400.00", balance="1,500.00")]
    r = route_pages(_page(rows), DEFAULT_REGISTRY{BKARG})
    assert r.status == "v2" and r.layout_id == SPEC.layout_id


def test_{bid}_unread_dated_line_caps_at_review():
    rows = _rows()
    pgs = _page(rows)
    pgs[0].words += [w("06-01-2024", 30, 400), w("DATEDLINE", 140, 400),
                     rt("50.00", 490, 400), rt("1,450.00", 570, 400)]
    r = route_pages(pgs, DEFAULT_REGISTRY{BKARG})
    if r.status == "v2":
        extras = r.result.metadata.extras
        assert extras.get("verdict") != "VERIFIED" or \\
            any("unread" in str(x) for x in extras.get("warnings", []))
'''

det_id = {"scb": "standard_chartered", "bom": "bank_of_maharashtra",
          "equitas": "equitas_sfb", "ujjivan": "ujjivan_sfb"}.get(pkg, bid)

out = TPL.format(bid=bid, spec_const=spec_const, pkg=pkg, mk=mk,
                 ifsc=ifsc, display=display, det_id=det_id, BKARG=BKARG)
path = os.path.join(TESTDIR, f"test_onboard_{bid}.py")
open(path, "w", encoding="utf-8").write(out)
print("wrote", path)
