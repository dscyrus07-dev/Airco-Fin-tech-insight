# audit_bank.py — independent audit of VERIFIED files for a bank.
# For a seeded sample of hold-out VERIFIED files, without using the spec:
#   1. dated amount-bearing text lines vs rows read (row completeness)
#   2. running-balance chain recomputed from engine rows
#   3. printed opening/closing anchors (generic regexes) vs engine anchors
# Writes .local/eval/<bank>.audit.json. Counts only, no statement content.
import os, sys, json, glob, re, random
from decimal import Decimal

HERE = os.path.dirname(__file__)
LOCAL = os.path.join(HERE, ".local")
BACKEND = os.path.abspath(os.path.join(HERE, "..", "..", "backend"))
sys.path.insert(0, BACKEND)

os.environ.setdefault("STATEMENT_ENGINE_V2_MODE", "shadow")

from app.services.statement_engine.v2_router import route_pdf
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY as REG

D = r"(?:0?[1-9]|[12]\d|3[01])"
M = r"(?:0?[1-9]|1[0-2])"
MON = r"[A-Za-z]{3,9}"
DATE_ANY = re.compile(rf"(?<![\d.,])(?:{D}[-/.]{M}[-/.]\d{{2,4}}|{D}[-/. ]{MON}[-/. ,]*\d{{2,4}}|\d{{4}}-\d{{2}}-\d{{2}})(?!\d)")
AMT = re.compile(r"\d[\d,]*\.\d{2}")
NON_ROW = re.compile(r"(?i)opening\s*balance|closing\s*balance|b/f|brought\s*forward|carried\s*forward|c/f|"
                     r"total|summary|statement\s*period|page\s*\d|generated|grand")
BAL_ANCHOR = re.compile(r"(?i)(opening|closing)\s*balance[^\d]*([\d,]+\.\d{2})|"
                        r"(balance)\s*(brought|carried)?\s*forward[^\d]*([\d,]+\.\d{2})")
DEC = Decimal

def audit_file(path):
    import pdfplumber
    lines = []
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            lines += [l for l in (pg.extract_text() or "").splitlines() if l.strip()]
    dated_amt = [l for l in lines if DATE_ANY.search(l) and AMT.search(l) and not NON_ROW.search(l)]
    anchors = dict()
    for l in lines:
        m = BAL_ANCHOR.search(re.sub(r"\s+", "", l)) or BAL_ANCHOR.search(l)
        if m:
            if m.group(3):  # balance forward -> opening
                anchors.setdefault("opening", DEC(m.group(5).replace(",", "")))
            else:
                anchors[m.group(1).lower()] = DEC(m.group(2).replace(",", ""))
    r = route_pdf(path, REG)
    if r.status != "v2" or not r.result:
        return {"skip": True, "status": r.status, "fb": r.fallback_reason}
    rows = list(r.result.transactions or [])
    extras = getattr(r.result.metadata, "extras", None) or {}
    verdict = extras.get("verdict")
    reasons = list(extras.get("verdict_reasons") or extras.get("reasons") or [])
    warns = list(extras.get("warnings") or [])[:8]
    # chain: each printed balance - prev = amount on the row (dir from debit/credit)
    breaks = 0
    for a, b in zip(rows, rows[1:]):
        da = (b.credit or DEC(0)) - (b.debit or DEC(0))
        if a.balance + da != b.balance:
            if a.balance - da != b.balance:  # reversed order tolerated
                breaks += 1
    out = {
        "verdict": verdict, "reasons": reasons, "warns": warns,
        "rows": len(rows), "dated_amt_lines": len(dated_amt),
        "chain_breaks": breaks,
        "anchor_opening": str(anchors.get("opening", "")),
        "anchor_closing": str(anchors.get("closing", "")),
        "first_bal": str(rows[0].balance) if rows else "",
        "last_bal": str(rows[-1].balance) if rows else "",
    }
    out["row_gap"] = len(dated_amt) - len(rows)
    if "opening" in anchors and rows:
        out["opening_match"] = anchors["opening"] == rows[0].balance - (
            (rows[0].credit or DEC(0)) - (rows[0].debit or DEC(0))) or anchors["opening"] == rows[0].balance
    if "closing" in anchors and rows:
        out["closing_match"] = anchors["closing"] == rows[-1].balance
    return out

