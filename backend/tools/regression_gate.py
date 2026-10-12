"""U6d regression gate: replay a hash-locked set of corpus files through the
statement engine and fail on any change. The manifest stores only
sha8 + expected row-hash + verdict — never content.

Usage:
    python -m tools.regression_gate            # check against manifest
    python -m tools.regression_gate --write    # (re)build the manifest
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
CORPUS = ROOT.parent / "Unified All Statements"
MANIFEST = BACKEND / "tests" / "regression_manifest.json"

# The locked set: one readable statement per folder class (deterministic pick =
# smallest sha per folder below). Extend by adding folders + re-running --write.
FOLDERS = [
    "HDFC Bank", "SBI", "Axis Bank", "ICICI Bank", "Kotak Mahindra Bank",
    "IDFC First Bank", "Karnataka Bank", "Paytm Payments Bank", "Bank of India",
    "Bank of Baroda", "Indian Bank", "Canara Bank", "Union Bank of India",
    "Punjab National Bank", "CSB Bank", "UCO Bank", "Airtel Payments Bank",
    "Deutsche Bank", "Tamilnad Mercantile Bank", "Dhanlaxmi Bank",
]


def _sha8(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def _rows_hash(outcome) -> str:
    h = hashlib.sha256()
    for t in outcome.rows:
        x = t.txn
        h.update(f"{x.date}|{x.debit}|{x.credit}|{x.balance}\n".encode())
    return h.hexdigest()[:16]


def _pick(folder: Path) -> Path | None:
    best = None
    for p in folder.glob("*.pdf"):
        h = _sha8(p)
        if best is None or h < best[0]:
            best = (h, p)
    return best[1] if best else None


def _run_one(path: Path) -> dict:
    """T3 verdict + row hash for one file (universal reader, in-process)."""
    from app.services.statement_engine.universal.reader import read
    res = read(str(path))
    rec = {"sha": _sha8(path), "verdict": res.verdict, "code": res.code,
           "rows": res.meta.get("rows", 0)}
    if res.outcome is not None:
        rec["row_hash"] = _rows_hash(res.outcome)
    return rec


def main() -> int:
    write = "--write" in sys.argv
    picked = {}
    for folder in FOLDERS:
        d = CORPUS / folder
        if not d.is_dir():
            continue
        p = _pick(d)
        if p:
            picked[folder] = p
    if write:
        manifest = {}
        for folder, p in picked.items():
            try:
                manifest[folder] = _run_one(p)
                print(f"  {folder}: {manifest[folder]['verdict']} {manifest[folder]['rows']} rows")
            except Exception as exc:
                print(f"  {folder}: ERROR {type(exc).__name__}")
        MANIFEST.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        print(f"wrote {MANIFEST} ({len(manifest)} files)")
        return 0

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    diffs = []
    for folder, expected in manifest.items():
        p = picked.get(folder)
        if p is None or _sha8(p) != expected["sha"]:
            diffs.append(f"{folder}: corpus pick missing/changed (expected sha {expected['sha']})")
            continue
        got = _run_one(p)
        for k in ("verdict", "code", "rows", "row_hash"):
            if got.get(k) != expected.get(k):
                diffs.append(f"{folder}: {k} {expected.get(k)} -> {got.get(k)}")
    if diffs:
        print("REGRESSION GATE FAILED")
        for d in diffs:
            print(" -", d)
        return 1
    print(f"regression gate: {len(manifest)} files unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
