"""U3c independent cross-check: re-derive transaction rows for sampled
T3-clean files with a standalone parser that shares NO code with the
universal reader or the extraction engine (raw pdfplumber only).

Usage: python tools/u3c_crosscheck.py <u3a.jsonl> <n> <out.jsonl>

For each sampled REVIEW file it rebuilds dated rows from raw word geometry,
extracts (date, debit, credit, balance) by right-edge clustering of numeric
tokens, and compares the multiset against `row_keys` recorded by U3.
"""
import hashlib
import json
import random
import re
import sys
from pathlib import Path

import pdfplumber

BACKEND = Path(__file__).resolve().parents[1]
CORPUS = BACKEND.parents[1] / "Unified All Statements"

DATE_PATTERNS = [
    (re.compile(r"^(\d{1,2})[ /-](\d{1,2})[ /-](\d{2,4})$"), "dmy"),
    (re.compile(r"^(\d{1,2})[- ]([A-Za-z]{3,9})[- ](\d{2,4})$"), "dmony"),
]
MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
          "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
NUM = re.compile(r"^[+-]?(?:Rs\.?|INR|₹)?\s*[+-]?\d[\d,]*\.?\d{0,2}\s*(?:[Dd][Rr]|[Cc][Rr])?\.?$")


def _num(t):
    t = t.strip().replace(",", "")
    suf = re.search(r"(?i)(cr|dr)\.?$", t)
    s = ""
    if suf:
        s = suf.group(1).lower()
        t = t[: suf.start()]
    t = re.sub(r"(?i)^(Rs\.?|INR|₹)\s*", "", t).strip()
    neg = t.startswith("-") or t.startswith("(")
    t = t.lstrip("+-(").rstrip(")")
    try:
        v = float(t)
    except ValueError:
        return None, ""
    return (-v if neg else v), s


def _date(t):
    for rx, kind in DATE_PATTERNS:
        m = rx.match(t.strip())
        if not m:
            continue
        if kind == "dmy":
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            d, mo, y = int(m.group(1)), MONTHS.get(m.group(2)[:3].lower(), 0), int(m.group(3))
        if y < 100:
            y += 2000
        if 1 <= d <= 31 and 1 <= mo <= 12 and 1990 <= y <= 2100:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def _lines(words):
    rows = {}
    for w in words:
        key = round(w["top"] / 3)
        rows.setdefault(key, []).append(w)
    out = []
    for _, ws in sorted(rows.items()):
        ws.sort(key=lambda w: w["x0"])
        merged, cur = [], None
        for w in ws:
            if cur and w["x0"] - cur["x1"] < 4:
                cur["text"] += " " + w["text"]
                cur["x1"] = w["x1"]
            else:
                if cur:
                    merged.append(cur)
                cur = dict(w)
        if cur:
            merged.append(cur)
        out.append(merged)
    return out


def extract_rows(path):
    """Standalone: cluster numeric right-edges on dated lines; last numeric = balance."""
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:150]:
            words = page.extract_words(x_tolerance=1.5) or []
            for line in _lines(words):
                date = next((_date(w["text"]) for w in line[:2] if _date(w["text"])), None)
                if not date:
                    continue
                nums = [(w["x1"], w["text"]) for w in line if NUM.match(w["text"].strip())]
                if len(nums) < 2:
                    continue
                nums.sort()
                vals = [_num(t) for _, t in nums]
                vals = [v for v, _ in vals if v is not None]
                bal = vals[-1]
                amount = vals[-2]
                rows.append((date, round(amount, 2), round(bal, 2)))
    return rows


def key_of(rec):
    cb = {}
    for t in rec:
        cb[(t[0], t[1], t[2])] = cb.get((t[0], t[1], t[2]), 0) + 1
    return cb


def main():
    u3a, n, outp = Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
    random.seed(11)
    recs = [json.loads(l) for l in u3a.open(encoding="utf-8")]
    clean = [r for r in recs if r["univ"].get("verdict") == "REVIEW" and r["univ"].get("row_keys")]
    sample = random.sample(clean, min(n, len(clean)))
    out = outp.open("a", encoding="utf-8")
    done = {json.loads(l)["sha"] for l in outp.open(encoding="utf-8")} if outp.exists() else set()
    for r in sample:
        if r["sha"] in done:
            continue
        pdf = CORPUS / r["folder"] / Path(r.get("path", "")).name
        # u3a has no path field: find the file by content sha
        if not pdf.is_file():
            d = CORPUS / r["folder"]
            pdf = None
            for f in sorted(d.glob("*.pdf")):
                h = hashlib.sha256()
                with open(f, "rb") as fh:
                    for ch in iter(lambda: fh.read(1 << 20), b""):
                        h.update(ch)
                if h.hexdigest()[:8] == r["sha"]:
                    pdf = f
                    break
            if pdf is None:
                continue
        try:
            mine = extract_rows(str(pdf))
        except Exception as exc:
            out.write(json.dumps({"sha": r["sha"], "error": type(exc).__name__}) + "\n")
            continue
        theirs = {}
        for row in r["univ"]["row_keys"]:
            d_, dr, cr, bal = row[0], row[1], row[2], row[3]
            amt = dr if dr is not None else (cr if cr is not None else None)
            if amt is None or bal is None:
                continue
            k = (d_, round(float(amt), 2), round(float(bal), 2))
            theirs[k] = theirs.get(k, 0) + 1
        mine_c = key_of(mine)
        missing = sum(max(0, theirs[k] - mine_c.get(k, 0)) for k in theirs)
        extra = sum(max(0, mine_c[k] - theirs.get(k, 0)) for k in mine_c)
        out.write(json.dumps({"sha": r["sha"], "folder": r["folder"],
                              "univ_rows": sum(theirs.values()), "ind_rows": sum(mine_c.values()),
                              "missing_vs_univ": missing, "extra_vs_univ": extra}) + "\n")
        out.flush()
    print("done")


if __name__ == "__main__":
    main()
