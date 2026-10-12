"""Re-measure u3a records whose univ verdict was REVIEW and whose row set
differed from the registered-layout baseline (or whole folders hit by the
single-amount first-row fix). Writes u3a_fix.jsonl alongside u3a.jsonl.
Usage: python tools/u3_remeasure.py u3a.jsonl u3a_fix.jsonl
"""
import hashlib
import json
import sys
from multiprocessing import Pool
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
CORPUS = ROOT.parent / "Unified All Statements"
sys.path.insert(0, str(BACKEND))


def sha8(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()[:8]


def _find(folder: str, sha: str) -> Path | None:
    d = CORPUS / folder
    for f in sorted(d.glob("*.pdf")):
        if sha8(f) == sha:
            return f
    return None


def _run_one(path: str) -> dict:
    from app.services.statement_engine.universal import reader as univ
    from app.services.statement_engine.extraction.engine import extract_pages  # noqa
    p = Path(path)
    try:
        u = univ.read(str(p))
        rec = {"sha": sha8(p), "verdict": u.verdict, "code": u.code,
               "pre_cap": u.meta.get("checks_verdict"), "rows": u.meta.get("rows", 0)}
        if u.outcome is not None:
            def _k(t):
                txn = t.txn
                return (str(txn.date),
                        str(txn.debit) if txn.debit is not None else None,
                        str(txn.credit) if txn.credit is not None else None,
                        str(txn.balance))
            rec["row_keys"] = [_k(t) for t in u.outcome.rows]
        return rec
    except Exception as exc:
        return {"sha": sha8(p), "verdict": "FAILED", "code": "CRASH", "detail": type(exc).__name__}


def main():
    src, outp = Path(sys.argv[1]), Path(sys.argv[2])
    recs = [json.loads(l) for l in src.open(encoding="utf-8")]
    want = []
    for r in recs:
        u = r["univ"]
        if u.get("verdict") != "REVIEW":
            continue
        differ = r.get("base_rows") and u.get("row_keys") and r["base_rows"] != u["row_keys"]
        if differ or r["folder"] in ("Paytm Payments Bank", "Paytm Bank", "Kotak Mahindra Bank", "Kotak Bank"):
            want.append(r)
    print(f"{len(want)} files to re-measure")
    paths = []
    for r in want:
        p = _find(r["folder"], r["sha"])
        if p:
            paths.append(str(p))
    print(f"{len(paths)} resolved")
    out = outp.open("w", encoding="utf-8")
    with Pool(3) as pool:
        for rec in pool.imap_unordered(_run_one, paths, chunksize=2):
            out.write(json.dumps(rec, default=str) + "\n")
            out.flush()
    print("done")


if __name__ == "__main__":
    main()
