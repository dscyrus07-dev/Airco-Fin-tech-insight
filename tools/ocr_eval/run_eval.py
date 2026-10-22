"""Run the OCR tier over the synthetic scan corpus and score it. Reports per quality category.

    # real service (or mock:<dir>)
    PYTHONPATH=backend python tools/ocr_eval/run_eval.py --corpus <dir> --url http://localhost:8090 --out <dir>/report
    # scorer/pipeline self-check without any model: the 'oracle' returns the ground truth as perfect OCR output
    PYTHONPATH=backend python tools/ocr_eval/run_eval.py --corpus <dir> --oracle [--perturb-side 1]

Everything here is synthetic (no real statement is read). Results do not change the REVIEW cap.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(__file__))
import scoring  # noqa: E402


def _oracle_doc(entry, perturb_side: int):
    from app.services.statement_engine.ocr.contracts import OcrBlock, OcrDocument, OcrLine, OcrPage
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend", "tests", "statement_engine", "ocr"))
    import synthetic as syn
    rows = []
    for r in entry["rows"]:
        rows.append({"date": date.fromisoformat(r["date"]), "narr": r["narr"], "ref": r["ref"],
                     "dr": Decimal(r["debit"]) if r["debit"] else None, "cr": Decimal(r["credit"]) if r["credit"] else None,
                     "bal": Decimal(r["balance"])})
    flipped = 0
    for r in rows:                                   # deliberate side swap: proves the scorer sees it
        if flipped < perturb_side and r["dr"] is not None:
            r["dr"], r["cr"] = None, r["dr"]
            flipped += 1
    per = 22
    pages = []
    for pi, chunk in enumerate([rows[i:i + per] for i in range(0, len(rows), per)]):
        blocks = []
        if pi == 0:
            blocks.append(OcrBlock("header", [40, 30, 900, 60], "SAMPLE COOPERATIVE BANK LTD"))
            blocks.append(OcrBlock("text", [40, 70, 900, 120],
                                   f"Statement of account from {rows[0]['date']:%d/%m/%Y} to {rows[-1]['date']:%d/%m/%Y}\n"
                                   f"Opening Balance {syn._fmt(Decimal(entry['opening']))}"))
        blocks.append(OcrBlock("table", [40, 140, 1600, 1900], syn.table_html(chunk)))
        lines = [OcrLine(syn._fmt(v), [0, 0, 10, 10], 0.99) for r in chunk for v in (r["dr"], r["cr"], r["bal"]) if v is not None]
        pages.append(OcrPage(page=pi + 1, width=1654, height=2339, blocks=blocks, lines=lines, elapsed_s=0.5))
    return OcrDocument(pages=pages, engine="oracle", verifier="oracle", dpi=entry["dpi"])


def run_one(entry, corpus, use_oracle, perturb):
    from app.services.statement_engine.ocr import client
    from app.services.statement_engine.ocr.reader import read_document
    path = os.path.join(corpus, entry["pdf"])
    doc = _oracle_doc(entry, perturb) if use_oracle else client.ocr_pdf(path, None, verify=True, page_count=entry["pages"])
    res = read_document(doc, bank_hint="Unknown bank")
    ext = []
    if res.universal and res.universal.outcome:
        for nr in res.universal.outcome.rows:
            t = nr.txn
            ext.append({"date": t.date, "debit": t.debit, "credit": t.credit, "balance": t.balance})
    cr = (res.universal.meta.get("check_results") if res.universal else None) or {}
    item = scoring.score_statement(entry["rows"], ext)
    item.update(id=entry["id"], category=entry["category"], served=res.ok, verdict=res.verdict, code=res.code,
                pre_cap=(res.universal.meta.get("checks_verdict") if res.universal else None),
                chain_pass=cr.get("chain") == "pass", reference_pass=cr.get("reference") == "pass",
                page_seconds=[p.elapsed_s for p in doc.pages if p.elapsed_s], failed_pages=len(res.failed_pages),
                review_codes=list(res.review_codes))
    return item


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--url", default="")
    ap.add_argument("--oracle", action="store_true")
    ap.add_argument("--perturb-side", type=int, default=0)
    ap.add_argument("--categories", default="")
    ap.add_argument("--limit", type=int, default=0, help="statements per category (0 = all)")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    if not a.oracle:
        if not a.url:
            sys.exit("give --url (service or mock:<dir>) or --oracle")
        os.environ["STATEMENT_ENGINE_OCR_URL"] = a.url
    man = json.load(open(os.path.join(a.corpus, "manifest.json")))["statements"]
    want = set(filter(None, a.categories.split(",")))
    seen, items = {}, []
    for e in man:
        if want and e["category"] not in want:
            continue
        if a.limit and seen.get(e["category"], 0) >= a.limit:
            continue
        seen[e["category"]] = seen.get(e["category"], 0) + 1
        items.append(run_one(e, a.corpus, a.oracle, a.perturb_side))
    cats = sorted({i["category"] for i in items})
    report = {"synthetic": True, "oracle": a.oracle, "gates": scoring.GATES, "categories": {}}
    for c in cats:
        agg = scoring.aggregate([i for i in items if i["category"] == c])
        report["categories"][c] = {"aggregate": agg, "gates": scoring.gate_report(agg, c == "clean_200")}
    report["overall"] = scoring.aggregate(items)
    report["statements"] = [{k: v for k, v in i.items() if k != "page_seconds"} for i in items]
    md = ["# OCR evaluation (SYNTHETIC scans)" + (" - ORACLE SELF-CHECK, not a model result" if a.oracle else ""), "",
          "| category | n | served | exact amounts | side flips | invented (chain-pass) | chain+ref pass | p95 s/page |",
          "|---|---|---|---|---|---|---|---|"]
    f = lambda v, p=1: "n/a" if v is None else f"{v*100:.{p}f}%"
    sec = lambda v: "n/a" if v is None else f"{v:.1f}"
    for c in cats:
        g = report["categories"][c]["aggregate"]
        md.append(f"| {c} | {g['statements']} | {g['served']} | {f(g['exact_amount_rate'],2)} | {g['side_flips']} | "
                  f"{g['invented_in_chain_passing']} | {f(g['chain_and_reference_pass_rate'],0)} | {sec(g['seconds_per_page_p95'])} |")
    md += ["", "Targets are release gates, not proven capabilities. Passing them would not lift the REVIEW cap."]
    print("\n".join(md))
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        json.dump(report, open(os.path.join(a.out, "report.json"), "w"), indent=1, default=str)
        open(os.path.join(a.out, "report.md"), "w").write("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
