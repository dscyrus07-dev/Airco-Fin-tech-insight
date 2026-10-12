"""U3 measurement: run the universal (T3) reader over the readable corpus and
compare against registered-layout baselines. Resumable: each output line is one
file; reruns skip shas already recorded.

Usage:
    python -m tools.u3_measure a          # accuracy set (phase6 base_verified)
    python -m tools.u3_measure b          # reach set (unhandled folders/files)
    python -m tools.u3_measure d          # negative set (non-statements)
    python -m tools.u3_measure a b d      # everything

Outputs: comparison/universal/u3<set>.jsonl (untracked). No PII: sha8 + folder
+ metrics only.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repo root (wt-univ)
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
CORPUS = ROOT.parent / "Unified All Statements"
OUTDIR = ROOT / "comparison" / "universal"
BASE_VERIFIED = ROOT.parent / "comparison" / "phase6" / "base_verified.jsonl"
if not BASE_VERIFIED.exists():
    BASE_VERIFIED = ROOT / "comparison" / "phase6" / "base_verified.jsonl"

WORKERS = 3
SHA_LEN = 8


def _sha8(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:SHA_LEN]


def _folder_bank_map() -> dict:
    """corpus folder -> bank id from banks/*.json."""
    out = {}
    banks_dir = BACKEND / "app" / "services" / "statement_engine" / "banks"
    for fp in banks_dir.glob("*.json"):
        if fp.name == "_masks.json":
            continue
        try:
            rec = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        folder = rec.get("corpus_folder")
        if folder:
            out[folder] = rec.get("id", "")
    return out


def _row_key(t) -> tuple:
    return (t.date,
            str(t.debit) if t.debit is not None else None,
            str(t.credit) if t.credit is not None else None,
            str(t.balance) if t.balance is not None else None)


def _compare(base_rows, mine_rows) -> dict:
    """Ordered row compare. Returns exact-match flag + multiset precision/recall."""
    b = [_row_key(t) for t in base_rows]
    m = [_row_key(t) for t in mine_rows]
    exact = b == m
    cb, cm = Counter(b), Counter(m)
    overlap = sum((cb & cm).values())
    prec = overlap / len(m) if m else 0.0
    rec = overlap / len(b) if b else 0.0
    first_diff = next((i for i, (x, y) in enumerate(zip(b, m)) if x != y), None)
    if first_diff is None and len(b) != len(m):
        first_diff = min(len(b), len(m))
    return {"exact": exact, "base_rows": len(b), "mine_rows": len(m),
            "row_precision": round(prec, 4), "row_recall": round(rec, 4),
            "first_diff": first_diff}


def _process(args) -> dict:
    """Worker: one file -> baseline rows (if requested) + universal result."""
    path_str, bank_key, want_baseline = args
    path = Path(path_str)
    rec = {"key": hashlib.sha256(path_str.encode()).hexdigest()[:16],
           "folder": path.parent.name}
    try:
        rec["sha"] = _sha8(path)
    except Exception as exc:
        rec["error"] = f"hash:{type(exc).__name__}"
        return rec

    from app.services.statement_engine.extraction.pdf_extractor import read_pages
    from app.services.statement_engine.extraction.engine import extract_pages
    from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
    from app.services.statement_engine.universal import reader as univ

    try:
        pages = read_pages(str(path))
    except Exception as exc:
        rec["error"] = f"read:{type(exc).__name__}"
        rec["univ"] = {"verdict": "FAILED", "code": "LOCKED" if "assword" in str(exc) else "READ_ERROR"}
        return rec
    rec["pages"] = len(pages)

    if want_baseline:
        try:
            res = DEFAULT_REGISTRY.resolve(pages, bank_key)
            rec["base_resolve"] = res.status
            rec["base_evidence"] = res.bank_evidence
            if res.spec is not None:
                rec["layout"] = res.spec.layout_id
                out = extract_pages(pages, res.spec)
                rec["base_verdict"] = out.checks.verdict if out.checks else ("FAILED" if out.failure else "VERIFIED")
                rec["base_rows"] = [_row_key(t.txn) for t in out.rows]
            else:
                rec["base_verdict"] = "NO_LAYOUT"
                rec["base_rows"] = []
        except Exception as exc:
            rec["base_verdict"] = "ERROR"
            rec["base_err"] = type(exc).__name__
            rec["base_rows"] = []

    try:
        u = univ.read(bank_hint=bank_key or "Unknown bank", pages=pages)
        rec["univ"] = {"verdict": u.verdict, "code": u.code,
                       "pre_cap": u.meta.get("checks_verdict"),
                       "rows": u.meta.get("rows", 0),
                       "elapsed": round(u.elapsed_s, 2),
                       "infer": {k: u.meta.get(k) for k in
                                 ("header", "money", "date_shape", "amount_form", "confidence", "margin")
                                 if u.meta.get(k) is not None},
                       "detail": u.detail[:200]}
        if u.outcome is not None:
            rec["univ"]["row_keys"] = [_row_key(t.txn) for t in u.outcome.rows]
    except Exception as exc:
        rec["univ"] = {"verdict": "FAILED", "code": "CRASH", "detail": type(exc).__name__}
    return rec


def _done_keys(out: Path) -> set:
    done = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["key"])
            except Exception:
                pass
    return done


def _key(path: Path) -> str:
    return hashlib.sha256(str(path).encode()).hexdigest()[:16]


def _iter_corpus():
    for folder in sorted(CORPUS.iterdir()):
        if folder.is_dir():
            for pdf in sorted(folder.glob("*.pdf")):
                yield folder.name, pdf


def _run(tag: str, jobs, out_name: str) -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = OUTDIR / out_name
    done = _done_keys(out)
    todo = [j for j in jobs if _key(j[0]) not in done]
    print(f"[{tag}] {len(todo)} to run ({len(done)} done)", flush=True)
    if not todo:
        return
    args = [(str(p), bk, wb) for p, bk, wb in todo]
    t0 = time.time()
    n = 0
    with out.open("a", encoding="utf-8") as fh, Pool(WORKERS) as pool:
        for rec in pool.imap_unordered(_process, args, chunksize=4):
            fh.write(json.dumps(rec, default=str) + "\n")
            fh.flush()
            n += 1
            if n % 100 == 0:
                dt = time.time() - t0
                print(f"[{tag}] {n}/{len(todo)} {dt:.0f}s eta {dt/n*(len(todo)-n):.0f}s", flush=True)


def main(sets) -> None:
    f2b = _folder_bank_map()
    # registered-layout coverage per bank for set B classification
    sys.path.insert(0, str(BACKEND))
    from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
    banks_with_layouts = {s.bank_key for s in DEFAULT_REGISTRY.specs()}

    if "a" in sets:
        jobs = []
        for line in BASE_VERIFIED.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            pdf = CORPUS / rec["folder"] / Path(rec["path"]).name
            if pdf.exists():
                jobs.append((pdf, f2b.get(rec["folder"], ""), True))
        _run("a", jobs, "u3a.jsonl")

    if "b" in sets:
        base_names = {(json.loads(l)["folder"], Path(json.loads(l)["path"]).name)
                      for l in BASE_VERIFIED.read_text(encoding="utf-8").splitlines()}
        skip_folders = {"Non_Bank_Documents", "Other_Unknown", "Human Verification"}
        jobs = []
        for folder, pdf in _iter_corpus():
            if folder in skip_folders or (folder, pdf.name) in base_names:
                continue
            jobs.append((pdf, f2b.get(folder, ""), True))
        _run("b", jobs, "u3b.jsonl")

    if "d" in sets:
        jobs = []
        for folder in ("Non_Bank_Documents", "Other_Unknown"):
            d = CORPUS / folder
            if d.is_dir():
                for pdf in sorted(d.glob("*.pdf")):
                    jobs.append((pdf, "", False))
        _run("d", jobs, "u3d.jsonl")


if __name__ == "__main__":
    main(set(sys.argv[1:]) or {"a"})
