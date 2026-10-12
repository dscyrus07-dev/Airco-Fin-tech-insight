# bank_eval.py — per-bank gate metrics from probe/xcheck/scan artifacts.
# Emits .local/eval/<bank>.json used by bank_doc.py and the report.
import os, sys, json, glob
from collections import Counter, defaultdict

HERE = os.path.dirname(__file__)
LOCAL = os.path.join(HERE, ".local")

def load_jsonl(pat):
    rows = []
    for f in glob.glob(os.path.join(LOCAL, pat)):
        for l in open(f, encoding="utf-8"):
            try: rows.append(json.loads(l))
            except Exception: pass
    return rows

folders = json.load(open(os.path.join(LOCAL, "folders.json")))
scans = load_jsonl("scan_meta*.jsonl")
probes = {r["sha8"]: r for r in load_jsonl("probe_shadow.jsonl") if "sha8" in r}
xcheck = load_jsonl("xcheck.jsonl")

manifest = {}
for f in glob.glob(os.path.join(LOCAL, "manifest*.jsonl")):
    for l in open(f, encoding="utf-8"):
        try:
            j = json.loads(l); manifest[j["sha8"]] = j["path"]
        except Exception: pass
ROOT_PREFIX = "unified all statements"
def top_folder(s):
    p = manifest.get(s["sha8"], "")
    low = p.lower().replace("/", "\\")
    i = low.find(ROOT_PREFIX)
    if i < 0: return s["folder"]
    return p[i + len(ROOT_PREFIX):].lstrip("\\/").split("\\")[0].split("/")[0] or "(root)"

sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "backend")))
try:
    from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY as _REG
    LAYOUT2BANK = {s.layout_id: s.bank_key for s in _REG.specs()}
except Exception:
    LAYOUT2BANK = {}

ID_ALIAS = {"bob": "bank_of_baroda", "bom": "bank_of_maharashtra",
            "equitas": "equitas_sfb", "scb": "standard_chartered",
            "ujjivan": "ujjivan_sfb"}
def canon(b): return ID_ALIAS.get(b, b)

def detected_bank(p):
    if not p: return None
    if p.get("status") == "v2":
        d = p.get("layout_bank") or LAYOUT2BANK.get(p.get("layout")) \
            or (p.get("layout") or "").split("_")[0] or None
        return d
    fb = p.get("fb") or ""
    for pre in ("other_bank:", "legacy_only:"):
        if fb.startswith(pre): return fb[len(pre):]
    return p.get("detected")

def det_ok(p, bid):
    d = detected_bank(p)
    if not d: return None
    return canon(d) == bid

def evaluate(bid):
    my_folders = {k for k, v in folders.items() if v["bank_id"] == bid}
    files = [s for s in scans if top_folder(s) in my_folders]
    text = [f for f in files if f.get("has_text") and not f.get("locked") and not f.get("corrupt")]
    pr = [probes.get(f["sha8"]) for f in text if f["sha8"] in probes]
    det = Counter(det_ok(p, bid) for p in pr)
    tier = Counter((p or {}).get("status") for p in pr)
    verdicts = Counter((p or {}).get("verdict") for p in pr)
    fb = Counter((p or {}).get("fb") for p in pr if (p or {}).get("fb"))
    rows_tot = sum((p or {}).get("rows", 0) for p in pr)
    # cross-bank: files from OTHER folders attributed to me
    fa = [x for x in xcheck if canon(x.get("layout_bank") or x.get("detected") or "") == bid
          and folders.get(x["folder"], {}).get("bank_id") != bid]
    # spec coverage = share of text files that routed v2
    v2_n = tier.get("v2", 0)
    return {
        "bank_id": bid, "folders": sorted(my_folders),
        "total": len(files), "text_n": len(text),
        "scanned_n": sum(1 for f in files if not f.get("has_text") and not f.get("locked") and not f.get("corrupt")),
        "locked_n": sum(1 for f in files if f.get("locked")),
        "probed_n": len(pr),
        "det_ok": det.get(True, 0), "det_wrong": det.get(False, 0), "det_none": det.get(None, 0),
        "det_ok_pct": round(100 * det.get(True, 0) / len(pr), 1) if pr else None,
        "tier": dict(tier), "v2_pct": round(100 * v2_n / len(text), 1) if text else 0,
        "verdicts": {k: v for k, v in verdicts.items() if k},
        "fb": dict(fb), "rows_total": rows_tot,
        "xcheck_false_accepts": [{"sha8": x["sha8"], "folder": x["folder"],
                                  "via": "layout" if canon(x.get("layout_bank") or "") == bid else "detector"}
                                 for x in fa],
        "xcheck_false_accept_n": len(fa),
    }

if __name__ == "__main__":
    os.makedirs(os.path.join(LOCAL, "eval"), exist_ok=True)
    bids = sys.argv[1:] or sorted({v["bank_id"] for v in folders.values() if v["bank_id"]})
    for bid in bids:
        ev = evaluate(bid)
        json.dump(ev, open(os.path.join(LOCAL, "eval", f"{bid}.json"), "w"), indent=1)
        print(bid, "det_ok%", ev["det_ok_pct"], "v2%", ev["v2_pct"],
              "fa:", ev["xcheck_false_accept_n"], dict(ev["verdicts"]))
