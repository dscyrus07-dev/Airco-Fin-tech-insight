"""Spec-independent audit of VERIFIED files.

For each sha8 (path from manifest): re-extract raw text with pdfplumber,
count dated amount-bearing text lines, recompute the running-balance chain
from the engine's own extracted rows, and compare first/last balances with
printed opening/closing anchors located by generic regex (not spec regexes).

usage: python tools/verify/audit_verify.py <backend> <manifest_dir> <run.jsonl> <out.jsonl>
           [--banks=..] [--per-bank N] [--seed S]
Only audits records with verdict==VERIFIED in run.jsonl.
"""
import json, os, random, re, sys
from decimal import Decimal

backend, manifest_dir, run_path, out_path = sys.argv[1:5]
banks, per_bank, seed = set(), 40, 20261013
for a in sys.argv[5:]:
    if a.startswith("--banks="):
        banks = set(a[8:].split(","))
    elif a.startswith("--per-bank="):
        per_bank = int(a[11:])
    elif a.startswith("--seed="):
        seed = int(a[7:])

sys.path.insert(0, backend)

# file index
folders = json.load(open(os.path.join(manifest_dir, "folders.json")))
f2b = {f: m["bank_id"] for f, m in folders.items() if isinstance(m, dict) and m.get("bank_id")}
paths = {}
for mf in ("manifest_0.jsonl", "manifest_1.jsonl"):
    for ln in open(os.path.join(manifest_dir, mf)):
        d = json.loads(ln)
        p = d.get("path", "")
        rel = p.replace(os.sep, "/")
        top = rel.split("Unified All Statements/")[-1].split("/")[0]
        b = f2b.get(top)
        if b:
            paths[d["sha8"]] = (p, b)

runs = [json.loads(ln) for ln in open(run_path, encoding="utf-8")]
cands = [r for r in runs if r.get("verdict") == "VERIFIED" and r["sha8"] in paths
         and (not banks or r["exp"] in banks)]
random.seed(seed)
bybank = {}
for r in cands:
    bybank.setdefault(r["exp"], []).append(r)
sel = [r for b in bybank for r in random.sample(bybank[b], min(per_bank, len(bybank[b])))]

DATE = re.compile(r"(?:\b\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}\b|\b\d{1,2}[- ](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[- ]\d{2,4}\b|\b\d{4}[-/]\d{2}[-/]\d{2}\b)", re.I)
AMT = re.compile(r"\d{1,3}(?:,\d{2,3})*\.\d{2}|\b\d+\.\d{2}\b")
OPEN = re.compile(r"(?i)open(?:ing)?\s*balance[^\d]*([\d,]+\.\d{2})")
CLOSE = re.compile(r"(?i)clos(?:ing|e)\s*balance[^\d]*([\d,]+\.\d{2})")
# lines that look like transactions: date + >=2 money tokens (amount + balance)
def dated_amount_lines(text):
    n = 0
    for ln in text.splitlines():
        if DATE.search(ln) and len(AMT.findall(ln)) >= 2:
            n += 1
    return n

def num(s):
    return Decimal(s.replace(",", ""))

import pdfplumber
from app.services.statement_engine.v2_router import route_pdf
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY

done = set()
if os.path.exists(out_path):
    done = {json.loads(l)["sha8"] for ln in open(out_path, encoding="utf-8")}

n = 0
with open(out_path, "a", encoding="utf-8") as out:
    for r in sel:
        if r["sha8"] in done:
            continue
        path, b = paths[r["sha8"]]
        rec = {"sha8": r["sha8"], "bank": b, "flags": []}
        try:
            r2 = route_pdf(path, DEFAULT_REGISTRY)
            txns = r2.result.transactions if r2.result else []
            text = ""
            with pdfplumber.open(path) as pdf:
                for pg in pdf.pages:
                    text += (pg.extract_text() or "") + "\n"
            dal = dated_amount_lines(text)
            nrows = len(txns)
            # dated amount-bearing lines above row count => potentially dropped rows
            if dal > nrows + 2:
                rec["flags"].append(f"line_gap:{dal}>{nrows}")
            # chain: bal[i] = bal[i-1] + credit - debit  (bal[-1] seed = opening anchor or bal0-amt0)
            bals = [t.balance for t in txns]
            chain_bad = 0
            if len(txns) >= 2:
                prev = bals[0]  # balance is post-row; chain forward from row 0
                for i in range(1, len(txns)):
                    exp = prev + (txns[i].credit or Decimal(0)) - (txns[i].debit or Decimal(0))
                    if abs(exp - bals[i]) > Decimal("0.02"):
                        chain_bad += 1
                    prev = bals[i]
            if chain_bad:
                rec["flags"].append(f"chain_breaks:{chain_bad}")
            mo, mc = OPEN.search(text), CLOSE.search(text)
            if mo and txns:
                opening = num(mo.group(1))
                first_bal = bals[0] - (txns[0].credit or 0) + (txns[0].debit or 0)
                if abs(opening - first_bal) > Decimal("0.02"):
                    rec["flags"].append("opening_mismatch")
            if mc and txns:
                closing = num(mc.group(1))
                if abs(closing - bals[-1]) > Decimal("0.02"):
                    rec["flags"].append("closing_mismatch")
            rec.update(rows=nrows, dal=dal, open=bool(mo), close=bool(mc))
        except Exception as e:
            rec["flags"].append("audit_err:" + str(e)[:60])
        out.write(json.dumps(rec) + "\n")
        out.flush()
        n += 1
        if n % 20 == 0:
            print("audited", n, flush=True)
print("AUDITED", n)