def main(bid, n=30, seed=7):
    folders = json.load(open(os.path.join(LOCAL, "folders.json")))
    manifest = {}
    for f in glob.glob(os.path.join(LOCAL, "manifest*.jsonl")):
        for l in open(f, encoding="utf-8"):
            try:
                j = json.loads(l); manifest[j["sha8"]] = j["path"]
            except Exception: pass
    scans = []
    for f in glob.glob(os.path.join(LOCAL, "scan_meta*.jsonl")):
        for l in open(f, encoding="utf-8"):
            try: scans.append(json.loads(l))
            except Exception: pass
    my = {k for k, v in folders.items() if v["bank_id"] == bid}
    def top(s):
        p = manifest.get(s["sha8"], "")
        low = p.lower().replace("/", "\\")
        i = low.find("unified all statements")
        return s["folder"] if i < 0 else p[i+len("unified all statements"):].lstrip("\\/").split("\\")[0].split("/")[0]
    probes = {}
    for l in open(os.path.join(LOCAL, "probe_shadow.jsonl"), encoding="utf-8"):
        try:
            j = json.loads(l); probes[j["sha8"]] = j
        except Exception: pass
    cand = [s["sha8"] for s in scans
            if top(s) in my and s.get("has_text") and not s.get("locked")
            and probes.get(s["sha8"], {}).get("verdict") == "VERIFIED"
            and s["sha8"] in manifest]
    rng = random.Random(seed); pick = sorted(cand); rng.shuffle(pick)
    # second sample: non-VERIFIED v2/fallback files -> capture check reasons for the doc
    other = [s["sha8"] for s in scans
             if top(s) in my and s.get("has_text") and not s.get("locked")
             and probes.get(s["sha8"], {}).get("status") in ("v2", "fallback")
             and probes.get(s["sha8"], {}).get("verdict") != "VERIFIED"
             and s["sha8"] in manifest]
    rng2 = random.Random(seed + 1); opick = sorted(other); rng2.shuffle(opick)
    res = []
    for sha in pick[:n]:
        try:
            r = audit_file(manifest[sha]); r["sha8"] = sha
        except Exception as e:
            r = {"sha8": sha, "err": type(e).__name__}
        res.append(r)
        print(".", end="", flush=True)
    reasons = []
    for sha in opick[:15]:
        try:
            r = route_pdf(manifest[sha], REG)
            ex = (getattr(r.result.metadata, "extras", None) or {}) if r.result else {}
            reasons.append({"sha8": sha, "status": r.status, "fb": r.fallback_reason,
                            "verdict": ex.get("verdict"),
                            "reasons": list(ex.get("verdict_reasons") or ex.get("reasons") or [])[:6]})
        except Exception as e:
            reasons.append({"sha8": sha, "err": type(e).__name__})
        print(":", end="", flush=True)
    # positive row_gap only: dated amount lines exceeding parsed rows = dropped rows.
    # negative gaps are expected on inherit-date layouts (undated rows carry amounts).
    bad = [r for r in res if "err" in r or r.get("chain_breaks", 0) > 2
           or r.get("row_gap", 0) > max(2, 0.1 * r.get("rows", 1))
           or r.get("opening_match") is False or r.get("closing_match") is False]
    out = {"bank_id": bid, "audited": len(res), "sampled": len(pick[:n]),
           "verified_pool": len(cand), "ok": len(res) - len(bad), "bad": len(bad),
           "bad_detail": [r for r in bad][:10],
           "reasons_sample": reasons,
           "files": res}
    outp = os.path.join(LOCAL, "eval", f"{bid}.audit.json")
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    json.dump(out, open(outp, "w"), indent=1)
    print(f"\n{bid}: audited={len(res)} ok={out['ok']} bad={len(bad)}")

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 30)
