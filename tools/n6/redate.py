"""Recompute dated_amt_lines + rows_gt_dated_lines flag on existing h2h records
after the DATE/AMT_LINE regex fix in head2head.py. Rewrites <bank>.h2h.jsonl
in place (counts + flags only; chain/anchor results are unchanged)."""
import glob, json, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.services.statement_engine.extraction.pdf_extractor import read_pages
from app.services.statement_engine.extraction.words import group_lines

DATE = re.compile(r"^\d{0,4}\d{2}[-/.]\d{2}[-/.]\d{2,4}$|^\d{2}\s?-?\s?[A-Za-z]{3}\s?-?\s?\d{2,4}$")
AMT_LINE = re.compile(r"^-?[\d,]+(?:\.\d{1,2})?\s?\(?[cd]r\.?\)?$|^-?[\d,]+(?:\.\d{1,2})?$|^-?$|^-?[\d,]+$", re.I)


def dated_amount_lines(pages):
    n = 0
    for p in pages:
        for l in group_lines(p.words):
            toks = [w.text.strip() for w in l]
            if any(DATE.match(t) for t in toks[:3]) and sum(1 for t in toks if AMT_LINE.match(t)) >= 2:
                n += 1
    return n


local = os.path.join(os.path.dirname(__file__), ".local")
mani = {}
for mf in glob.glob(os.path.join(os.path.dirname(__file__), "..", "verify2", ".local", "manifest_*.jsonl")):
    for ln in open(mf, encoding="utf-8"):
        d = json.loads(ln)
        mani[d["sha8"]] = d["path"]

for bank in sys.argv[1:]:
    p = os.path.join(local, f"{bank}.h2h.jsonl")
    recs = [json.loads(l) for l in open(p, encoding="utf-8")]
    with open(p + ".new", "w", encoding="utf-8") as out:
        for r in recs:
            path = mani.get(r["sha8"])
            if path and "dated_amt_lines" in r:
                try:
                    dated = dated_amount_lines(read_pages(path))
                    r["dated_amt_lines"] = dated
                    for leg in ("leg", "v2"):
                        if isinstance(r.get(leg), dict) and "rows" in r[leg]:
                            fl = [f for f in r[leg].get("flags", []) if f != "rows_gt_dated_lines"]
                            if dated < r[leg]["rows"]:
                                fl.append("rows_gt_dated_lines")
                            r[leg]["flags"] = fl
                except Exception:
                    pass
            out.write(json.dumps(r) + "\n")
    os.replace(p + ".new", p)
    print(bank, "redated", len(recs))
